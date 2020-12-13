import pytest

from xonsh.parsers.completion_context import CommandArg, CommandContext, CompletionContextParser


def parse(command, inner_index):
    return CompletionContextParser().parse(command, inner_index)


X = "\x00"  # cursor marker


def assert_match(commandline, context):
    if X in commandline:
        index = commandline.index(X)
        commandline = commandline.replace(X, "")
    else:
        index = len(commandline)
    assert parse(commandline, index) == context


COMMAND_EXAMPLES = (
    (f"comm{X}", CommandContext(args=(), arg_index=0, prefix="comm")),
    (f" comm{X}", CommandContext(args=(), arg_index=0, prefix="comm")),
    (f"comm{X}and", CommandContext(args=(), arg_index=0, prefix="comm", suffix="and")),
    (f"command {X}", CommandContext(args=(CommandArg("command"),), arg_index=1)),
    (f"{X} command", CommandContext(args=(CommandArg("command"),), arg_index=0)),
    (f" command {X}", CommandContext(args=(CommandArg("command"),), arg_index=1)),
    (f"command --{X}", CommandContext(args=(CommandArg("command"),), arg_index=1, prefix="--")),
    (f"command a {X}", CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=2)),
    (f"command a b{X}", CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=2, prefix="b")),
    (f"command a   b{X}", CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=2, prefix="b")),
    (f"command {X} a", CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=1)),
    (f"command a {X} b", CommandContext(args=(CommandArg("command"), CommandArg("a"), CommandArg("b")), arg_index=2)),
    (f"command -{X} b", CommandContext(args=(CommandArg("command"), CommandArg("b")), arg_index=1, prefix="-")),
    (f"command a {X}b", CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=2, suffix="b")),
    (f"command a{X}b", CommandContext(args=(CommandArg("command"),), arg_index=1, prefix="a", suffix="b")),
    (f"'comm an{X}d'", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="'", closing_quote="'")),
    (f"'''comm an{X}d'''", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="'''", closing_quote="'''")),
    (f"fr'comm an{X}d'", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="fr'", closing_quote="'")),
    (f"'comm and' a{X}b", CommandContext(
        args=(CommandArg("comm and", opening_quote="'", closing_quote="'"),), arg_index=1, prefix="a", suffix="b")),
)


@pytest.mark.parametrize("commandline, context", COMMAND_EXAMPLES)
def test_command(commandline, context):
    assert_match(commandline, context)
