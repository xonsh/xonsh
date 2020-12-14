import itertools

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
    (f"'comm and' a{X}b", CommandContext(
        args=(CommandArg("comm and", opening_quote="'", closing_quote="'"),), arg_index=1, prefix="a", suffix="b")),
)

STRING_ARGS_EXAMPLES = (
    (f"'comm an{X}d'", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="'", closing_quote="'")),
    (f"'comm and{X}'", CommandContext(
        args=(), arg_index=0, prefix="comm and", suffix="", opening_quote="'", closing_quote="'")),
    (f"\"comm an{X}d\"", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="\"", closing_quote="\"")),
    (f"'''comm an{X}d'''", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="'''", closing_quote="'''")),
    (f"fr'comm an{X}d'", CommandContext(
        args=(), arg_index=0, prefix="comm an", suffix="d", opening_quote="fr'", closing_quote="'")),
    (f"'()+{X}'", CommandContext(
        args=(), arg_index=0, prefix="()+", opening_quote="'", closing_quote="'")),
)

COMMAND_EXAMPLES += STRING_ARGS_EXAMPLES


@pytest.mark.parametrize("commandline, context", COMMAND_EXAMPLES)
def test_command(commandline, context):
    assert_match(commandline, context)


@pytest.mark.parametrize("commandline, context", STRING_ARGS_EXAMPLES)
def test_partial_string_arg(commandline, context):
    partial_commandline = commandline.rstrip("\"'")
    partial_context = context._replace(closing_quote="")
    assert_match(partial_commandline, partial_context)


CONT = "\\" "\n"


@pytest.mark.parametrize("commandline, context", (
        # line continuations:
        (f"echo {CONT}a {X}", CommandContext(args=(CommandArg("echo"), CommandArg("a")), arg_index=2)),
        (f"echo {CONT}{X}a {CONT} b",
         CommandContext(args=(CommandArg("echo"), CommandArg("b")), arg_index=1, suffix="a")),
        (f"echo a{CONT}{X}b",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b")),
        (f"echo a{X}{CONT}b",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b")),
        (f"echo ${CONT}(a) {CONT} {X}b",
         CommandContext(args=(CommandArg("echo"), CommandArg("$(a)")), arg_index=2, suffix="b")),

        # line continuations in strings:
        (f"echo 'a{CONT}{X}b'",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b", opening_quote="'",
                        closing_quote="'")),
        (f"echo '''a{CONT}{X}b'''",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b", opening_quote="'''",
                        closing_quote="'''")),
        (f"echo 'a{CONT}{X}b",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b", opening_quote="'")),
        (f"echo '''a{CONT}{X}b",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b", opening_quote="'''")),
        (f"echo ''{CONT}'a{X}b",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b", opening_quote="'''")),
        (f"echo '''a{CONT}{X} b",
         CommandContext(args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix=" b", opening_quote="'''")),

        # triple-quoted strings:
        (f"echo '''a\nb{X}\nc'''", CommandContext(
            args=(CommandArg("echo"),), arg_index=1,
            prefix="a\nb", suffix="\nc", opening_quote="'''", closing_quote="'''")),
        (f"echo '''a\n b{X} \n  c'''", CommandContext(
            args=(CommandArg("echo"),), arg_index=1,
            prefix="a\n b", suffix=" \n  c", opening_quote="'''", closing_quote="'''")),

        # partial triple-quoted strings:
        (f"echo '''a\nb{X}\nc", CommandContext(
            args=(CommandArg("echo"),), arg_index=1,
            prefix="a\nb", suffix="\nc", opening_quote="'''")),
        (f"echo '''a\n b{X} \n  c", CommandContext(
            args=(CommandArg("echo"),), arg_index=1,
            prefix="a\n b", suffix=" \n  c", opening_quote="'''")),
))
def test_multiline_command(commandline, context):
    assert_match(commandline, context)


NESTING_EXAMPLES = (
    # nesting, prefix
    (f"echo $({X})", "$("),
    (f"echo @$({X})", "@$("),
    (f"echo $(echo $({X}))", "$("),
    (f"echo @(x + $({X}))", "$("),
    (f"!({X})", "!("),
    (f"$[{X}]", "$["),
    (f"![{X}]", "!["),
)

NESTED_SIMPLE_CMD_EXAMPLES = [
    (nesting, f"simple {X}", CommandContext(args=(CommandArg("simple"),), arg_index=1, subcmd_opening=prefix))
    for nesting, prefix in NESTING_EXAMPLES[1:]]


@pytest.mark.parametrize("nesting, commandline, context", list(itertools.chain((
        # complex subcommand in a simple nested expression
        (NESTING_EXAMPLES[0][0], commandline, context._replace(subcmd_opening=NESTING_EXAMPLES[0][1]))
        for commandline, context in COMMAND_EXAMPLES
), NESTED_SIMPLE_CMD_EXAMPLES)))
def test_nested_command(commandline, context, nesting):
    nested_commandline = nesting.replace(X, commandline)
    assert_match(nested_commandline, context)


@pytest.mark.parametrize("nesting, commandline, context", NESTED_SIMPLE_CMD_EXAMPLES)
@pytest.mark.parametrize("malformation", (
        lambda s: s[:-1],  # remove the last closing brace ')' / ']'
        lambda s: s + s[-1],  # add an extra closing brace ')' / ']'
        lambda s: s[-1] + s,
        lambda s: s + "$(",
        lambda s: "$(" + s,
))
def test_malformed_subcmd(nesting, commandline, context, malformation):
    nested_commandline = nesting.replace(X, commandline)
    nested_commandline = malformation(nested_commandline)
    assert_match(nested_commandline, context)


def test_other_subcommand_arg():
    command = "echo $(pwd) "
    assert parse(command, len(command)) == CommandContext(
        (CommandArg("echo"), CommandArg("$(pwd)")), arg_index=2)


def test_combined_subcommand_arg():
    command = f"echo file=$(pwd{X})/x"

    # index inside the subproc
    assert_match(command, CommandContext(
        (), arg_index=0, prefix="pwd", subcmd_opening="$("))

    # index at the end of the command
    assert_match(command.replace(X, ""), CommandContext(
        (CommandArg("echo"),), arg_index=1, prefix="file=$(pwd)/x"))


@pytest.mark.parametrize("commandline, context", (
        (f"{X}$(echo)", CommandContext((), 0, suffix="$(echo)")),
        (f"${X}(echo)", CommandContext((), 0, prefix="$", suffix="(echo)")),
        (f"$(echo){X}", CommandContext((), 0, prefix="$(echo)")),
        (f"${X}( echo)", CommandContext((), 0, prefix="$", suffix="( echo)")),
        (f"$(echo ){X}", CommandContext((), 0, prefix="$(echo )")),
))
def test_cursor_in_subcmd_borders(commandline, context):
    assert_match(commandline, context)
