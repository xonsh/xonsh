"""Tests for tab-completion of click-based aliases (xonsh/xonsh#6265).

Exercises :func:`xonsh.completers.click.complete_click`, wired up by
``@aliases.register_click_command``. The completer is looked up by
``xonsh.completers._aliases.complete_aliases`` via
``alias.func.xonsh_complete``.
"""

import pytest

from xonsh.aliases import Aliases
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)


@pytest.fixture
def click():
    return pytest.importorskip("click")


def _complete(aliases, alias_name, *tokens, prefix=""):
    """Drive the alias's ``xonsh_complete`` directly and return a set of strs.

    ``tokens`` are the full argument words typed *before* the cursor (not
    including the alias name itself); ``prefix`` is the partial word at
    the cursor.
    """
    args = (CommandArg(alias_name),) + tuple(CommandArg(t) for t in tokens)
    ctx = CommandContext(args=args, arg_index=len(args), prefix=prefix)
    alias = aliases._raw[alias_name]
    result = alias.func.xonsh_complete(command=ctx, alias=alias)
    if result is None:
        return None
    return {str(r) for r in result}


def test_click_complete_options_by_prefix(click):
    """``hello --nam<TAB>`` offers ``--name``."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--name", default="Anonymous")
    @aliases.click.option("--count", default=1)
    def _hello(ctx, name, count):
        pass

    assert _complete(aliases, "hello", prefix="--nam") == {"--name"}


def test_click_complete_all_long_options(click):
    """``hello --<TAB>`` lists every long option, plus the implicit ``--help``."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--name", default="Anonymous")
    @aliases.click.option("--count", default=1)
    def _hello(ctx, name, count):
        pass

    assert _complete(aliases, "hello", prefix="--") == {
        "--name",
        "--count",
        "--help",
    }


def test_click_complete_short_and_long_options(click):
    """``cmd -<TAB>`` includes short flags as well as long ones."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("-n", "--name")
    @aliases.click.option("-v", "--verbose", is_flag=True)
    def _cmd(ctx, name, verbose):
        pass

    result = _complete(aliases, "cmd", prefix="-")
    assert {"-n", "--name", "-v", "--verbose"}.issubset(result)


def test_click_complete_flag_pair_secondary_opts(click):
    """Flag pairs (``--verbose/--quiet``) surface *both* sides."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--verbose/--quiet", default=False)
    def _cmd(ctx, verbose):
        pass

    result = _complete(aliases, "cmd", prefix="--")
    assert {"--verbose", "--quiet"}.issubset(result)


def test_click_complete_option_value_choice(click):
    """``--color <TAB>`` offers the ``click.Choice`` values."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--color", type=click.Choice(["red", "green", "blue"]))
    def _cmd(ctx, color):
        pass

    assert _complete(aliases, "cmd", "--color", prefix="") == {
        "red",
        "green",
        "blue",
    }


def test_click_complete_option_value_choice_prefix(click):
    """Prefix filters the Choice values (``--color r<TAB>`` → only ``red``)."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--color", type=click.Choice(["red", "green", "blue"]))
    def _cmd(ctx, color):
        pass

    assert _complete(aliases, "cmd", "--color", prefix="r") == {"red"}


def test_click_complete_option_value_opaque_returns_none(click):
    """``--name <TAB>`` (no Choice type) returns ``None`` so other completers
    (path/base) can still fire. Flags do NOT count as value-consuming.
    """
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--name", default="")
    def _cmd(ctx, name):
        pass

    assert _complete(aliases, "cmd", "--name", prefix="") is None


def test_click_complete_flag_does_not_consume_next_token(click):
    """After a bare flag, options should complete again — the flag takes no value.

    Regression guard: the completer must distinguish ``is_flag`` / count
    options from options that take a value.
    """
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("-v", "--verbose", is_flag=True)
    @aliases.click.option("--name", default="")
    def _cmd(ctx, verbose, name):
        pass

    # After "-v ", "--<TAB>" should still offer --name (we're not waiting
    # for -v's value).
    assert _complete(aliases, "cmd", "-v", prefix="--") == {
        "--name",
        "--verbose",
        "--help",
    }


def test_click_complete_group_subcommands(click):
    """``grp <TAB>`` lists sub-commands of a ``click.Group``."""
    aliases = Aliases()

    @click.group()
    def _grp():
        pass

    @_grp.command(short_help="run the server")
    def serve():
        pass

    @_grp.command()
    def status():
        pass

    aliases.register_click_command(_grp)
    assert _complete(aliases, "grp", prefix="") == {"serve", "status"}


def test_click_complete_group_subcommand_prefix(click):
    """Prefix filters sub-command names."""
    aliases = Aliases()

    @click.group()
    def _grp():
        pass

    @_grp.command()
    def serve():
        pass

    @_grp.command()
    def status():
        pass

    aliases.register_click_command(_grp)
    assert _complete(aliases, "grp", prefix="se") == {"serve"}


def test_click_complete_subcommand_options(click):
    """Inside a sub-command, ``--<TAB>`` completes *the sub-command's* options."""
    aliases = Aliases()

    @click.group()
    def _grp():
        pass

    @_grp.command()
    @click.option("--port", default=8080)
    def serve(port):
        pass

    aliases.register_click_command(_grp)
    result = _complete(aliases, "grp", "serve", prefix="--")
    assert result == {"--port", "--help"}


def test_click_complete_group_flag_before_subcommand(click):
    """A group-level flag between ``grp`` and the sub-command doesn't
    derail sub-command resolution.
    """
    aliases = Aliases()

    @click.group()
    @click.option("--debug", is_flag=True)
    def _grp(debug):
        pass

    @_grp.command()
    @click.option("--port", default=8080)
    def serve(port):
        pass

    aliases.register_click_command(_grp)
    assert _complete(aliases, "grp", "--debug", "serve", prefix="--") == {
        "--port",
        "--help",
    }


def test_click_complete_positional_argument_choice(click):
    """``click.Argument`` with a Choice type completes its values."""
    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.argument("target", type=click.Choice(["prod", "staging", "dev"]))
    def _deploy(ctx, target):
        pass

    assert _complete(aliases, "deploy", prefix="") == {"prod", "staging", "dev"}
    assert _complete(aliases, "deploy", prefix="p") == {"prod"}


def test_click_complete_custom_alias_name(click):
    """Completion works even when the alias is registered under a custom name."""
    aliases = Aliases()

    @aliases.register_click_command("hi")
    @aliases.click.option("--name", default="Anonymous")
    def _hello(ctx, name):
        pass

    assert "hi" in aliases
    assert _complete(aliases, "hi", prefix="--nam") == {"--name"}


def test_click_complete_via_complete_aliases(click, xession):
    """Smoke test: the full ``complete_aliases`` pipeline picks up our
    ``xonsh_complete`` attribute and produces the same completions.
    """
    from xonsh.completers._aliases import complete_aliases

    @xession.aliases.register_click_command
    @xession.aliases.click.option("--name", default="World")
    @xession.aliases.click.option("--count", default=1)
    def _hello_click_alias_for_test(ctx, name, count):
        pass

    try:
        full = CompletionContext(
            command=CommandContext(
                args=(CommandArg("hello-click-alias-for-test"),),
                arg_index=1,
                prefix="--nam",
            )
        )
        comps, _extra = complete_aliases(full)
        assert {str(c) for c in comps} == {"--name"}
    finally:
        del xession.aliases["hello-click-alias-for-test"]


def test_click_complete_option_help_text_in_description(click):
    """Options surface their ``help=`` text as the RichCompletion description —
    keeps the behaviour parity with argparse-based aliases.
    """
    from xonsh.completers.tools import RichCompletion

    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--name", default="Anon", help="Who to greet")
    def _hello(ctx, name):
        pass

    alias = aliases._raw["hello"]
    ctx = CommandContext(args=(CommandArg("hello"),), arg_index=1, prefix="--nam")
    result = alias.func.xonsh_complete(command=ctx, alias=alias)
    comps = {c: c for c in result if isinstance(c, RichCompletion)}
    assert any(c.description == "Who to greet" for c in comps)


def test_click_complete_unknown_subcommand_stops_walk(click):
    """An unknown sub-command token halts traversal and falls back to the
    current group — we still complete the group's options.
    """
    aliases = Aliases()

    @click.group()
    @click.option("--debug", is_flag=True)
    def _grp(debug):
        pass

    @_grp.command()
    def serve():
        pass

    aliases.register_click_command(_grp)
    # "nonexistent" isn't a real sub-command; completer should still work
    # against the root group and offer its options.
    result = _complete(aliases, "grp", "nonexistent", prefix="--")
    assert "--debug" in result
    assert "--help" in result
