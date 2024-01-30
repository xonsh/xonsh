import itertools
import typing as tp
from unittest import mock

import pytest

import xonsh.parsers.completion_context as ctx
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContextParser,
    PythonContext,
)
from xonsh.pytest.tools import ON_WINDOWS

DEBUG = False
MISSING = object()
X = "\x00"  # cursor marker
PARSER: tp.Optional[CompletionContextParser] = None


@pytest.fixture(scope="module", autouse=True)
def parser():
    global PARSER
    PARSER = CompletionContextParser(debug=DEBUG)
    patcher = None
    if ON_WINDOWS:
        # on-windows has an option for interactive sessions. Overriding the lazyObject
        patcher = mock.patch.object(
            ctx,
            "LINE_CONT_REPLACEMENT_DIFF",
            ("\\\n", "", -2),
        )
        patcher.start()
    yield
    PARSER = None
    if ON_WINDOWS and patcher:
        patcher.stop()


def parse(command, inner_index):
    return PARSER.parse(command, inner_index)


def assert_match(
    commandline, command_context=MISSING, python_context=MISSING, is_main_command=False
):
    if X in commandline:
        index = commandline.index(X)
        commandline = commandline.replace(X, "")
    else:
        index = len(commandline)
    context = parse(commandline, index)
    if context is None:
        raise SyntaxError(
            "Failed to parse the commandline - set DEBUG = True in this file to see the error"
        )
    if is_main_command and python_context is MISSING:
        python_context = PythonContext(commandline, index)
    if command_context is not MISSING:
        assert context.command == command_context
    if python_context is not MISSING:
        assert context.python == python_context


COMMAND_EXAMPLES = (
    (f"comm{X}", CommandContext(args=(), arg_index=0, prefix="comm")),
    (f" comm{X}", CommandContext(args=(), arg_index=0, prefix="comm")),
    (f"comm{X}and", CommandContext(args=(), arg_index=0, prefix="comm", suffix="and")),
    (f"command {X}", CommandContext(args=(CommandArg("command"),), arg_index=1)),
    (f"{X} command", CommandContext(args=(CommandArg("command"),), arg_index=0)),
    (f" command {X}", CommandContext(args=(CommandArg("command"),), arg_index=1)),
    (
        f"command --{X}",
        CommandContext(args=(CommandArg("command"),), arg_index=1, prefix="--"),
    ),
    (
        f"command a {X}",
        CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=2),
    ),
    (
        f"command a b{X}",
        CommandContext(
            args=(CommandArg("command"), CommandArg("a")), arg_index=2, prefix="b"
        ),
    ),
    (
        f"command a   b{X}",
        CommandContext(
            args=(CommandArg("command"), CommandArg("a")), arg_index=2, prefix="b"
        ),
    ),
    (
        f"command {X} a",
        CommandContext(args=(CommandArg("command"), CommandArg("a")), arg_index=1),
    ),
    (
        f"command a {X} b",
        CommandContext(
            args=(CommandArg("command"), CommandArg("a"), CommandArg("b")), arg_index=2
        ),
    ),
    (
        f"command -{X} b",
        CommandContext(
            args=(CommandArg("command"), CommandArg("b")), arg_index=1, prefix="-"
        ),
    ),
    (
        f"command a {X}b",
        CommandContext(
            args=(CommandArg("command"), CommandArg("a")), arg_index=2, suffix="b"
        ),
    ),
    (
        f"command a{X}b",
        CommandContext(
            args=(CommandArg("command"),), arg_index=1, prefix="a", suffix="b"
        ),
    ),
    (
        f"'comm and' a{X}b",
        CommandContext(
            args=(CommandArg("comm and", opening_quote="'", closing_quote="'"),),
            arg_index=1,
            prefix="a",
            suffix="b",
        ),
    ),
    (
        f"command >/dev/nul{X}",
        CommandContext(
            args=(CommandArg("command"), CommandArg(">", is_io_redir=True)),
            arg_index=2,
            prefix="/dev/nul",
        ),
    ),
    (
        f"command 2>/dev/nul{X}",
        CommandContext(
            args=(CommandArg("command"), CommandArg("2>", is_io_redir=True)),
            arg_index=2,
            prefix="/dev/nul",
        ),
    ),
    (
        f"command >>/dev/nul{X}",
        CommandContext(
            args=(CommandArg("command"), CommandArg(">>", is_io_redir=True)),
            arg_index=2,
            prefix="/dev/nul",
        ),
    ),
    (
        f"command </dev/nul{X}",
        CommandContext(
            args=(CommandArg("command"), CommandArg("<", is_io_redir=True)),
            arg_index=2,
            prefix="/dev/nul",
        ),
    ),
)

EMPTY_COMMAND_EXAMPLES = (
    (f"{X}", CommandContext((), 0)),
    (f" {X}", CommandContext((), 0)),
    (f"{X} ", CommandContext((), 0)),
    (f" {X} ", CommandContext((), 0)),
)

STRING_ARGS_EXAMPLES = (
    (
        f"'comm an{X}d'",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm an",
            suffix="d",
            opening_quote="'",
            closing_quote="'",
        ),
    ),
    (
        f"'comm and{X}'",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm and",
            suffix="",
            opening_quote="'",
            closing_quote="'",
        ),
    ),
    (
        f"'comm {X}'",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm ",
            suffix="",
            opening_quote="'",
            closing_quote="'",
        ),
    ),
    (
        f'"comm an{X}d"',
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm an",
            suffix="d",
            opening_quote='"',
            closing_quote='"',
        ),
    ),
    (
        f"'''comm an{X}d'''",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm an",
            suffix="d",
            opening_quote="'''",
            closing_quote="'''",
        ),
    ),
    (
        f"fr'comm an{X}d'",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm an",
            suffix="d",
            opening_quote="fr'",
            closing_quote="'",
        ),
    ),
    (
        f"'()+{X}'",
        CommandContext(
            args=(), arg_index=0, prefix="()+", opening_quote="'", closing_quote="'"
        ),
    ),
    (
        f"'comm and'{X}",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm and",
            opening_quote="'",
            closing_quote="'",
            is_after_closing_quote=True,
        ),
    ),
    (
        f"'''comm and'''{X}",
        CommandContext(
            args=(),
            arg_index=0,
            prefix="comm and",
            opening_quote="'''",
            closing_quote="'''",
            is_after_closing_quote=True,
        ),
    ),
)

COMMAND_EXAMPLES += STRING_ARGS_EXAMPLES
COMMAND_EXAMPLES += EMPTY_COMMAND_EXAMPLES


@pytest.mark.parametrize("commandline, context", COMMAND_EXAMPLES)
def test_command(commandline, context):
    assert_match(commandline, context, is_main_command=True)


@pytest.mark.parametrize(
    "commandline, context",
    tuple(
        (commandline, context)
        for commandline, context in STRING_ARGS_EXAMPLES
        if commandline.endswith("'") or commandline.endswith('"')
    ),
)
def test_partial_string_arg(commandline, context):
    partial_commandline = commandline.rstrip("\"'")
    partial_context = context._replace(closing_quote="")
    assert_match(partial_commandline, partial_context, is_main_command=True)


CONT = "\\" "\n"


@pytest.mark.parametrize(
    "commandline, context",
    (
        # line continuations:
        (
            f"echo {CONT}a {X}",
            CommandContext(args=(CommandArg("echo"), CommandArg("a")), arg_index=2),
        ),
        (
            f"echo {CONT}{X}a {CONT} b",
            CommandContext(
                args=(CommandArg("echo"), CommandArg("b")), arg_index=1, suffix="a"
            ),
        ),
        (
            f"echo a{CONT}{X}b",
            CommandContext(
                args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b"
            ),
        ),
        (
            f"echo a{X}{CONT}b",
            CommandContext(
                args=(CommandArg("echo"),), arg_index=1, prefix="a", suffix="b"
            ),
        ),
        (
            f"echo ${CONT}(a) {CONT} {X}b",
            CommandContext(
                args=(CommandArg("echo"), CommandArg("$(a)")), arg_index=2, suffix="b"
            ),
        ),
        # line continuations in strings:
        (
            f"echo 'a{CONT}{X}b'",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a",
                suffix="b",
                opening_quote="'",
                closing_quote="'",
            ),
        ),
        (
            f"echo '''a{CONT}{X}b'''",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a",
                suffix="b",
                opening_quote="'''",
                closing_quote="'''",
            ),
        ),
        (
            f"echo 'a{CONT}{X}b",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a",
                suffix="b",
                opening_quote="'",
            ),
        ),
        (
            f"echo '''a{CONT}{X}b",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a",
                suffix="b",
                opening_quote="'''",
            ),
        ),
        (
            f"echo ''{CONT}'a{X}b",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a",
                suffix="b",
                opening_quote="'''",
            ),
        ),
        (
            f"echo '''a{CONT}{X} b",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a",
                suffix=" b",
                opening_quote="'''",
            ),
        ),
        # triple-quoted strings:
        (
            f"echo '''a\nb{X}\nc'''",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a\nb",
                suffix="\nc",
                opening_quote="'''",
                closing_quote="'''",
            ),
        ),
        (
            f"echo '''a\n b{X} \n  c'''",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a\n b",
                suffix=" \n  c",
                opening_quote="'''",
                closing_quote="'''",
            ),
        ),
        # partial triple-quoted strings:
        (
            f"echo '''a\nb{X}\nc",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a\nb",
                suffix="\nc",
                opening_quote="'''",
            ),
        ),
        (
            f"echo '''a\n b{X} \n  c",
            CommandContext(
                args=(CommandArg("echo"),),
                arg_index=1,
                prefix="a\n b",
                suffix=" \n  c",
                opening_quote="'''",
            ),
        ),
    ),
)
def test_multiline_command(commandline, context):
    assert_match(commandline, context, is_main_command=True)


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
    (
        nesting,
        f"simple {X}",
        CommandContext(
            args=(CommandArg("simple"),), arg_index=1, subcmd_opening=prefix
        ),
    )
    for nesting, prefix in NESTING_EXAMPLES[1:]
]


@pytest.mark.parametrize(
    "nesting, commandline, context",
    list(
        itertools.chain(
            (
                # complex subcommand in a simple nested expression
                (
                    NESTING_EXAMPLES[0][0],
                    commandline,
                    context._replace(subcmd_opening=NESTING_EXAMPLES[0][1]),
                )
                for commandline, context in COMMAND_EXAMPLES
            ),
            NESTED_SIMPLE_CMD_EXAMPLES,
        )
    ),
)
def test_nested_command(commandline, context, nesting):
    nested_commandline = nesting.replace(X, commandline)
    assert_match(nested_commandline, command_context=context, python_context=None)


NESTING_MALFORMATIONS = (
    lambda s: s[:-1],  # remove the last closing brace ')' / ']'
    lambda s: s + s[-1],  # add an extra closing brace ')' / ']'
    lambda s: s[-1] + s,
    lambda s: s + "$(",
    lambda s: "$(" + s,
)


@pytest.mark.parametrize("nesting, commandline, context", NESTED_SIMPLE_CMD_EXAMPLES)
@pytest.mark.parametrize("malformation", NESTING_MALFORMATIONS)
def test_malformed_subcmd(nesting, commandline, context, malformation):
    nested_commandline = nesting.replace(X, commandline)
    nested_commandline = malformation(nested_commandline)
    assert_match(nested_commandline, command_context=context, python_context=None)


MALFORMED_SUBCOMMANDS_NESTINGS = (
    # nesting, subcmd_opening
    (f"echo $(a $({X}", "$("),
    (f"echo $(a $(b; {X}", ""),
    (f"$(echo $(a $({X}", "$("),
    (f"echo $[a $({X}]", "$("),
    (f"echo $(a $[{X})", "$["),
    (f"echo @(x = $({X}", "$("),
    (f"echo @(a; x = $({X}", "$("),
    (f"echo @(x = $(a; {X}", ""),
)


@pytest.mark.parametrize("nesting, subcmd_opening", MALFORMED_SUBCOMMANDS_NESTINGS)
@pytest.mark.parametrize("commandline, context", COMMAND_EXAMPLES[:5])
def test_multiple_malformed_subcmds(nesting, subcmd_opening, commandline, context):
    nested_commandline = nesting.replace(X, commandline)
    nested_context = context._replace(subcmd_opening=subcmd_opening)
    assert_match(nested_commandline, nested_context, python_context=None)


def test_other_subcommand_arg():
    command = "echo $(pwd) "
    assert_match(
        command,
        CommandContext((CommandArg("echo"), CommandArg("$(pwd)")), arg_index=2),
        is_main_command=True,
    )


def test_combined_subcommand_arg():
    command = f"echo file=$(pwd{X})/x"

    # index inside the subproc
    assert_match(
        command,
        CommandContext((), arg_index=0, prefix="pwd", subcmd_opening="$("),
        python_context=None,
    )

    # index at the end of the command
    assert_match(
        command.replace(X, ""),
        CommandContext((CommandArg("echo"),), arg_index=1, prefix="file=$(pwd)/x"),
        is_main_command=True,
    )


SUBCMD_BORDER_EXAMPLES = (
    (f"{X}$(echo)", CommandContext((), 0, suffix="$(echo)")),
    (f"${X}(echo)", CommandContext((), 0, prefix="$", suffix="(echo)")),
    (f"$(echo){X}", CommandContext((), 0, prefix="$(echo)")),
    (f"${X}( echo)", CommandContext((), 0, prefix="$", suffix="( echo)")),
    (f"$(echo ){X}", CommandContext((), 0, prefix="$(echo )")),
)


@pytest.mark.parametrize("commandline, context", SUBCMD_BORDER_EXAMPLES)
def test_cursor_in_subcmd_borders(commandline, context):
    assert_match(commandline, context, is_main_command=True)


MULTIPLE_COMMAND_KEYWORDS = (
    "; ",
    "\n",
    " and ",
    "&& ",
    " or ",
    "|| ",
    "| ",
)

MULTIPLE_CMD_SIMPLE_EXAMPLES = [
    (
        keyword,
        ("echo hi", f"simple {X}"),
        CommandContext(args=(CommandArg("simple"),), arg_index=1),
    )
    for keyword in MULTIPLE_COMMAND_KEYWORDS
]

EXTENSIVE_COMMAND_PAIRS = tuple(
    itertools.chain(
        zip(COMMAND_EXAMPLES, COMMAND_EXAMPLES[::-1]),
        zip(COMMAND_EXAMPLES, EMPTY_COMMAND_EXAMPLES),
        zip(EMPTY_COMMAND_EXAMPLES, COMMAND_EXAMPLES),
        zip(EMPTY_COMMAND_EXAMPLES, EMPTY_COMMAND_EXAMPLES),
    )
)

MULTIPLE_COMMAND_EXTENSIVE_EXAMPLES = tuple(
    itertools.chain(
        (
            # cursor in first command
            ((first, second.replace(X, "")), first_context)
            for (first, first_context), (
                second,
                second_context,
            ) in EXTENSIVE_COMMAND_PAIRS
        ),
        (
            # cursor in second command
            ((first.replace(X, ""), second), second_context)
            for (first, first_context), (
                second,
                second_context,
            ) in EXTENSIVE_COMMAND_PAIRS
        ),
        (
            # cursor in middle command
            ((first.replace(X, ""), second, third.replace(X, "")), second_context)
            for (first, _1), (second, second_context), (third, _3) in zip(
                COMMAND_EXAMPLES[:3], COMMAND_EXAMPLES[3:6], COMMAND_EXAMPLES[6:9]
            )
        ),
        (
            # cursor in third command
            ((first.replace(X, ""), second.replace(X, ""), third), third_context)
            for (first, _1), (second, _2), (third, third_context) in zip(
                COMMAND_EXAMPLES[:3], COMMAND_EXAMPLES[3:6], COMMAND_EXAMPLES[6:9]
            )
        ),
    )
)


@pytest.mark.parametrize(
    "keyword, commands, context",
    tuple(
        itertools.chain(
            (
                (MULTIPLE_COMMAND_KEYWORDS[0], commands, context)
                for commands, context in MULTIPLE_COMMAND_EXTENSIVE_EXAMPLES
            ),
            MULTIPLE_CMD_SIMPLE_EXAMPLES,
        )
    ),
)
def test_multiple_commands(keyword, commands, context):
    joined_command = keyword.join(commands)

    cursor_command = next(command for command in commands if X in command)
    if cursor_command is commands[0]:
        relative_index = cursor_command.index(X)
    else:
        absolute_index = joined_command.index(X)
        relative_index = (
            absolute_index
            - joined_command.rindex(keyword, 0, absolute_index)
            - len(keyword)
        )
        if keyword.endswith(" "):
            # the last space is part of the command
            relative_index += 1
            cursor_command = " " + cursor_command

    assert_match(joined_command, context, is_main_command=True)


@pytest.mark.parametrize(
    "commandline",
    (
        f"{X};",
        f"; {X}",
        f"{X};;",
        f"; {X};",
        f";; {X}",
        f";;; {X}",
    ),
)
def test_multiple_empty_commands(commandline):
    assert_match(commandline, CommandContext((), 0), is_main_command=True)


@pytest.mark.parametrize(
    "nesting, keyword, commands, context",
    tuple(
        (
            nesting,
            keyword,
            commands,
            context,
        )  # no subcmd_opening in nested multi-commands
        for nesting, prefix in NESTING_EXAMPLES
        for keyword, commands, context in MULTIPLE_CMD_SIMPLE_EXAMPLES
        if keyword != "\n"  # the lexer ignores newlines inside subcommands
    ),
)
def test_nested_multiple_commands(nesting, keyword, commands, context):
    joined_command = keyword.join(commands)
    nested_joined = nesting.replace(X, joined_command)
    assert_match(nested_joined, context, python_context=None)


def test_multiple_nested_commands():
    assert_match(
        f"echo hi; echo $(ls{X})",
        CommandContext((), 0, prefix="ls", subcmd_opening="$("),
        python_context=None,
    )


@pytest.mark.parametrize(
    "commandline, context",
    tuple(
        (commandline, context)
        for commandline, context in STRING_ARGS_EXAMPLES
        if commandline.endswith("'") or commandline.endswith('"')
    ),
)
def test_multiple_partial_string_arg(commandline, context):
    partial_commandline = commandline.rstrip("\"'")
    partial_context = context._replace(closing_quote="")
    assert_match("echo;" + partial_commandline, partial_context)
    assert_match("echo $[a ;" + partial_commandline, partial_context)


@pytest.mark.parametrize(
    "nesting, keyword, commands, context",
    tuple(
        (nesting, keyword, commands, context)
        for nesting, prefix in NESTING_EXAMPLES[:1]
        for keyword, commands, context in MULTIPLE_CMD_SIMPLE_EXAMPLES[:1]
    ),
)
@pytest.mark.parametrize("malformation", NESTING_MALFORMATIONS)
def test_malformed_subcmd_1(malformation, nesting, keyword, commands, context):
    joined_command = keyword.join(commands)
    nested_joined = nesting.replace(X, joined_command)
    malformed_commandline = malformation(nested_joined)
    assert_match(malformed_commandline, context, python_context=None)


MULTIPLE_COMMAND_BORDER_EXAMPLES = tuple(
    itertools.chain(
        itertools.chain(
            *(
                (
                    (
                        f"ls{ws1}{X}{kwd}{ws2}echo",
                        (
                            CommandContext((CommandArg("ls"),), 1)
                            if ws1
                            else CommandContext((), 0, prefix="ls")
                        ),
                    ),
                )
                for ws1, ws2, kwd in itertools.product(
                    ("", " "), ("", " "), ("&&", ";")
                )
            )
        ),
        # all keywords are treated as a normal arg if the cursor is at the edge
        (
            (
                f"ls {X}and echo",
                CommandContext((CommandArg("ls"), CommandArg("echo")), 1, suffix="and"),
            ),
            (
                f"ls and{X} echo",
                CommandContext((CommandArg("ls"), CommandArg("echo")), 1, prefix="and"),
            ),
            (
                f"ls ||{X} echo",
                CommandContext((CommandArg("ls"), CommandArg("echo")), 1, prefix="||"),
            ),
        ),
        # if the cursor is inside the keyword, it's treated as a normal arg
        (
            (
                f"ls a{X}nd echo",
                CommandContext(
                    (CommandArg("ls"), CommandArg("echo")), 1, prefix="a", suffix="nd"
                ),
            ),
            (
                f"ls &{X}& echo",
                CommandContext(
                    (CommandArg("ls"), CommandArg("echo")), 1, prefix="&", suffix="&"
                ),
            ),
        ),
    )
)


@pytest.mark.parametrize(
    "commandline, context",
    tuple(
        itertools.chain(
            MULTIPLE_COMMAND_BORDER_EXAMPLES,
            (
                # ensure these rules work with more than one command
                (f"cat | {commandline}", context)
                for commandline, context in MULTIPLE_COMMAND_BORDER_EXAMPLES
            ),
        )
    ),
)
def test_cursor_in_multiple_keyword_borders(commandline, context):
    assert_match(commandline, context)


PYTHON_EXAMPLES = (
    # commandline, context
    (f"x = {X}", PythonContext("x = ", 4)),
    (f"a {X}= x; b = y", PythonContext("a = x; b = y", 2)),
    (f"a {X}= x\nb = $(ls)", PythonContext("a = x\nb = $(ls)", 2)),
)

PYTHON_NESTING_EXAMPLES = (
    # nesting, prefix
    f"echo @({X})",
    f"echo $(echo @({X}))",
    f"echo @(x + @({X}))",  # invalid syntax, but can still be in a partial command
)


@pytest.mark.parametrize(
    "nesting, commandline, context",
    list(
        itertools.chain(
            (
                # complex subcommand in a simple nested expression
                (nesting, commandline, context._replace(is_sub_expression=True))
                for nesting in PYTHON_NESTING_EXAMPLES[:1]
                for commandline, context in PYTHON_EXAMPLES
            ),
            (
                # simple subcommand in a complex nested expression
                (nesting, commandline, context._replace(is_sub_expression=True))
                for nesting in PYTHON_NESTING_EXAMPLES
                for commandline, context in PYTHON_EXAMPLES[:1]
            ),
        )
    ),
)
def test_nested_python(commandline, context, nesting):
    nested_commandline = nesting.replace(X, commandline)
    assert_match(nested_commandline, command_context=None, python_context=context)


@pytest.mark.parametrize(
    "commandline, context",
    [
        (
            commandline.replace("$", "@"),
            context._replace(
                prefix=context.prefix.replace("$", "@"),
                suffix=context.suffix.replace("$", "@"),
            ),
        )
        for commandline, context in SUBCMD_BORDER_EXAMPLES
    ],
)
def test_cursor_in_sub_python_borders(commandline, context):
    assert_match(commandline, context, is_main_command=True)


@pytest.mark.parametrize(
    "code",
    (
        f"""
x = 3
x.{X}""",
        f"""
x = 3;
y = 4;
x.{X}""",
        f"""
def func({X}):
    return 100
    """,
        f"""
class A:
    def a():
        return "a{X}"
    pass
exit()
    """,
    ),
)
def test_multiline_python(code):
    assert_match(code, is_main_command=True)
