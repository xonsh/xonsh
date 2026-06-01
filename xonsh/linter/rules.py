"""Lint rules for xonsh source code.

Each rule is a plain function ``(tree) -> list[Finding]`` operating on the
*transformed* xonsh AST (a standard :mod:`ast` ``Module`` in which subprocess
lines have been lowered to ``__xonsh__.subproc_*`` calls, so shell command
words are opaque string constants and never masquerade as Python names).

The MVP ships four rules:

* ``XSH001`` — a ``$VAR`` whose name is unknown but is a close match for a real
  xonsh environment variable (likely a typo).
* ``XSH002`` — a string literal assigned to a ``$VAR`` whose registered
  validator rejects it (e.g. ``$XONSH_STORE_STDOUT = 'yes'`` instead of
  ``True``).
* ``XSH003`` — use of a deprecated environment variable.
* ``XSH101`` — an import bound name that is never used (pyflakes' F401).

The env-var rules draw their source of truth from :data:`xonsh.environ.DEFAULT_VARS`
(~157 vars, each a ``Var`` carrying ``validate`` / ``deprecated`` metadata),
which is something no generic Python or shell linter can know about.
"""

from __future__ import annotations

import ast
import difflib
from typing import NamedTuple


class Finding(NamedTuple):
    line: int
    col: int  # 1-based, to match the syntax-checker's diagnostics
    code: str
    message: str


# Only flag an unknown ``$VAR`` as a typo when it is *this* close to a real
# variable name. High cutoff keeps legitimately-custom env vars silent.
_CLOSE_CUTOFF = 0.8


def _known_env_vars():
    # Imported lazily: keeps ``import xonsh.linter`` cheap and avoids paying the
    # environ import cost unless a file is actually linted.
    from xonsh.environ import DEFAULT_VARS

    return DEFAULT_VARS


def _env_var_name(node):
    """If *node* is ``__xonsh__.env['NAME']`` (a ``$VAR`` / ``${'NAME'}`` in
    Python mode), return ``'NAME'``; otherwise ``None``.

    Dynamic forms like ``${expr}`` with a non-constant subscript return ``None``
    — there is no static name to check.
    """
    if not isinstance(node, ast.Subscript):
        return None
    val = node.value
    if not (
        isinstance(val, ast.Attribute)
        and val.attr == "env"
        and isinstance(val.value, ast.Name)
        and val.value.id == "__xonsh__"
    ):
        return None
    sl = node.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    return None


def _pos(node):
    return getattr(node, "lineno", 0), getattr(node, "col_offset", 0) + 1


def check_env_vars(tree) -> list[Finding]:
    """XSH001 (typo), XSH002 (bad literal value), XSH003 (deprecated)."""
    dv = _known_env_vars()
    known = list(dv)
    out: list[Finding] = []

    # Pass 1: every $VAR read or write — typo (unknown but close) or deprecated.
    for node in ast.walk(tree):
        name = _env_var_name(node)
        if name is None:
            continue
        line, col = _pos(node)
        if name not in dv:
            match = difflib.get_close_matches(name, known, n=1, cutoff=_CLOSE_CUTOFF)
            if match:
                out.append(
                    Finding(
                        line,
                        col,
                        "XSH001",
                        f"unknown environment variable ${name}; "
                        f"did you mean ${match[0]}?",
                    )
                )
        elif getattr(dv[name], "deprecated", False):
            out.append(
                Finding(
                    line, col, "XSH003", f"environment variable ${name} is deprecated"
                )
            )

    # Pass 2: ``$KNOWN_VAR = <str literal>`` whose validator rejects the value.
    # Restricted to *string* literals on purpose — a quoted bool/number is the
    # classic mistake (``$XONSH_STORE_STDOUT = 'yes'``), while bare ``0``/``1``
    # ints stay unflagged so we don't fight users who spell bools that way.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        val = node.value
        if not (isinstance(val, ast.Constant) and isinstance(val.value, str)):
            continue
        for tgt in node.targets:
            name = _env_var_name(tgt)
            if name is None or name not in dv:
                continue
            validate = getattr(dv[name], "validate", None)
            if validate is None:
                continue
            try:
                ok = bool(validate(val.value))
            except Exception:
                # Inconclusive — stay silent rather than risk a false positive.
                ok = True
            if not ok:
                line, col = _pos(tgt)
                out.append(
                    Finding(
                        line,
                        col,
                        "XSH002",
                        f"invalid value {val.value!r} for ${name} "
                        f"(failed {getattr(validate, '__name__', 'validation')})",
                    )
                )
    return out


def _dunder_all_names(tree) -> set[str]:
    """Names listed in a module-level ``__all__`` count as 'used'."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        out.add(elt.value)
    return out


def check_unused_imports(tree) -> list[Finding]:
    """XSH101 — an imported name that is never loaded anywhere in the module."""
    imports = []  # (bound_name, lineno, col, label)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                bound = a.asname or a.name.partition(".")[0]
                label = f"{a.name} as {a.asname}" if a.asname else a.name
                imports.append((bound, *_pos(node), label))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue  # __future__ imports are directives, never "used"
            mod = node.module or ""
            for a in node.names:
                if a.name == "*":
                    continue  # star imports bind unknown names — can't track
                bound = a.asname or a.name
                label = f"{mod}.{a.name}" if mod else a.name
                if a.asname:
                    label += f" as {a.asname}"
                imports.append((bound, *_pos(node), label))
    if not imports:
        return []

    used = {
        n.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    used |= _dunder_all_names(tree)

    return [
        Finding(line, col, "XSH101", f"{label!r} imported but unused")
        for bound, line, col, label in imports
        if bound not in used
    ]


#: All rules run by :func:`xonsh.linter.cli.lint_source`, in order.
ALL_RULES = (check_env_vars, check_unused_imports)
