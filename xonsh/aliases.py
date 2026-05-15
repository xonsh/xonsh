"""Aliases for the xonsh shell."""

import argparse
import functools
import inspect
import operator
import os
import pathlib
import re
import shlex
import shutil
import sys
import textwrap
import types
import typing as tp
from collections import abc as cabc
from pathlib import Path
from typing import Literal

import xonsh.completers._aliases as xca
import xonsh.history.main as xhm
import xonsh.xoreutils.which as xxw
import xonsh.xoreutils.xcontext as xxt
from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.dirstack import _get_cwd, cd, dirs, popd, pushd
from xonsh.environ import locate_binary, make_args_env
from xonsh.foreign_shells import foreign_shell_data
from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers.ast import isexpression
from xonsh.platform import (
    IN_APPIMAGE,
    ON_ANACONDA,
    ON_DARWIN,
    ON_DRAGONFLY,
    ON_FREEBSD,
    ON_NETBSD,
    ON_OPENBSD,
    ON_WINDOWS,
)
from xonsh.procs.executables import locate_file
from xonsh.procs.jobs import bg, clean_jobs, disown, fg, jobs
from xonsh.procs.specs import DecoratorAlias, SpecAttrDecoratorAlias
from xonsh.timings import timeit_alias
from xonsh.tools import (
    XonshError,
    adjust_shlvl,
    argvquote,
    capturable,
    escape_windows_cmd_string,
    print_color,
    print_exception,
    strip_simple_quotes,
    swap_values,
    threadable,
    to_repr_pretty_,
    to_shlvl,
    uncapturable,
    unthreadable,
)
from xonsh.xontribs import xontribs_main


@lazyobject
def EXEC_ALIAS_RE():
    return re.compile(r"@\(|\$\(|!\(|\$\[|!\[|\&\&|\|\||\s+and\s+|\s+or\s+|[>|<]")


def get_alias_name(name_or_func, dash_case=True):
    """Derive an alias name from a function or a string.

    For functions, uses ``__name__`` with a single leading underscore stripped
    (so ``_hello`` becomes ``hello``). Strings are used as-is. If ``dash_case``
    is True, underscores are replaced with dashes.
    """
    if callable(name_or_func):
        name = name_or_func.__name__
        if name.startswith("_"):
            name = name[1:]
    else:
        name = name_or_func
    if dash_case:
        name = name.replace("_", "-")
    return name


class AliasReturnCommandResult(list):
    """List subclass that can carry local_env from return_command aliases."""

    local_env: dict

    def __init__(self, *args, local_env=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_env = local_env or {}


def _normalize_return_command_result(val, alias_repr):
    """Normalize the return value of a ``@return_command`` alias.

    A ``return_command`` alias may return either:

    - a non-empty ``list`` — the resolved command tokens, with **no** env
      overlay attached to the returned command,
    - a ``dict`` with a required ``"cmd"`` key (a non-empty list of tokens)
      and an optional ``"env"`` key (a ``dict``) — the command tokens plus
      an env overlay that applies **only** to the returned command.

    The ``env=`` kwarg the alias received is a separate concept: it is an
    overlay active **during the function body** (mutating it affects
    subprocesses the alias runs inline, just like for an ordinary callable
    alias). It is independent of the returned command's env — to set env
    for the returned command, the alias must use dict-return.

    Raises ``ValueError`` on malformed returns, using ``alias_repr`` in the
    message so the user can tell which alias produced the bad value.

    Returns
    -------
    cmd : list
        The command tokens to execute.
    returned_env : dict
        The env overlay for the returned command (empty dict if the alias
        returned a bare list or a dict without ``"env"``).
    """
    returned_env: dict = {}
    if isinstance(val, dict):
        env_overlay = val.get("env")
        if env_overlay is not None:
            if not isinstance(env_overlay, dict):
                raise ValueError(
                    f"return_command alias {alias_repr}: 'env' must be a dict, "
                    f"got {env_overlay!r}."
                )
            returned_env = dict(env_overlay)
        val = val.get("cmd")
    if not isinstance(val, list) or not val:
        raise ValueError(
            f"return_command alias {alias_repr}: wrong return value {val!r}, "
            f"expected a non-empty list or dict with command."
        )
    return val, returned_env


class FuncAlias:
    """Provides a callable alias for xonsh commands."""

    attributes_show = ["__xonsh_threadable__", "__xonsh_capturable__", "return_what"]
    attributes_inherit = attributes_show + ["__doc__"]
    return_what: Literal["command", "result"] = "result"

    def __init__(self, name, func=None):
        self.__name__ = self.name = name
        self.func = func
        for attr in self.attributes_inherit:
            if (val := getattr(func, attr, None)) is not None:
                self.__setattr__(attr, val)

    def __repr__(self):
        r = {"name": self.name, "func": self.func.__name__}
        r |= {
            attr: val
            for attr in self.attributes_show
            if (val := getattr(self, attr, None)) is not None
        }
        return f"FuncAlias({repr(r)})"

    def __call__(
        self,
        args=None,
        stdin=None,
        stdout=None,
        stderr=None,
        spec=None,
        stack=None,
        decorators=None,
        alias_name=None,
        called_alias_name=None,
        env=None,
    ):
        return run_alias_by_params(
            self.func,
            {
                "args": args,
                "stdin": stdin,
                "stdout": stdout,
                "stderr": stderr,
                "spec": spec,
                "stack": stack,
                "decorators": decorators,
                "alias_name": getattr(self.func, "__alias_name__", alias_name),
                "called_alias_name": called_alias_name,
                "env": env,
            },
        )


def print_alias_help(name: str, superhelp: bool = False) -> None:
    """Print info about an alias to the active shell.

    Used by the ``cmd?``/``cmd??`` subprocess-mode help syntax.
    Output is colorized via xonsh color tokens.

    Parameters
    ----------
    name
        Alias name (must be present in ``XSH.aliases``).
    superhelp
        If True (``cmd??``), include docstring, threadable/capturable
        flags, source location and source code for ``FuncAlias``.
    """
    import xonsh.tools as xt
    from xonsh.procs.executables import locate_executable

    def _label(text):
        return "{YELLOW}" + text + "{RESET}"

    alias = XSH.aliases[name]
    lines = [f"{_label('Alias:')} {repr(alias)}"]

    # Expanded form (skip if expansion stops at a callable — then only the
    # alias name was replaced by the function object itself, no extra info).
    try:
        expanded = XSH.aliases.get([name])
    except Exception:
        expanded = None
    if expanded is not None and not callable(expanded[0]):
        lines.append(f"{_label('Expanded:')} {repr(list(expanded))}")

    # Resolved arg0 of the expanded list (only when arg0 is a string —
    # callables have no path).
    if expanded and isinstance(expanded[0], str):
        arg0 = expanded[0]
        arg0_path = locate_executable(arg0)
        if arg0_path is not None and arg0_path != arg0:
            lines.append(f"{_label('Resolved ' + arg0 + ':')} {repr(arg0_path)}")

    func = getattr(alias, "func", None)

    # Docstring is shown for both ``?`` and ``??``.
    doc = XSH.aliases.get_doc(name)
    if doc:
        from xonsh.environ import _rst_inline_to_color

        lines.append(f"{_label('Descr:')} {_rst_inline_to_color(doc)}")

    if superhelp:
        # FuncAlias-only metadata.
        if func is not None:
            threadable = getattr(alias, "__xonsh_threadable__", None)
            capturable = getattr(alias, "__xonsh_capturable__", None)
            if threadable is not None:
                lines.append(f"{_label('Threadable:')} {threadable}")
            if capturable is not None:
                lines.append(f"{_label('Capturable:')} {capturable}")

            # Unwrap ``functools.wraps``-style chains so the shown source
            # reflects the user-visible function (e.g. a click command body)
            # rather than the internal wrapper.
            try:
                src_func = inspect.unwrap(func)
            except ValueError:
                src_func = func
            co = getattr(src_func, "__code__", None)
            if co is not None:
                lines.append(
                    f"{_label('Source:')} {co.co_filename}:{co.co_firstlineno}"
                )
            try:
                src = inspect.getsource(src_func)
            except (OSError, TypeError):
                src = None
            if src:
                lines.append(f"{_label('Code:')}\n{textwrap.dedent(src).rstrip()}")
            else:
                lines.append(f"{_label('Code:')} <source unavailable>")

    xt.print_color("\n".join(lines))


class Aliases(cabc.MutableMapping):
    """Represents a location to hold and look up aliases."""

    def __init__(self, *args, **kwargs):
        self._raw = {}
        # Per-alias docstring registry. Populated when an alias is assigned
        # via the dict-form ``aliases[k] = {"alias": ..., "doc": "..."}``
        # (which lets list/string aliases carry a description), and consumed
        # by :meth:`get_doc` with priority over the alias object's own
        # ``__doc__``. Cleared on overwrite/delete so a stale doc never
        # sticks to a different value bound under the same name.
        self._docs: dict[str, str] = {}
        self.update(*args, **kwargs)

    def __dir__(self):
        d = set(super().__dir__())
        d.update(("click", "register_click_command"))
        return list(d)

    def __getattr__(self, name):
        # Lazy click integration: import is deferred until the first access
        # to ``aliases.click`` or ``aliases.register_click_command``, so
        # xonsh sessions that never use click don't pay the import cost.
        # Once loaded, the attributes are cached on ``self.__dict__`` and
        # future lookups skip this method entirely.
        if name in ("click", "register_click_command"):
            try:
                self._add_click_command()
            except ImportError:
                raise AttributeError(
                    f"{name!r} requires the 'click' package to be installed"
                ) from None
            return self.__dict__[name]
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def _add_click_command(self):
        """Expose the click integration helpers on this Aliases instance.

        Lazily invoked from :meth:`__getattr__` on first access to
        ``self.click`` or ``self.register_click_command``. Imports the
        ``click`` module and caches:

        * ``self.click`` — the ``click`` module itself, for convenient
          access from xonshrc / user scripts.
        * ``self.register_click_command`` — decorator factory bound to this
          Aliases instance via :func:`functools.partial`. See
          :func:`_click_command_alias`.

        Raises :class:`ImportError` if ``click`` is not installed; callers
        (``__getattr__``) translate this to :class:`AttributeError`.
        """
        import click

        self.click = click
        self.register_click_command = functools.partial(
            _click_command_alias, _aliases=self
        )

    def _register(self, func, name="", dash_case=True):
        name = get_alias_name(name or func, dash_case=dash_case)
        func.__alias_name__ = name
        self[name] = func
        return func

    @tp.overload
    def register(self, func: types.FunctionType) -> types.FunctionType:
        """simple usage"""

    @tp.overload
    def register(
        self, name: str, *, dash_case: bool = True
    ) -> tp.Callable[[types.FunctionType], types.FunctionType]: ...

    def register(self, func_or_name, name=None, dash_case=True):
        """Decorator to register the given function by name."""

        if isinstance(func_or_name, types.FunctionType):
            return self._register(func_or_name, name, dash_case)

        def wrapper(func):
            return self._register(func, func_or_name, dash_case)

        return wrapper

    @staticmethod
    def completer(completer_func):
        """Decorator that attaches a completer function to an alias.

        Usage::

            def _my_completer(command, alias):
                return {'opt1', 'opt2'}

            @aliases.register
            @aliases.completer(_my_completer)
            def _hello(args):
                echo @(args)

        Now ``hello <TAB>`` will suggest ``opt1`` and ``opt2``.
        """

        def decorator(func):
            func.xonsh_complete = completer_func
            return func

        return decorator

    @staticmethod
    def return_command(f):
        """Decorator that switches alias from returning result to return in new command for execution."""
        f.return_what = "command"
        return f

    unthreadable = staticmethod(unthreadable)
    threadable = staticmethod(threadable)
    uncapturable = staticmethod(uncapturable)
    capturable = staticmethod(capturable)

    def eval_alias(
        self,
        value,
        seen_tokens=frozenset(),
        acc_args=(),
        decorators=None,
        env_out=None,
    ):
        """
        "Evaluates" the alias ``value``, by recursively looking up the leftmost
        token and "expanding" if it's also an alias.

        A value like ``["cmd", "arg"]`` might transform like this:
        ``> ["cmd", "arg"] -> ["ls", "-al", "arg"] -> callable()``
        where ``cmd=ls -al`` and ``ls`` is an alias with its value being a
        callable.  The resulting callable will be "partially applied" with
        ``["-al", "arg"]``.

        ``env_out``, if given, is a mutable dict that accumulates the env
        overlay requested by any ``return_command`` alias encountered while
        resolving the chain (via dict-return ``"env"`` key). The top-level
        :meth:`get` caller passes its own collector dict here.
        """
        decorators = decorators if decorators is not None else []
        # Beware of mutability: default values for keyword args are evaluated
        # only once.
        if (
            isinstance(value, cabc.Iterable)
            and hasattr(value, "__len__")
            and len(value) > 1
        ):
            i = 0
            for v in value:
                if isinstance(mod := self._raw.get(str(v)), DecoratorAlias):
                    decorators.append(mod)
                    i += 1
                else:
                    break
            value = value[i:]

        if callable(value) and getattr(value, "return_what", "result") == "command":
            alias_repr = repr(getattr(value, "__name__", value))
            # ``kwarg_env`` is a live overlay: while the alias body runs,
            # mutating it affects commands the alias spawns inline (same
            # semantics as the ``env=`` kwarg for a normal callable alias).
            # It does NOT flow to the returned command — for that, the
            # alias must return a dict with an ``"env"`` key.
            kwarg_env: dict = {}
            try:
                with XSH.env.swap(overlay=kwarg_env):
                    value = value(acc_args, decorators=decorators, env=kwarg_env)
                acc_args = []
            except Exception as e:
                print_exception(f"Exception inside alias {alias_repr}: {e}")
                return None
            value, returned_env = _normalize_return_command_result(
                value, alias_repr=alias_repr
            )
            if env_out is not None and returned_env:
                env_out.update(returned_env)

        if callable(value):
            return [value] + list(acc_args)
        else:
            expand_path = XSH.expand_path
            token, *rest = map(expand_path, value)
            if token in seen_tokens or token not in self._raw:
                # ^ Making sure things like `egrep=egrep --color=auto` works,
                # and that `l` evals to `ls --color=auto -CF` if `l=ls -CF`
                # and `ls=ls --color=auto`
                rtn = [token]
                rtn.extend(rest)
                rtn.extend(acc_args)
                return rtn
            else:
                seen_tokens = seen_tokens | {token}
                acc_args = rest + list(acc_args)
                return self.eval_alias(
                    self._raw[token],
                    seen_tokens,
                    acc_args,
                    decorators=decorators,
                    env_out=env_out,
                )

    def get(
        self,
        key,
        default=None,
        decorators=None,
    ):
        """
        Returns list that represent command with resolved aliases.
        The ``key`` can be string with alias name or list for a command.
        In the first position will be the resolved command name or callable alias.
        If the key is not present, then `default` is returned.

        ``decorators`` is the list of `DecoratorAlias` objects that found during
        resolving aliases (#5443).

        Note! The return value is always list because during resolving
        we can find return_command alias that can completely replace
        command and add new arguments.
        """
        decorators = decorators if decorators is not None else []
        args = []
        if isinstance(key, list):
            args = key[1:]
            key = key[0]
        val = self._raw.get(key)
        # Env overlay collected for the RETURNED command — from a dict-return
        # at any level of the alias chain. Kept strictly separate from the
        # ``env=`` kwarg, which is a live overlay active only during the body
        # of a return_command alias.
        returned_env: dict = {}
        if callable(val) and getattr(val, "return_what", "result") == "command":
            kwarg_env: dict = {}
            try:
                with XSH.env.swap(overlay=kwarg_env):
                    val = val(args, decorators=decorators, env=kwarg_env)
                args = []
            except Exception as e:
                print_exception(f"Exception inside alias {key!r}: {e}")
                return None
            val, returned_env = _normalize_return_command_result(
                val, alias_repr=repr(key)
            )

        if val is None:
            return default
        elif isinstance(val, cabc.Iterable) or callable(val):
            result = self.eval_alias(
                val,
                seen_tokens={key},
                decorators=decorators,
                acc_args=args,
                env_out=returned_env,
            )
            if returned_env and result is not None:
                result = AliasReturnCommandResult(result, local_env=returned_env)
            return result
        else:
            msg = "alias of {!r} has an inappropriate type: {!r}"
            raise TypeError(msg.format(key, val))

    def get_doc(self, name: str) -> str:
        """Return the cleaned docstring of an alias.

        Resolution order:

        1. An explicit doc set via the dict-form
           ``aliases[k] = {"alias": ..., "doc": "..."}`` takes priority
           over everything else — it's the only way to attach a description
           to a list/string alias and an intentional override for callable
           aliases.
        2. For ``FuncAlias`` instances, the wrapped function's
           ``__doc__`` (read from ``alias.func`` directly to avoid falling
           back to ``FuncAlias.__doc__``, which would otherwise leak the
           class placeholder ``"Provides a callable alias for xonsh
           commands."``).
        3. For any other alias object (e.g. ``ArgParserAlias``,
           ``ExecAlias``), the object's own ``__doc__``.
        4. List- and string-aliases without an explicit doc yield ``""``.

        The returned string is run through :func:`inspect.cleandoc` so
        multi-line docstrings have shared indentation removed.
        """
        if name in self._docs:
            return inspect.cleandoc(self._docs[name])
        try:
            alias = self._raw[name]
        except KeyError:
            return ""
        func = getattr(alias, "func", None)
        if func is not None:
            doc = getattr(func, "__doc__", None)
        elif isinstance(alias, (list, str, ExecAlias)):
            # ``ExecAlias`` has a class docstring ("Provides an exec alias
            # for xonsh source code.") that would otherwise leak through as
            # the description for every plain string alias with shell
            # syntax — same pitfall as ``FuncAlias`` above. Treat it like
            # list/str: no implicit description.
            return ""
        else:
            doc = getattr(alias, "__doc__", None)
        return inspect.cleandoc(doc) if doc else ""

    def expand_alias(self, line: str, cursor_index: int) -> str:
        """Expands any aliases present in line if alias does not point to a
        builtin function and if alias is only a single command.
        The command won't be expanded if the cursor's inside/behind it.
        """
        word = (line.split(maxsplit=1) or [""])[0]
        if word in self and not callable(self.get(word)[0]):  # type: ignore
            word_idx = line.find(word)
            word_edge = word_idx + len(word)
            if cursor_index > word_edge:
                # the cursor isn't inside/behind the word
                expansion = " ".join(self.get(word))
                line = line[:word_idx] + expansion + line[word_edge:]
        return line

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self._raw[key]

    def __setitem__(self, key, val):
        # Dict-form: ``aliases[k] = {"alias": <value>, "doc": "..."}``.
        # Lets list/string aliases (which carry no ``__doc__``) advertise a
        # description for tab-completion and ``cmd?``. Also overrides the
        # ``__doc__`` of a function/FuncAlias when the user wants a
        # different one-line summary than the function's docstring.
        # Recognised keys: "alias" (required), "doc" (optional). Any other
        # keys are reserved for future use and currently ignored.
        explicit_doc: str | None = None
        if isinstance(val, dict) and "alias" in val:
            explicit_doc = val.get("doc") or None
            val = val["alias"]

        if isinstance(val, str):
            f = "<exec-alias:" + key + ">"
            if EXEC_ALIAS_RE.search(val) is not None:
                # We have a sub-command (e.g. $(cmd)) or IO redirect (e.g. >>)
                self._raw[key] = ExecAlias(val, filename=f)
            elif isexpression(val):
                # expansion substitution
                lexer = XSH.execer.parser.lexer
                self._raw[key] = list(map(strip_simple_quotes, lexer.split(val)))
            else:
                # need to exec alias
                self._raw[key] = ExecAlias(val, filename=f)
        elif isinstance(val, types.FunctionType):
            self._raw[key] = FuncAlias(key, val)
        else:
            self._raw[key] = val

        # Update the per-alias doc registry. Always clear first so a
        # rewrite without ``"doc"`` doesn't leave a stale description from
        # a prior dict-form assignment.
        self._docs.pop(key, None)
        if explicit_doc:
            self._docs[key] = explicit_doc

    def _common_or(self, other):
        new_dict = self._raw.copy()
        for key in dict(other):
            new_dict[key] = other[key]
        result = Aliases(new_dict)
        # ``Aliases(new_dict)`` re-feeds every entry through ``__setitem__``,
        # which clears any per-key doc — so docs that came from ``self._docs``
        # or from ``other._docs`` (when ``other`` is itself an ``Aliases``)
        # need to be re-applied here. Keys whose values came from ``other``
        # surrender their old doc unless ``other`` supplies a new one,
        # mirroring ``__ior__`` semantics.
        other_keys = set(dict(other))
        for key, doc in self._docs.items():
            if key not in other_keys:
                result._docs.setdefault(key, doc)
        if isinstance(other, Aliases):
            for key, doc in other._docs.items():
                result._docs[key] = doc
        return result

    def __or__(self, other):
        return self._common_or(other)

    def __ror__(self, other):
        return self._common_or(other)

    def __ior__(self, other):
        for key in dict(other):
            self[key] = other[key]
        # When ``other`` is an ``Aliases``, ``other[key]`` returns the raw
        # alias (FuncAlias / list / string) — its dict-form is gone, so any
        # docs in ``other._docs`` were not propagated through __setitem__.
        # Apply them now so an Aliases-to-Aliases merge keeps descriptions.
        if isinstance(other, Aliases):
            for key, doc in other._docs.items():
                self._docs[key] = doc
        return self

    def __delitem__(self, key):
        del self._raw[key]
        self._docs.pop(key, None)

    def update(self, *args, **kwargs):
        for key, val in dict(*args, **kwargs).items():
            self[key] = val

    def __iter__(self):
        yield from self._raw

    def __len__(self):
        return len(self._raw)

    def __str__(self):
        return str(self._raw)

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}({self._raw})"

    _repr_pretty_ = to_repr_pretty_


class ExecAlias:
    """Provides an exec alias for xonsh source code."""

    def __init__(self, src, filename="<exec-alias>"):
        """
        Parameters
        ----------
        src : str
            Source code that will be
        """
        self.src = src
        self.filename = filename

    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        execer = XSH.execer
        frame = stack[0][0]  # execute as though we are at the call site

        alias_args = {"args": args}
        for i, a in enumerate(args):
            alias_args[f"arg{i}"] = a

        thread_local = {}
        with XSH.env.swap(alias_args, __THREAD_LOCAL__=thread_local):
            execer.exec(
                self.src,
                glbs=frame.f_globals,
                locs=frame.f_locals,
                filename=self.filename,
            )
        return thread_local.get("returncode", 0)

    def __repr__(self):
        return f"ExecAlias({self.src!r}, filename={self.filename!r})"


ALIAS_PARAMS_DEFAULT = {
    "args": None,
    "stdin": None,
    "stdout": None,
    "stderr": None,
    "spec": None,
    "stack": None,
    "decorators": None,
    "alias_name": None,
    "called_alias_name": None,
    "env": None,
}
ALIAS_KWARG_NAMES = frozenset(ALIAS_PARAMS_DEFAULT)


def _click_command_alias(func_or_name=None, *, _aliases):
    """Decorator factory that registers a xonsh alias as a ``click`` command.

    Mirrors the calling conventions of :meth:`Aliases.register`:

    * ``@aliases.register_click_command`` — bare, derives alias name from
      the function name (leading underscore stripped, dash-cased).
    * ``@aliases.register_click_command()`` — empty parentheses, same as bare.
    * ``@aliases.register_click_command("custom-name")`` — explicit alias name.

    Inside the click callback, ``ctx`` is a :class:`click.Context` subclass
    carrying the usual xonsh alias params (``alias_args``, ``stdin``, ``stdout``,
    ``stderr``, etc from ALIAS_PARAMS_DEFAULT). The ``args`` alias param is exposed as
    ``ctx.alias_args`` to avoid clashing with ``click.Context.args``.

    Only available when the ``click`` package is installed; wired up by
    :meth:`Aliases._add_click_command` from :meth:`Aliases.__init__`.
    """
    import functools

    import click

    def _make_alias(func, alias_name=None):
        if isinstance(func, click.Command):
            cmd = func
            original_func = cmd.callback
            name_source = original_func if original_func else cmd.name
        else:
            original_func = func
            name_source = func
            params = list(inspect.signature(func).parameters)
            if not params or params[0] != "ctx":
                raise TypeError(
                    f"Click alias {func.__name__!r} must have 'ctx' as the "
                    f"first parameter."
                )
            cmd = click.command()(click.pass_context(func))

        class XonshContext(click.Context):
            def __init__(self, *args, xsh=None, **kwargs):
                super().__init__(*args, **kwargs)
                xsh = xsh or {}
                for key in ALIAS_PARAMS_DEFAULT:
                    # 'args' clashes with click.Context.args — rename.
                    attr = "alias_args" if key == "args" else key
                    setattr(self, attr, xsh.get(key))

        # Expose the click module itself so callbacks can use
        # ``ctx.click.echo(...)`` etc. without a separate import.
        # (Set after the class body — Python class-scope rules block
        # ``click = click`` inside the body from resolving the enclosing
        # function's name.)
        XonshContext.click = click

        cmd.context_class = XonshContext

        registered_name = get_alias_name(alias_name or name_source)

        def _wrapper(**xsh_data):
            try:
                cmd.main(
                    args=xsh_data.get("args"),
                    prog_name=xsh_data.get("called_alias_name") or registered_name,
                    standalone_mode=False,
                    xsh=xsh_data,
                )
            except click.exceptions.ClickException as e:
                e.show()
                return e.exit_code
            except click.exceptions.Abort:
                return 1
            return 0

        # Make _wrapper look like the original function to inspect.getsource
        # (so `cmd??` shows the user's click callback, not _wrapper).
        if callable(original_func):
            functools.update_wrapper(_wrapper, original_func)

        # Override the signature AFTER update_wrapper so run_alias_by_params
        # sees the ALIAS_PARAMS_DEFAULT params, not the original function's.
        _wrapper.__signature__ = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    pname, inspect.Parameter.KEYWORD_ONLY, default=default
                )
                for pname, default in ALIAS_PARAMS_DEFAULT.items()
            ]
        )

        # Tab-completion: ``complete_aliases`` picks this up via
        # ``alias.func.xonsh_complete``. Bound to the live click.Command so
        # the completer always reflects the current option/argument set —
        # even if the user mutates ``cmd.params`` after registration.
        from xonsh.completers.click import complete_click

        _wrapper.xonsh_complete = functools.partial(complete_click, cmd)

        _aliases.register(registered_name, dash_case=False)(_wrapper)
        return _wrapper

    # Direct use: @aliases.register_click_command (no parens)
    if callable(func_or_name):
        return _make_alias(func_or_name)

    # Parameterized use: @aliases.register_click_command() / (...)("name")
    def _decorator(func):
        return _make_alias(func, alias_name=func_or_name)

    return _decorator


class PartialEvalAlias:
    """Partially evaluated alias.

    Wraps a callable alias with accumulated arguments. The wrapped function's
    signature is inspected once at init time. At call time, arguments are
    matched by name (with positional fallback for unnamed parameters).
    """

    def __init__(self, f, acc_args=()):
        self.f = f
        self.acc_args = acc_args
        self.__name__ = getattr(f, "__name__", self.__class__.__name__)
        self._param_names = list(inspect.signature(f).parameters.keys())
        self._numargs = len(self._param_names)

    def __call__(
        self,
        args,
        stdin=None,
        stdout=None,
        stderr=None,
        spec=None,
        stack=None,
        alias_name=None,
        called_alias_name=None,
    ):
        args = list(self.acc_args) + args
        if self._numargs == 0:
            if args:
                msg = "callable alias {f!r} takes no arguments, but {args!r} provided. "
                msg += "Of these {acc_args!r} were partially applied."
                raise XonshError(
                    msg.format(f=self.f, args=args, acc_args=self.acc_args)
                )
            return self.f()
        available = ALIAS_PARAMS_DEFAULT.copy()
        available.update(
            args=args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            spec=spec,
            stack=stack,
            alias_name=getattr(self.f, "__alias_name__", alias_name),
            called_alias_name=called_alias_name,
        )
        kwargs = {n: available[n] for n in self._param_names if n in available}
        if len(kwargs) != self._numargs:
            # Positional fallback for unnamed params
            kwargs = dict(zip(self._param_names, available.values(), strict=False))
        return self.f(**kwargs)

    def __repr__(self):
        return f"PartialEvalAlias({self.f!r}, acc_args={self.acc_args!r})"


def partial_eval_alias(f, acc_args=()):
    """Wraps a callable alias with accumulated arguments."""
    if not acc_args:
        return f
    return PartialEvalAlias(f, acc_args=acc_args)


def run_alias_by_params(func: tp.Callable, params: dict[str, tp.Any]):
    """
    Run alias function based on signature and params.
    If function param names are in alias signature fill them.
    If function params have unknown names fill using alias signature order.
    """
    alias_params = ALIAS_PARAMS_DEFAULT.copy()
    alias_params |= params
    sign = inspect.signature(func)
    func_params = sign.parameters.items()
    kwargs = {
        name: alias_params[name] for name, p in func_params if name in alias_params
    }

    if len(kwargs) != len(func_params):
        # There is unknown param. Switch to positional mode.
        kwargs = dict(
            zip(
                map(operator.itemgetter(0), func_params),
                alias_params.values(),
                strict=False,
            )
        )
    return func(**kwargs)


#
# Actual aliases below
#


def xonsh_exit(args, stdin=None):
    """Sends signal to exit shell."""
    if not clean_jobs():
        # Do not exit if jobs not cleaned up
        return None, None
    if args:
        try:
            code = int(args[0])
        except ValueError:
            code = 1
    else:
        code = 0
    XSH.exit = code
    return None, None


def xonsh_reset(args, stdin=None):
    """Clears __xonsh__.ctx"""
    XSH.ctx.clear()


def source_foreign_fn(
    shell: str,
    files_or_code: Annotated[list[str], Arg(nargs="+")],
    interactive=False,
    login=False,
    envcmd=None,
    aliascmd=None,
    extra_args="",
    safe=True,
    prevcmd="",
    postcmd="",
    funcscmd="",
    sourcer=None,
    use_tmpfile=False,
    seterrprevcmd=None,
    seterrpostcmd=None,
    overwrite_aliases=False,
    suppress_skip_message=False,
    show=False,
    show_output=False,
    dryrun=False,
    _stderr=None,
):
    """Sources a file written in a foreign shell language.

    Parameters
    ----------
    shell
        Name or path to the foreign shell
    files_or_code
        file paths to source or code in the target language.
    interactive : -i, --interactive
        whether the sourced shell should be interactive
    login : -l, --login
        whether the sourced shell should be login
    envcmd : --envcmd
        command to print environment
    aliascmd : --aliascmd
        command to print aliases
    extra_args : --extra-args
        extra arguments needed to run the shell
    safe : -u, --unsafe
        whether the source shell should be run safely, and not raise any errors, even if they occur.
    prevcmd : -p, --prevcmd
        command(s) to run before any other commands, replaces traditional source.
    postcmd : --postcmd
        command(s) to run after all other commands
    funcscmd : --funcscmd
        code to find locations of all native functions in the shell language.
    sourcer : --sourcer
        the source command in the target shell language.
        If this is not set, a default value will attempt to be
        looked up based on the shell name.
    use_tmpfile : --use-tmpfile
        whether the commands for source shell should be written to a temporary file.
    seterrprevcmd : --seterrprevcmd
        command(s) to set exit-on-error before any other commands.
    seterrpostcmd : --seterrpostcmd
        command(s) to set exit-on-error after all other commands.
    overwrite_aliases : --overwrite-aliases
        flag for whether or not sourced aliases should replace the current xonsh aliases.
    suppress_skip_message : --suppress-skip-message
        flag for whether or not skip messages should be suppressed.
    show : --show
        show the generated shell command that will be sent to the foreign
        shell (does not show what the sourced script prints — see
        ``--show-output`` for that).
    show_output : --show-output
        forward stdout and stderr produced by the sourced script to the
        xonsh terminal. By default they are silently discarded.
    dryrun : -d, --dry-run
        Will not actually source the file.
    """
    extra_args = tuple(extra_args.split())
    env = XSH.env
    suppress_skip_message = (
        env.get("FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE")
        if not suppress_skip_message
        else suppress_skip_message
    )
    files: tuple[str, ...] = ()
    if prevcmd:
        pass  # don't change prevcmd if given explicitly
    elif os.path.isfile(files_or_code[0]):
        if not sourcer:
            return (None, "xonsh: error: `sourcer` command is not mentioned.\n", 1)
        # we have filenames to source
        shell_name = os.path.basename(shell).lower()
        quote = (
            functools.partial(argvquote, force=True)
            if shell_name in {"cmd", "cmd.exe"}
            else shlex.quote
        )
        prevcmd = "".join(f"{sourcer} {quote(f)}\n" for f in files_or_code)
        files = tuple(files_or_code)
    elif not prevcmd:
        prevcmd = " ".join(files_or_code)  # code to run, no files
    foreign_shell_data.cache_clear()  # make sure that we don't get prev src
    fsenv, fsaliases = foreign_shell_data(
        shell=shell,
        login=login,
        interactive=interactive,
        envcmd=envcmd,
        aliascmd=aliascmd,
        extra_args=extra_args,
        safe=safe,
        prevcmd=prevcmd,
        postcmd=postcmd,
        funcscmd=funcscmd or None,  # the default is None in the called function
        sourcer=sourcer,
        use_tmpfile=use_tmpfile,
        seterrprevcmd=seterrprevcmd,
        seterrpostcmd=seterrpostcmd,
        show=show,
        show_output=show_output,
        dryrun=dryrun,
        files=files,
    )
    if fsenv is None:
        if dryrun:
            return
        else:
            msg = f"xonsh: error: Source failed: {prevcmd!r}\n"
            msg += "xonsh: error: Possible reasons: File not found or syntax error\n"
            return (None, msg, 1)
    # apply results
    denv = env.detype()
    for k, v in fsenv.items():
        if k == "SHLVL":  # ignore $SHLVL as sourcing should not change $SHLVL
            continue
        if k in denv and v == denv[k]:
            continue  # no change from original
        env[k] = v
    # Remove any env-vars that were unset by the script.
    for k in denv:
        if k not in fsenv:
            env.pop(k, None)
    # Update aliases
    baliases = XSH.aliases
    for k, v in fsaliases.items():
        if k in baliases and v == baliases[k]:
            continue  # no change from original
        elif overwrite_aliases or k not in baliases:
            baliases[k] = v
        elif suppress_skip_message:
            pass
        else:
            msg = (
                "Skipping application of {0!r} alias from {1!r} "
                "since it shares a name with an existing xonsh alias. "
                'Use "--overwrite-alias" option to apply it anyway. '
                'You may prevent this message with "--suppress-skip-message" or '
                '"$FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE = True".'
            )
            print(msg.format(k, shell), file=_stderr)


class SourceForeignAlias(ArgParserAlias):
    def build(self):
        parser = self.create_parser(**self.kwargs)
        # for backwards compatibility
        parser.add_argument(
            "-n",
            "--non-interactive",
            action="store_false",
            dest="interactive",
            help="Deprecated: The default mode runs in non-interactive mode.",
        )
        return parser


source_foreign = SourceForeignAlias(
    func=source_foreign_fn, has_args=True, prog="source-foreign"
)


def source_alias_fn(
    files: Annotated[list[str], Arg(nargs="+")], ignore_ext=False, _stdin=None
):
    """Executes the contents of the provided files in the current context.
    If sourced file isn't found in cwd, search for file along $PATH to source
    instead.

    Parameters
    ----------
    files
        paths to source files.
    ignore_ext : -e, --ignore-ext
        don't check the file extension
    """
    env = XSH.env
    encoding = env.get("XONSH_ENCODING")
    errors = env.get("XONSH_ENCODING_ERRORS")
    for i, fname in enumerate(files):
        fpath = fname
        if not os.path.isfile(fpath):
            fpath = locate_file(fname)
            if fpath is None:
                if env.get("XONSH_DEBUG"):
                    print(f"source: {fname!r}: No such file", file=sys.stderr)
                if i == 0:
                    raise RuntimeError(
                        f"must source at least one file, {fname!r} does not exist."
                    )
                break
        _, fext = os.path.splitext(fpath)
        fext, name = Path(fpath).suffix, Path(fpath).name
        if not fext and name.startswith("."):
            fext = name  # hidden file with no extension
        if not ignore_ext and fext not in {".xsh", ".py", ".xonshrc"}:
            raise RuntimeError(
                f"Attempting to source file with non-xonsh extension {name!r}! "
                f"If you are trying to source a file in another language, "
                "then please use the appropriate source command "
                "e.g. `source-bash script.sh`. "
                "Use `-e` to ignore extension checking and source the file."
            )
        with open(fpath, encoding=encoding, errors=errors) as fp:
            src = fp.read()
        if not src.endswith("\n"):
            src += "\n"
        ctx = XSH.ctx
        updates = {"__file__": fpath, "__name__": os.path.abspath(fpath)}
        with (
            env.swap(XONSH_MODE="source", **make_args_env(files[i + 1 :])),
            swap_values(ctx, updates),
        ):
            try:
                XSH.builtins.execx(src, "exec", ctx, filename=fpath)
            except SyntaxError:
                print_color(
                    "You may be attempting to source non-xonsh file: "
                    f"{fpath!r}. "
                    "If you are trying to source a file in "
                    "another language, then please use the appropriate "
                    "source command. For example, `source-bash "
                    "script.sh`.",
                    file=sys.stderr,
                )
                raise


source_alias = ArgParserAlias(
    func=source_alias_fn, has_args=True, prog="source", threadable=False
)


def source_cmd_fn(
    files: Annotated[list[str], Arg(nargs="+")],
    login=False,
    aliascmd=None,
    extra_args="",
    safe=True,
    postcmd="",
    funcscmd="",
    seterrprevcmd=None,
    overwrite_aliases=False,
    suppress_skip_message=False,
    show=False,
    show_output=False,
    dryrun=False,
    _stderr=None,
):
    """
        Source cmd.exe files

    Parameters
    ----------
    files
        paths to source files.
    login : -l, --login
        whether the sourced shell should be login
    envcmd : --envcmd
        command to print environment
    aliascmd : --aliascmd
        command to print aliases
    extra_args : --extra-args
        extra arguments needed to run the shell
    safe : -s, --safe
        whether the source shell should be run safely, and not raise any errors, even if they occur.
    postcmd : --postcmd
        command(s) to run after all other commands
    funcscmd : --funcscmd
        code to find locations of all native functions in the shell language.
    seterrprevcmd : --seterrprevcmd
        command(s) to set exit-on-error before any other commands.
    overwrite_aliases : --overwrite-aliases
        flag for whether or not sourced aliases should replace the current xonsh aliases.
    suppress_skip_message : --suppress-skip-message
        flag for whether or not skip messages should be suppressed.
    show : --show
        show the generated shell command that will be sent to cmd.exe
        (does not show what the sourced script prints — see
        ``--show-output`` for that).
    show_output : --show-output
        forward stdout and stderr produced by the sourced script to the
        xonsh terminal. By default they are silently discarded.
    dryrun : -d, --dry-run
        Will not actually source the file.
    """
    args = list(files)
    fpath = locate_binary(args[0])
    args[0] = fpath if fpath else args[0]
    if not os.path.isfile(args[0]):
        return (None, f"xonsh: error: File not found: {args[0]}\n", 1)
    prevcmd = "call "
    prevcmd += " ".join([argvquote(arg, force=True) for arg in args])
    prevcmd = escape_windows_cmd_string(prevcmd)
    with XSH.env.swap(PROMPT="$P$G"):
        return source_foreign_fn(
            shell="cmd",
            files_or_code=args,
            interactive=True,
            sourcer="call",
            envcmd="set",
            seterrpostcmd="if errorlevel 1 exit 1",
            use_tmpfile=True,
            prevcmd=prevcmd,
            #     from this function
            login=login,
            aliascmd=aliascmd,
            extra_args=extra_args,
            safe=safe,
            postcmd=postcmd,
            funcscmd=funcscmd,
            seterrprevcmd=seterrprevcmd,
            overwrite_aliases=overwrite_aliases,
            suppress_skip_message=suppress_skip_message,
            show=show,
            show_output=show_output,
            dryrun=dryrun,
        )


source_cmd = ArgParserAlias(func=source_cmd_fn, has_args=True, prog="source-cmd")


def xexec_fn(
    command: Annotated[list[str], Arg(nargs=argparse.REMAINDER)],
    login=False,
    clean=False,
    name="",
    _stdin=None,
):
    """exec (also aliased as xexec) uses the os.execvpe() function to
    replace the xonsh process with the specified program.

    This provides the functionality of the bash 'exec' builtin::

        >>> exec bash -l -i
        bash $

    Parameters
    ----------
    command
        program to launch along its arguments
    login : -l, --login
        the shell places a dash at the
        beginning of the zeroth argument passed to command to simulate login
        shell.
    clean : -c, --clean
        causes command to be executed with an empty environment.
    name : -a, --name
        the shell passes name as the zeroth argument
        to the executed command.

    Notes
    -----
    This command **is not** the same as the Python builtin function
    exec(). That function is for running Python code. This command,
    which shares the same name as the sh-lang statement, is for launching
    a command directly in the same process. In the event of a name conflict,
    please use the xexec command directly or dive into subprocess mode
    explicitly with ![exec command]. For more details, please see
    http://xon.sh/faq.html#exec.
    """
    if len(command) == 0:
        return (None, "xonsh: exec: no command specified\n", 1)

    cmd = command[0]
    if name:
        command[0] = name
    if login:
        command[0] = f"-{command[0]}"

    denv = {}
    if not clean:
        denv = XSH.env.detype()

        # decrement $SHLVL to mirror bash's behaviour
        if "SHLVL" in denv:
            old_shlvl = to_shlvl(denv["SHLVL"])
            denv["SHLVL"] = str(adjust_shlvl(old_shlvl, -1))

    # Clear the alias stack so the new process doesn't falsely detect
    # recursion.  exec replaces the process — there is no actual recursion.
    # (https://github.com/xonsh/xonsh/pull/6198)
    denv.pop("__ALIAS_STACK", None)
    denv.pop("__ALIAS_NAME", None)

    try:
        os.execvpe(cmd, command, denv)
    except OSError as e:
        if e.errno == 8:  # Exec format error — not a binary, try shebang
            from xonsh.procs.specs import get_script_subproc_command

            try:
                scriptcmd = get_script_subproc_command(cmd, command[1:])
            except PermissionError:
                scriptcmd = None
            if scriptcmd:
                os.execvpe(scriptcmd[0], scriptcmd, denv)
            # fall through to the error return below
        if e.errno == 2:  # FileNotFoundError
            return (
                None,
                f"xonsh: exec: file not found: {e.args[1]}: {command[0]}\n",
                1,
            )
        return (
            None,
            f"xonsh: exec: {e.args[1]}: {command[0]}\n",
            1,
        )


xexec = ArgParserAlias(func=xexec_fn, has_args=True, prog="xexec")


@lazyobject
def xonfig():
    """Runs the xonsh configuration utility."""
    from xonsh.xonfig import xonfig_main  # lazy import

    return xonfig_main


@unthreadable
def trace(args, stdin=None, stdout=None, stderr=None, spec=None):
    """Runs the xonsh tracer utility."""
    from xonsh.tracer import tracermain  # lazy import

    try:
        return tracermain(args, stdin=stdin, stdout=stdout, stderr=stderr, spec=spec)
    except SystemExit:
        pass


def showcmd(args, stdin=None):
    """usage: showcmd [-e|--expand-alias] [-h|--help] cmd

    Displays the command and arguments as a list of strings that xonsh would
    run in subprocess mode. This is useful for determining how xonsh evaluates
    your commands and arguments prior to running these commands.

    optional arguments:
      -e, --expand-alias    expand alias
      -h, --help            show this help message and exit

    Examples
    --------
      @ showcmd echo $USER "can't" hear "the sea"
      ['echo', 'I', "can't", 'hear', 'the sea']

      @ aliases['ali'] = 'echo 1'
      @ showcmd -e ali 2
      ['echo', '1', '2']

    """
    if len(args) == 0 or (len(args) == 1 and args[0] in {"-h", "--help"}):
        print(showcmd.__doc__.rstrip().replace("\n    ", "\n"))
    elif args[0] in {"-e", "--expand-alias"}:
        sys.displayhook(XSH.aliases.eval_alias(args[1:]))
    else:
        sys.displayhook(args)


def get_xxonsh_alias():
    """
    Determine the correct invocation to launch xonsh the same way the
    current session was launched.

    Always returns a list, so the result can be concatenated with other
    argv lists (e.g. ``['tmux', 'new-session'] + get_xxonsh_alias()``).

    For an entry-point launch (e.g. ``/usr/local/bin/xonsh``) the value of
    ``sys.argv[0]`` is already a runnable absolute path, so the result is
    a single-element list.

    For a "from source" launch via ``python -m xonsh`` (``sys.argv[0]``
    basename is ``__main__.py``) a naive ``[sys.executable, "-m", "xonsh"]``
    would be CWD-dependent: ``python -m xonsh`` resolves the package via
    ``sys.path``, which has the *current* working directory at position 0.
    Running ``xxonsh`` from outside the source repo would silently pick
    whatever ``import xonsh`` resolves to in ``site-packages`` (or raise
    ``ModuleNotFoundError``), which is almost never what the user wants.

    Instead, compute the parent directory of the source ``xonsh`` package
    once (from the absolute path of ``__main__.py``) and spawn Python with
    a ``-c`` bootstrap that prepends that directory to ``sys.path`` before
    importing ``xonsh.main``. This makes the alias resolve to the same
    source tree from any CWD, regardless of what is installed in
    ``site-packages``.
    """
    # Local import: xonsh.main pulls in heavy modules (shell, execer,
    # xontribs), so keep the dependency lazy.
    from xonsh.main import get_current_xonsh

    current_xonsh = get_current_xonsh()
    if os.path.basename(current_xonsh) != "__main__.py":
        # Entry-point case: sys.argv[0] is an absolute path to the xonsh
        # launcher and is already runnable as-is.
        return [current_xonsh]

    # Source case: __main__.py lives inside the xonsh/ package, whose
    # parent directory is the one we need on sys.path for
    # ``from xonsh.main import main`` to pick up the source version.
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(current_xonsh)))
    bootstrap = (
        f"import sys; sys.path.insert(0, {pkg_parent!r}); "
        f"from xonsh.main import main; main()"
    )
    return [sys.executable, "-c", bootstrap]


def get_xpip_alias():
    """
    Determines the correct invocation to get xonsh's pip
    """
    if not getattr(sys, "executable", None):
        return lambda args, stdin=None: (
            "",
            "Sorry, unable to run pip on your system (missing sys.executable)",
            1,
        )

    basecmd = [sys.executable, "-m", "pip"]
    try:
        if ON_WINDOWS:
            # XXX: Does windows have an installation mode that requires UAC?
            return basecmd
        elif IN_APPIMAGE:
            # In AppImage `sys.executable` is equal to path to xonsh.AppImage file and the real python executable is in $_
            return [
                XSH.env.get("_", "APPIMAGE_PYTHON_EXECUTABLE_NOT_FOUND"),
                "-m",
                "pip",
            ]
        elif not os.access(os.path.dirname(sys.executable), os.W_OK):
            import site

            pydir = os.path.dirname(sys.executable)

            @Aliases.return_command
            def _xpip_user(args):
                if args and args[0] == "install":
                    return basecmd + ["install", "--user"] + args[1:]
                else:
                    return basecmd + args

            _xpip_user.__doc__ = (
                f"Normally ``xpip`` runs ``{' '.join(basecmd)}``, but in this "
                "session it is a wrapper that adds ``--user`` to ``pip install`` "
                "commands.\n"
                "\n"
                "Created during startup because the directory containing the "
                f"Python executable (``{pydir}``) is not writable by the current "
                "user. This typically means Python is installed system-wide, so "
                "``pip install`` without ``--user`` would require root privileges. "
                "The ``--user`` flag tells pip to install packages into the "
                f"per-user site-packages directory (``{site.getusersitepackages()}``)."
            )
            return _xpip_user
        else:
            return basecmd
    except Exception:
        # Something freaky happened, return something that'll probably work
        return basecmd


def _find_cmd_exe() -> str:
    """
    Resolve the cmd.exe executable.

    Avoids using COMSPEC in order to allow COMSPEC to be used to
    indicate Xonsh (or other shell) as the default shell. (#5701)
    """
    canonical = pathlib.Path(os.environ["SystemRoot"], "System32", "cmd.exe")
    return str(canonical) if canonical.is_file() else os.environ["COMSPEC"]


WINDOWS_CMD_ALIASES = frozenset(
    {
        "cls",
        "copy",
        "del",
        "dir",
        "echo",
        "erase",
        "md",
        "mkdir",
        "mklink",
        "move",
        "rd",
        "ren",
        "rename",
        "rmdir",
        "time",
        "type",
        "vol",
    }
)
"""Built-in commands of ``cmd.exe`` that xonsh borrows on Windows."""


def win_sudo(args):
    """Run a command with Windows UAC elevation.

    Registered as the ``sudo`` alias on Windows only when no ``sudo`` binary
    is found on ``$PATH`` (see issue #5706). Resolves the target via
    :func:`xonsh.environ.locate_binary` and re-launches it through
    ``ShellExecuteEx`` with the ``runas`` verb; ``cmd.exe`` built-ins
    (``dir``, ``copy``, ...) are dispatched via ``cmd /D /C`` from the
    current working directory. The elevated process opens in a new console
    and does not inherit standard streams, so its output is not piped back.
    """
    import xonsh.platforms.winutils as winutils

    if not args:
        return ("", "sudo: missing executable to run as Administrator\n", 1)
    cmd = args[0]
    if (resolved := locate_binary(cmd)) is not None:
        return winutils.sudo(os.path.normpath(resolved), args[1:])
    elif cmd.lower() in WINDOWS_CMD_ALIASES:
        cmd_args = ["/D", "/C", "CD", _get_cwd(), "&&"] + args
        return winutils.sudo(_find_cmd_exe(), cmd_args)
    else:
        return ("", f'sudo: cannot find executable "{cmd}"\n', 127)


def _output_to_path_object(lines):
    """Transform first output line into single path. Return None if the output is empty."""
    if lines and (path_str := lines[0].strip()):
        return XSH.imp.pathlib.Path(path_str)
    else:
        return None


def _output_to_path_objects(lines):
    """Transform lines output into list of path objects. Skip empty lines."""
    if lines:
        return [XSH.imp.pathlib.Path(line.strip()) for line in lines if line.strip()]
    else:
        return None


def make_default_aliases():
    """Creates a new default aliases dictionary."""
    default_aliases = {
        "cd": cd,
        "completer": xca.completer_alias,
        "pushd": pushd,
        "popd": popd,
        "dirs": dirs,
        "jobs": jobs,
        "fg": fg,
        "bg": bg,
        "disown": disown,
        "EOF": xonsh_exit,
        "exit": xonsh_exit,
        "quit": xonsh_exit,
        "exec": xexec,
        "xexec": xexec,
        "source": source_alias,
        "source-zsh": SourceForeignAlias(
            func=functools.partial(source_foreign_fn, "zsh", sourcer="source"),
            has_args=True,
            prog="source-zsh",
        ),
        "source-bash": SourceForeignAlias(
            func=functools.partial(source_foreign_fn, "bash", sourcer="source"),
            has_args=True,
            prog="source-bash",
        ),
        "source-cmd": source_cmd,
        "source-foreign": source_foreign,
        "history": xhm.history_main,
        "trace": trace,
        "timeit": timeit_alias,
        "xonfig": xonfig,
        "showcmd": showcmd,
        "which": xxw.which,
        "xcontext": xxt.xcontext,
        "xontrib": xontribs_main,
        "xxonsh": get_xxonsh_alias(),
        "xpip": get_xpip_alias(),
        "xpython": [XSH.env.get("_", sys.executable)]
        if IN_APPIMAGE
        else [sys.executable],
        "xreset": xonsh_reset,
        # Command decorators
        "@error_raise": SpecAttrDecoratorAlias(
            {"raise_subproc_error": True},
            "Command decorator. Raise an exception if the command returns a non-zero exit code.",
        ),
        "@error_ignore": SpecAttrDecoratorAlias(
            {"raise_subproc_error": False},
            "Command decorator. Do not raise an exception if the command returns a non-zero exit code.",
        ),
        "@thread": SpecAttrDecoratorAlias(
            {"threadable": True, "force_threadable": True},
            "Command decorator. Mark current command as threadable.",
        ),
        "@unthread": SpecAttrDecoratorAlias(
            {"threadable": False, "force_threadable": False},
            "Command decorator. Mark current command as unthreadable.",
        ),
        "@lines": SpecAttrDecoratorAlias(
            {"output_format": "list_lines"},
            "Command decorator. Return output as list of lines.",
        ),
        "@path": SpecAttrDecoratorAlias(
            {"output_format": _output_to_path_object},
            "Command decorator. Return Path object for the first line in output.",
        ),
        "@paths": SpecAttrDecoratorAlias(
            {"output_format": _output_to_path_objects},
            "Command decorator. Return Path objects for the lines in output.",
        ),
        "@json": SpecAttrDecoratorAlias(
            {"output_format": lambda lines: XSH.imp.json.loads("\n".join(lines))},
            "Command decorator. Parses JSON and returns JSON object.",
        ),
        "@jsonl": SpecAttrDecoratorAlias(
            {"output_format": lambda lines: [XSH.imp.json.loads(lj) for lj in lines]},
            "Command decorator. Parses JSON strings and returns list of JSON objects.",
        ),
        "@yaml": SpecAttrDecoratorAlias(
            {"output_format": lambda lines: XSH.imp.yaml.safe_load("\n".join(lines))},
            "Command decorator. Parses YAML and returns dict.",
        ),
        "@xml": SpecAttrDecoratorAlias(
            {
                "output_format": lambda lines: __import__(
                    "xml.etree.ElementTree", fromlist=["fromstring"]
                ).fromstring("\n".join(lines))
            },
            "Command decorator. Parses XML and returns ElementTree Element.",
        ),
    }
    if ON_WINDOWS:
        # Borrow builtin commands from cmd.exe.
        for alias in WINDOWS_CMD_ALIASES:
            default_aliases[alias] = [_find_cmd_exe(), "/c", alias]
        default_aliases["call"] = ["source-cmd"]
        default_aliases["source-bat"] = ["source-cmd"]
        default_aliases["clear"] = "cls"
        if ON_ANACONDA or shutil.which("conda", path=XSH.env.get_detyped("PATH")):
            # ON_ANACONDA only fires when xonsh itself is installed inside the
            # conda env (sys.prefix has conda-meta/). Pip-installed xonsh +
            # standalone Miniconda3 leaves it False, so also probe $PATH for
            # a `conda` launcher to give those users a working fallback while
            # `conda init xonsh` on Windows is broken — see xonsh/xonsh#3676.
            default_aliases["activate"] = ["source-cmd", "activate.bat"]
            default_aliases["deactivate"] = ["source-cmd", "deactivate.bat"]
        if not shutil.which("sudo", path=XSH.env.get_detyped("PATH")):
            default_aliases["sudo"] = win_sudo
    elif ON_DARWIN:
        default_aliases["ls"] = ["ls", "-G"]
    elif ON_FREEBSD or ON_DRAGONFLY:
        default_aliases["grep"] = ["grep", "--color=auto"]
        default_aliases["egrep"] = ["egrep", "--color=auto"]
        default_aliases["fgrep"] = ["fgrep", "--color=auto"]
        default_aliases["ls"] = ["ls", "-G"]
    elif ON_NETBSD:
        default_aliases["grep"] = ["grep", "--color=auto"]
        default_aliases["egrep"] = ["egrep", "--color=auto"]
        default_aliases["fgrep"] = ["fgrep", "--color=auto"]
    elif ON_OPENBSD:
        pass
    else:
        default_aliases["grep"] = ["grep", "--color=auto"]
        default_aliases["egrep"] = ["egrep", "--color=auto"]
        default_aliases["fgrep"] = ["fgrep", "--color=auto"]
        default_aliases["ls"] = ["ls", "--color=auto", "-v"]
    return default_aliases
