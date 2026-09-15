"""A quoted first token is a string literal, not a command name.

Xonsh has no implicit subprocess form that starts with a quote -- ``"ls" -l``
is a syntax error -- so a line like ``"less" in aliases`` is Python, and the
completers that resolve "which executable does this line run" must not read it
as an invocation of ``less``.  They all ask that question through
``CommandContext.command_name``, which answers ``None`` for such a line while
still resolving the shell quoting that *is* meaningful inside an explicit
subprocess block (``![ "/opt/my prog" --help ]``).

Covers ``CommandContext.command_name`` itself and its four callers: the python,
import, man-page and alias completers.
"""

import pytest

from xonsh.completers._aliases import complete_aliases
from xonsh.completers.imports import complete_import
from xonsh.completers.man import complete_from_man
from xonsh.completers.python import complete_python
from xonsh.parsers.completion_context import CommandArg, CommandContext
from xonsh.pytest.tools import skip_if_on_windows

# every way of opening a string literal the lexer reports as a quote
QUOTES = ['"', "'", 'r"', 'f"', 'b"', 'rb"', '"""', "'''"]


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer):
    return xonsh_execer


def _values(result):
    """Flatten a completer result into a set of strings."""
    if not result:
        return set()
    comps = result[0] if isinstance(result, tuple) else result
    return {str(c).strip() for c in comps}


#
# CommandContext.command_name
#


def test_command_name_is_the_unquoted_first_arg():
    ctx = CommandContext(args=(CommandArg("git"), CommandArg("log")), arg_index=2)
    assert ctx.command_name == "git"


def test_command_name_is_none_without_args():
    assert CommandContext(args=(), arg_index=0).command_name is None


@pytest.mark.parametrize("quote", QUOTES)
def test_command_name_is_none_for_a_quoted_first_arg(quote):
    closing = quote.lstrip("rbf")
    ctx = CommandContext(
        args=(CommandArg("less", quote, closing), CommandArg("in")), arg_index=2
    )
    assert ctx.command_name is None


@pytest.mark.parametrize("first", ["/bin/ls", "bin/ls", "C:\\bin\\ls.exe"])
def test_command_name_keeps_a_path_untouched(first):
    """Resolving a path to its command is ``CommandsCache``'s job, not ours."""
    ctx = CommandContext(args=(CommandArg(first), CommandArg("-l")), arg_index=2)
    assert ctx.command_name == first


@pytest.mark.parametrize("subcmd_opening", ["![", "$[", "$(", "!("])
def test_command_name_keeps_quoting_inside_a_subproc_block(subcmd_opening):
    """``![ "/opt/my prog" -x ]`` really does name a command."""
    ctx = CommandContext(
        args=(CommandArg("/opt/my prog", '"', '"'),),
        arg_index=1,
        subcmd_opening=subcmd_opening,
    )
    assert ctx.command_name == "/opt/my prog"


@pytest.mark.parametrize("quote", ['"', "'", 'r"', 'f"'])
def test_command_name_from_a_parsed_line(quote, completion_context_parse):
    closing = quote.lstrip("rbf")
    line = f"{quote}less{closing} in ali"
    assert completion_context_parse(line, len(line)).command.command_name is None

    line = "less in ali"
    assert completion_context_parse(line, len(line)).command.command_name == "less"


#
# complete_python -- the reported bug, xonsh/xonsh#5285
#


@pytest.fixture
def aliased(xession):
    """Register ``less`` as an alias and expose ``aliases`` to python."""
    xession.commands_cache.aliases["less"] = "echo"
    xession.ctx["aliases"] = xession.commands_cache.aliases
    return xession


@pytest.mark.parametrize("quote", ['"', "'", 'r"', 'f"', 'b"', 'rb"', '"""'])
@pytest.mark.parametrize("op", ["in", "not in", "=="])
def test_python_completes_after_a_quoted_command_name(
    quote, op, aliased, completion_context_parse
):
    """``"less" in ali<TAB>`` must complete ``aliases``."""
    closing = quote.lstrip("rbf")
    line = f"{quote}less{closing} {op} ali"
    result = complete_python(completion_context_parse(line, len(line)))
    assert "aliases" in _values(result)


@pytest.mark.parametrize("line", ["less ali", "less -x ali"])
def test_python_still_skips_a_real_command_line(
    line, aliased, completion_context_parse
):
    """An unquoted command keeps suppressing python completion."""
    assert complete_python(completion_context_parse(line, len(line))) is None


def test_python_completion_after_quoted_command_end_to_end(aliased, completer_obj):
    """Full pipeline: ``"less" in ali<TAB>`` offers ``aliases``, not paths."""
    line = '"less" in ali'
    comps, _ = completer_obj.complete_line(line)
    assert "aliases" in {str(c).strip() for c in comps}


#
# complete_import
#


@pytest.mark.parametrize("keyword", ["from", "import"])
@pytest.mark.parametrize("quote", ['"', "'"])
def test_import_ignores_a_quoted_keyword(
    keyword, quote, xession, completion_context_parse
):
    """``"import" in aliases<TAB>`` is not an import statement."""
    line = f"{quote}{keyword}{quote} in ali"
    assert not _values(complete_import(completion_context_parse(line, len(line))))


@pytest.mark.parametrize(
    "line, expected",
    [("from os imp", "import"), ("import o", "os"), ("from o", "os")],
)
def test_import_still_completes_real_statements(
    line, expected, xession, completion_context_parse
):
    assert expected in _values(
        complete_import(completion_context_parse(line, len(line)))
    )


#
# complete_from_man
#


@skip_if_on_windows
def test_man_ignores_a_quoted_command_name(xession, completion_context_parse):
    """``"less" -<TAB>`` must not offer ``less``'s options."""
    line = '"less" -'
    assert not _values(complete_from_man(completion_context_parse(line, len(line))))


@skip_if_on_windows
def test_man_still_completes_a_real_command(xession, completion_context_parse):
    from xonsh.completers.man import _man_page_path

    if _man_page_path("less") is None:
        pytest.skip("no man page for 'less' on this host")
    line = "less -"
    assert _values(complete_from_man(completion_context_parse(line, len(line))))


#
# complete_aliases
#


@pytest.fixture
def alias_with_completer(xession):
    """An alias whose ``xonsh_complete`` records that it was called."""
    calls = []

    def completer(command, alias):
        calls.append(command)
        return {"FROM-THE-ALIAS"}

    def func(args):
        pass

    func.xonsh_complete = completer
    xession.aliases["mycmd"] = func
    xession.ctx["aliases"] = xession.aliases
    return calls


def test_aliases_ignores_a_quoted_command_name(
    alias_with_completer, completion_context_parse
):
    """``"mycmd" in aliases<TAB>`` must not run ``mycmd``'s completer."""
    line = '"mycmd" in ali'
    assert not _values(complete_aliases(completion_context_parse(line, len(line))))
    assert alias_with_completer == []


def test_aliases_still_completes_a_real_command(
    alias_with_completer, completion_context_parse
):
    line = "mycmd ali"
    assert "FROM-THE-ALIAS" in _values(
        complete_aliases(completion_context_parse(line, len(line)))
    )
    assert len(alias_with_completer) == 1
