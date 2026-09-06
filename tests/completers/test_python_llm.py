"""Regression coverage for ``xonsh/completers/python.py``.

For an unknown command, the Python completer splits ``--home=/`` on ``=`` and
used to offer operator tokens (``/`` ``//`` ``/=`` ``//=``) for the trailing
``/``.  Being exclusive and running before the path completer, those tokens
shadowed path completion.  A value that begins with a path separator must not
get operator completions, so the path completer can list the directory.

The command context can also interpret the first quoted string in a Python
membership expression as a command name. Command-cache suppression must use
the raw token so quoted Python literals remain distinct from actual commands.
"""

import os

import pytest

from xonsh.completers.python import complete_python
from xonsh.pytest.tools import skip_if_on_windows


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer):
    return xonsh_execer


def _values(result):
    if not result:
        return set()
    comps = result[0] if isinstance(result, tuple) else result
    return {str(c).strip() for c in comps}


@pytest.mark.parametrize("alias_name", ["less", "more", "dir"])
@pytest.mark.parametrize("quote", ['"', "'"])
def test_python_completion_after_quoted_alias_membership(
    alias_name, quote, xession, completion_context_parse
):
    """Quoted alias names must not make Python expressions look like commands."""
    xession.commands_cache.aliases[alias_name] = "echo"
    xession.ctx["aliases"] = xession.commands_cache.aliases
    line = f"{quote}{alias_name}{quote} in ali"

    context = completion_context_parse(line, len(line))
    result = complete_python(context)

    assert "aliases" in _values(result)


def test_python_completion_still_skips_real_alias_command(
    xession, completion_context_parse
):
    """An unquoted alias in command position must retain command suppression."""
    xession.commands_cache.aliases["less"] = "echo"
    xession.ctx["aliases"] = xession.commands_cache.aliases
    line = "less ali"

    result = complete_python(completion_context_parse(line, len(line)))

    assert result is None


@pytest.mark.parametrize(
    "line",
    ["qwewqe --home=/", "qwewqe if=/", "qwewqe --home=~"],
    ids=["dashed-opt", "bare-opt", "tilde"],
)
def test_python_skips_operators_for_path_value(line, completion_context_parse):
    """A path value after ``=`` must not yield Python operator tokens."""
    res = complete_python(completion_context_parse(line, len(line)))
    # tokens that collide with a leading '/' or '~'
    assert _values(res) & {"/", "//", "/=", "//=", "~"} == set()


@pytest.mark.parametrize("line", ["5 /", "x = /"])
def test_python_keeps_operators_for_real_expression(line, completion_context_parse):
    """Genuine operator completion (``/`` from an expression) is preserved.

    Here ``/`` is the whole prefix (from the space split), so the first
    completion attempt already matches operators and the ``=`` fallback that
    the fix guards is never reached.
    """
    res = complete_python(completion_context_parse(line, len(line)))
    assert {"/", "//", "/=", "//="} <= _values(res)


@skip_if_on_windows
def test_path_completion_not_shadowed_end_to_end(completer_obj):
    """Full pipeline: ``app --home=/<TAB>`` yields paths, not ``/=``."""
    line = "qwewqe --home=/"
    comps, lprefix = completer_obj.complete_line(line)
    vals = {str(c).rstrip() for c in comps}

    # operator tokens no longer shadow the path completer ...
    assert not (vals & {"/", "//", "/=", "//="})
    # ... and the root directory is listed, replacing only the typed '/'.
    assert lprefix == 1
    assert vals, "expected root path completions"
    assert all(v.startswith("/") for v in vals)
    assert any(v.endswith(os.sep) for v in vals)
