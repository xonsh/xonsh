"""Implements the xonsh (tab-)completion context parser.
This parser is meant to parse a (possibly incomplete) command line.
"""

import enum
import os
import re
from collections import defaultdict
from typing import (
    Any,
    Generic,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers.base import Location, raise_parse_error
from xonsh.parsers.lexer import Lexer
from xonsh.parsers.ply import yacc
from xonsh.tools import check_for_partial_string, get_line_continuation


class CommandArg(NamedTuple):
    """An argument for a command"""

    value: str
    """The argument's value"""
    opening_quote: str = ""
    """The arg's opening quote (if it exists)"""
    closing_quote: str = ""
    """The arg's closing quote (if it exists)"""
    is_io_redir: bool = False
    """Whether the arg is IO redirection"""

    @property
    def raw_value(self):
        """The complete argument including quotes"""
        return f"{self.opening_quote}{self.value}{self.closing_quote}"


class CommandContext(NamedTuple):
    """
    The object containing the current command's completion context.
    """

    args: tuple[CommandArg, ...]
    """The arguments in the command"""
    arg_index: int  # ``-1`` if the cursor isn't in the command.
    """The current argument's index"""

    prefix: str = ""
    """The current string arg's prefix"""
    suffix: str = ""
    """The current string arg's suffix"""
    opening_quote: str = ""
    """The current arg's opening quote if it exists (e.g. ``'``, ``r"``, ``'''``)"""
    closing_quote: str = ""
    """The current arg's closing quote if it exists (e.g. ``'``, ``"``, ``'''``)"""
    is_after_closing_quote: bool = False
    """
    The cursor is appending to a closed string literal, i.e. cursor at the end of ``ls "/usr/"``.
    This affects the completion's behaviour - see ``Completer.complete`` in ``xonsh/completer.py``.
    """

    subcmd_opening: str = ""
    """If this command is inside a subproc expression (e.g. ``$(``, ``![``)"""

    def completing_command(self, command: str) -> bool:
        """Return whether this context is completing args for a command"""
        return self.arg_index > 0 and self.command == command

    @property
    def raw_prefix(self):
        """Prefix before the cursor, including quotes"""
        if self.is_after_closing_quote:
            return f"{self.opening_quote}{self.prefix}{self.closing_quote}"
        else:
            return f"{self.opening_quote}{self.prefix}"

    @property
    def command(self):
        if self.args:
            return self.args[0].raw_value
        return None

    @property
    def words_before_cursor(self) -> str:
        """words without current prefix"""
        return " ".join([arg.raw_value for arg in self.args[: self.arg_index]])

    @property
    def text_before_cursor(self) -> str:
        """full text before cursor including prefix"""
        return self.words_before_cursor + " " + self.prefix

    @property
    def begidx(self) -> int:
        """cursor's position"""
        return len(self.text_before_cursor)


class PythonContext(NamedTuple):
    """
    The object containing the current python code completion context.
    """

    multiline_code: str
    """The multi-line python code"""
    cursor_index: int
    """The cursor's index in the multiline code"""
    is_sub_expression: bool = False
    """Whether this is a sub expression (``@(...)``)"""
    ctx: Optional[dict[str, Any]] = None
    """Objects in the current execution context"""

    def __repr__(self):
        # don't show ctx since it might be huge
        return f"PythonContext({self.multiline_code!r}, {self.cursor_index}, is_sub_expression={self.is_sub_expression})"

    @property
    def prefix(self):
        """The code from the start to the cursor (may be multiline)"""
        return self.multiline_code[: self.cursor_index]


class CompletionContext(NamedTuple):
    """
    The object containing the current completion context.
    """

    command: Optional[CommandContext] = None
    """
    The current command.
    This will be ``None`` when we can't be completing a command, e.g. ``echo @(<TAB>``.
    """
    python: Optional[PythonContext] = None
    """
    The current python code.
    This will be ``None`` when we can't be completing python, e.g. ``echo $(<TAB>``.
    """

    def with_ctx(self, ctx: dict[str, Any]) -> "CompletionContext":
        if self.python is not None:
            return self._replace(python=self.python._replace(ctx=ctx))
        return self


# Internal parser code:


class ExpansionOperation(enum.Enum):
    NEVER_EXPAND = object()
    SIMPLE_ARG_EXPANSION: "Any" = None  # the default


class Missing(enum.Enum):
    MISSING = object()


T = TypeVar("T")
T2 = TypeVar("T2")

# can't use Generic + NamedTuple, can't use dataclasses for compatibility with python 3.6.


class Spanned(Generic[T]):
    __slots__ = ["value", "span", "cursor_context", "expansion_obj"]

    def __init__(
        self,
        value: T,
        span: slice,
        cursor_context: Optional[Union[CommandContext, PythonContext, int]] = None,
        expansion_obj: Union["ExpandableObject", ExpansionOperation] = None,
    ):
        """
        Some parsed value with span and context information.
        This is an internal class for the parser.
        Parameters
        ----------
        value :
            The spanned value.
        span :
            The span of chars this value takes in the input string.
        cursor_context :
            The context for the cursor if it's inside this value.
            May be an ``int`` to represent the relative cursor location in a simple string arg.
        expansion_obj :
            The object needed to expand value.
            This is used to expand the value to the right (e.g. in `expand_command_span`).
        """
        self.value = value
        self.span = span
        self.cursor_context = cursor_context
        self.expansion_obj = expansion_obj

    @overload
    def replace(
        self,
        value: Missing = Missing.MISSING,
        span: Union[slice, Missing] = Missing.MISSING,
        cursor_context: Optional[
            Union[CommandContext, PythonContext, int, Missing]
        ] = Missing.MISSING,
        expansion_obj: Union[
            "ExpandableObject", ExpansionOperation, Missing
        ] = Missing.MISSING,
    ) -> "Spanned[T]": ...

    @overload
    def replace(
        self,
        value: T2,
        span: Union[slice, Missing] = Missing.MISSING,
        cursor_context: Optional[
            Union[CommandContext, PythonContext, int, Missing]
        ] = Missing.MISSING,
        expansion_obj: Union[
            "ExpandableObject", ExpansionOperation, Missing
        ] = Missing.MISSING,
    ) -> "Spanned[T2]": ...

    def replace(
        self,
        value: Union[T2, Missing] = Missing.MISSING,
        span: Union[slice, Missing] = Missing.MISSING,
        cursor_context: Optional[
            Union[CommandContext, PythonContext, int, Missing]
        ] = Missing.MISSING,
        expansion_obj: Union[
            "ExpandableObject", ExpansionOperation, Missing
        ] = Missing.MISSING,
    ) -> "Spanned[T2]":
        new_args = locals()
        kwargs = {}
        for variable in self.__slots__:
            new_value = new_args[variable]
            if new_value is Missing.MISSING:
                kwargs[variable] = getattr(self, variable)
            else:
                kwargs[variable] = new_value
        return Spanned(**kwargs)

    def __repr__(self):
        return (
            f"Spanned({self.value}, {self.span}, cursor_context={self.cursor_context}, "
            f"expansion_obj={self.expansion_obj})"
        )


Commands = Spanned[list[Spanned[CommandContext]]]
ArgContext = Union[Spanned[CommandContext], Commands, Spanned[PythonContext]]

ExpandableObject = Union[Spanned[CommandArg], ArgContext]
# https://github.com/python/mypy/issues/9424#issuecomment-687865111 :
Exp = TypeVar(
    "Exp",
    Spanned[CommandArg],
    Spanned[CommandContext],
    Commands,
    Spanned[PythonContext],
)


def with_docstr(docstr):
    def decorator(func):
        func.__doc__ = docstr
        return func

    return decorator


EMPTY_SPAN = slice(-1, -1)
RULES_SEP = "\n\t| "


@lazyobject
def NEWLINE_RE():
    return re.compile("\n")


@lazyobject
def LINE_CONT_REPLACEMENT_DIFF():
    """Returns (line_continuation, replacement, diff).
    Diff is the diff in length for each replacement.
    """
    line_cont = get_line_continuation()
    if " \\" == line_cont:
        # interactive windows
        replacement = " "
    else:
        replacement = ""
    line_cont += "\n"
    return line_cont, replacement, len(replacement) - len(line_cont)


class CompletionContextParser:
    """A parser to construct a completion context."""

    used_tokens = {
        "STRING",
    }
    paren_pairs = (
        ("DOLLAR_LPAREN", "RPAREN"),  # $()
        ("BANG_LPAREN", "RPAREN"),  # !()
        ("ATDOLLAR_LPAREN", "RPAREN"),  # @$()
        ("DOLLAR_LBRACKET", "RBRACKET"),  # $[]
        ("BANG_LBRACKET", "RBRACKET"),  # ![]
        # python sub-expression:
        ("AT_LPAREN", "RPAREN"),  # @()
    )
    r_parens = {right for _, right in paren_pairs}
    l_to_r_parens = {left: right for left, right in paren_pairs}
    used_tokens.update(left for left, _ in paren_pairs)
    used_tokens.update(right for _, right in paren_pairs)
    multi_tokens = {
        # multiple commands
        "SEMI",  # ;
        "NEWLINE",
        "PIPE",
        "AND",
        "OR",
    }
    used_tokens |= multi_tokens
    io_redir_tokens = {
        "LT",
        "GT",
        "RSHIFT",
        "IOREDIRECT1",
        "IOREDIRECT2",
    }
    used_tokens |= io_redir_tokens
    artificial_tokens = {"ANY"}
    ignored_tokens = {"INDENT", "DEDENT", "WS"}

    def __init__(
        self,
        yacc_optimize=True,
        yacc_table="xonsh.completion_parser_table",
        debug=False,
        outputdir=None,
    ):
        self.cursor = 0
        self.current_input = ""
        self.line_indices = ()
        self.paren_counts = defaultdict(int)

        self.error = None
        self.debug = debug
        self.lexer = Lexer(tolerant=True, pymode=False)
        self.tokens = tuple(self.used_tokens | self.artificial_tokens)

        yacc_kwargs = dict(
            module=self,
            debug=debug,
            optimize=yacc_optimize,
            tabmodule=yacc_table,
        )
        if not debug:
            yacc_kwargs["errorlog"] = yacc.NullLogger()
        if outputdir is None:
            outputdir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        yacc_kwargs["outputdir"] = outputdir

        # create parser on main thread, it's small and should be fast
        self.parser = yacc.yacc(**yacc_kwargs)

    def parse(
        self,
        multiline_text: str,
        cursor_index: int,
        ctx: Optional[dict[str, Any]] = None,
    ) -> Optional[CompletionContext]:
        """Returns a CompletionContext from a command line.

        Parameters
        ----------
        multiline_text : str
            The complete multiline text.
        cursor_index : int
            The current cursor's index in the multiline text.
        """
        self.cursor = cursor_index
        self.current_input = multiline_text
        self.line_indices = (0,) + tuple(
            match.start() + 1 for match in NEWLINE_RE.finditer(multiline_text)
        )
        self.paren_counts.clear()
        self.error = None

        try:
            assert self.cursor_in_span(
                slice(0, len(multiline_text))
            ), f"Bad cursor index: {cursor_index}"

            context: Optional[CompletionContext] = self.parser.parse(
                input=multiline_text, lexer=self, debug=1 if self.debug else 0
            )
        except (SyntaxError, AssertionError):
            if self.debug:
                raise
            context = None

        if self.debug and self.error is not None:
            raise self.error

        if context and ctx is not None:
            context = context.with_ctx(ctx)

        return context

    # Tokenizer:

    def input(self, s):
        return self.lexer.input(s)

    def token(self):
        """Simulate some lexer properties for the parser:
        * skip tokens from ``ignored_tokens``.
        * make ``lexpos`` absolute instead of per line.
        * set tokens that aren't in ``used_tokens`` to type ``ANY``.
        * handle a weird lexer behavior with ``AND``/``OR``.
        * set multi_tokens with cursor to type ``ANY``.
        * set mismatched closing parens to type ``ANY``.

        The paren checking is needed since accepting both matched and unmatched parenthesis isn't possible with an LALR(1) parser.
        See https://stackoverflow.com/questions/8496065/why-is-this-lr1-grammar-not-lalr1
        """
        while True:
            tok = self.lexer.token()

            if tok is None:
                return tok

            if tok.type in self.ignored_tokens:
                continue

            lineno = tok.lineno - 1  # tok.lineno is 1-indexed
            assert lineno < len(
                self.line_indices
            ), f"Invalid lexer state for token {tok} - bad lineno"

            tok.lexpos = lexpos = self.line_indices[lineno] + tok.lexpos

            if tok.type in self.multi_tokens:
                # for some reason the lexer simulates ``and`` / ``or`` values for ``&&` / ``||``
                if (
                    tok.type == "AND"
                    and self.current_input[lexpos : lexpos + 2] == "&&"
                ):
                    tok.value = "&&"
                elif (
                    tok.type == "OR" and self.current_input[lexpos : lexpos + 2] == "||"
                ):
                    tok.value = "||"

                # if the cursor is inside this token, set it to type ``ANY``
                outer_span = slice(lexpos, lexpos + len(tok.value))
                inner_span = slice(outer_span.start + 1, outer_span.stop)
                if self.cursor_in_span(inner_span) or (
                    # the cursor is in a space-separated multi keyword.
                    # even if the cursor's at the edge, the keyword should be considered as a normal arg
                    tok.value in ("and", "or") and self.cursor_in_span(outer_span)
                ):
                    tok.type = "ANY"

            # parentheses handling
            elif tok.type in self.l_to_r_parens:
                self.paren_counts[self.l_to_r_parens[tok.type]] += 1
            elif self.paren_counts.get(tok.type):
                self.paren_counts[tok.type] -= 1
            elif tok.type in self.r_parens:
                # tok.type is not in self.paren_counts, meaning this right paren is unmatched
                tok.type = "ANY"

            if tok.type in self.used_tokens:
                return tok

            tok.type = "ANY"
            return tok

    # Grammar:

    def p_context_command(self, p):
        """context : command
        | commands
        """
        spanned: Union[Spanned[CommandContext], Commands] = p[1]

        # expand the commands to the complete input
        complete_span = slice(0, len(self.current_input))
        spanned = self.try_expand_span(spanned, complete_span) or spanned

        context = spanned.cursor_context

        if isinstance(context, CommandContext):
            # if the context is the main command, it might be python code
            context_is_main_command = False
            if isinstance(spanned.value, list):
                for command in spanned.value:
                    if context is command.value:
                        # TODO: False for connecting keywords other than '\n' and ';'
                        context_is_main_command = True
                        break
            else:
                if context is spanned.value:
                    context_is_main_command = True

            if context_is_main_command:
                python_context = PythonContext(
                    multiline_code=self.current_input,
                    cursor_index=self.cursor,
                )
                p[0] = CompletionContext(command=context, python=python_context)
            else:
                p[0] = CompletionContext(command=context)
        elif isinstance(context, PythonContext):
            # the cursor is in a python sub expression `@()`, so it must be python
            p[0] = CompletionContext(python=context)
        else:
            if self.debug:
                self.error = SyntaxError(f"Failed to find cursor context in {spanned}")
            p[0] = None

    def p_command(self, p):
        """command : args
        |
        """
        if len(p) == 2:
            spanned_args: list[Spanned[CommandArg]] = p[1]
            span = slice(spanned_args[0].span.start, spanned_args[-1].span.stop)
        else:
            # empty command
            spanned_args = []
            span = EMPTY_SPAN  # this will be expanded in expand_command_span

        args = tuple(arg.value for arg in spanned_args)
        cursor_context: Optional[Union[CommandContext, PythonContext]] = None

        context = CommandContext(args, arg_index=-1)
        if self.cursor_in_span(span):
            for arg_index, arg in enumerate(spanned_args):
                if self.cursor < arg.span.start:
                    # an empty arg that will be inserted into arg_index
                    context = CommandContext(args, arg_index)
                    break
                if self.cursor_in_span(arg.span):
                    context, cursor_context = self.handle_command_arg(arg)
                    context = context._replace(
                        args=args[:arg_index] + args[arg_index + 1 :],
                        arg_index=arg_index,
                    )
                    break

        if cursor_context is None and context.arg_index != -1:
            cursor_context = context
        p[0] = Spanned(
            context,
            span,
            cursor_context,
            expansion_obj=spanned_args[-1] if spanned_args else None,
        )

    @staticmethod
    def p_multiple_commands_first(p):
        """commands : command"""
        command: Spanned[CommandContext] = p[1]
        p[0] = Spanned(
            [command],
            command.span,
            cursor_context=command.cursor_context,
        )

    @with_docstr(
        f"""commands : {RULES_SEP.join(f"commands {kwd} command" for kwd in multi_tokens)}"""
    )
    def p_multiple_commands_many(self, p):
        # commands KWD command
        commands: Commands = p[1]
        kwd_index = 2
        command: Spanned[CommandContext] = p[3]

        # expand commands span
        kwd_start = p.lexpos(kwd_index)
        commands = self.try_expand_right(commands, kwd_start) or commands

        # expand command
        kwd_stop = kwd_start + len(p[kwd_index])
        command = self.try_expand_left(command, kwd_stop) or command

        commands.value.append(command)
        expansion_obj = command

        if command.cursor_context is not None:
            cursor_context = command.cursor_context
        else:
            cursor_context = commands.cursor_context

        commands = commands.replace(
            span=slice(commands.span.start, expansion_obj.span.stop),
            cursor_context=cursor_context,
            expansion_obj=expansion_obj,
        )

        p[0] = commands

    @with_docstr(
        f"""sub_expression : {RULES_SEP.join(f"{l} commands {r}" for l, r in paren_pairs)}
        | {RULES_SEP.join(f"{l} commands" for l, _ in paren_pairs)}
    """
    )
    def p_sub_expression(self, p):
        sub_expr_opening = p[1]
        outer_start = p.lexpos(1)
        inner_start = outer_start + len(sub_expr_opening)

        commands: Commands
        if len(p) == 4:
            # LPAREN commands RPAREN
            commands = p[2]
            inner_stop = p.lexpos(3)
            outer_stop = inner_stop + len(p[3])
            closed_parens = True
        else:
            # LPAREN commands
            commands = p[2]
            if commands.span is EMPTY_SPAN:  # an empty command without a location
                inner_stop = outer_stop = inner_start
            else:
                inner_stop = outer_stop = commands.span.stop
            closed_parens = False

        inner_span = slice(inner_start, inner_stop)
        outer_span = slice(outer_start, outer_stop)

        commands = self.try_expand_span(commands, inner_span) or commands

        if len(commands.value) == 1:
            # if this is a single command, set it's subcmd_opening attribute
            single_command = commands.value[0]
            new_value: CommandContext = single_command.value._replace(
                subcmd_opening=sub_expr_opening
            )
            if commands.cursor_context is single_command.value:
                single_command = single_command.replace(cursor_context=new_value)
                commands = commands.replace(cursor_context=new_value)

            commands.value[0] = single_command.replace(value=new_value)

        if sub_expr_opening == "@(":
            # python sub-expression
            python_context = PythonContext(
                self.current_input[inner_span],
                self.cursor - inner_span.start,
                is_sub_expression=True,
            )
            if commands.cursor_context is not None and not any(
                command.value == commands.cursor_context for command in commands.value
            ):
                # the cursor is inside an inner arg
                cursor_context = commands.cursor_context
            elif self.cursor_in_span(inner_span):
                # the cursor is in the python expression
                cursor_context = python_context
            else:
                cursor_context = None

            if (
                len(commands.value)
                and commands.value[-1].expansion_obj is not None
                and self.is_command_or_commands(
                    commands.value[-1].expansion_obj.expansion_obj
                )
            ):
                # the last arg (in the last command) is a subcommand, e.g. `@(a; x = $(echo `
                expansion_obj = commands.value[-1].expansion_obj.expansion_obj
            else:
                expansion_obj = None

            p[0] = Spanned(python_context, outer_span, cursor_context, expansion_obj)
        else:
            p[0] = commands.replace(span=outer_span)

        if closed_parens:
            p[0] = p[0].replace(expansion_obj=ExpansionOperation.NEVER_EXPAND)

    def p_sub_expression_arg(self, p):
        """arg : sub_expression"""
        p[0] = self.sub_expression_arg(p[1])

    @with_docstr(
        f"""arg : {RULES_SEP.join({"ANY"} | used_tokens - multi_tokens - r_parens)}"""
    )
    def p_any_token_arg(self, p):
        raw_arg: str = p[1]
        start = p.lexpos(1)
        stop = start + len(raw_arg)
        span = slice(start, stop)

        # handle line continuations
        raw_arg, relative_cursor = self.process_string_segment(raw_arg, span)

        arg = CompletionContextParser.try_parse_string_literal(raw_arg)
        if arg is None:
            is_io_redir = p.slice[1].type in self.io_redir_tokens
            arg = CommandArg(raw_arg, is_io_redir=is_io_redir)

        p[0] = Spanned(arg, span, cursor_context=relative_cursor)

    @staticmethod
    def p_args_first(p):
        """args : arg"""
        p[0] = [p[1]]

    def p_args_many(self, p):
        """args : args arg"""
        args: list[Spanned[CommandArg]] = p[1]
        new_arg: Spanned[CommandArg] = p[2]
        last_arg: Spanned[CommandArg] = args[-1]

        in_between_span = slice(last_arg.span.stop, new_arg.span.start)
        in_between = self.current_input[in_between_span]

        # handle line continuations between these args
        in_between, relative_cursor = self.process_string_segment(
            in_between, in_between_span
        )

        joined_raw = f"{last_arg.value.raw_value}{in_between}{new_arg.value.raw_value}"
        string_literal = self.try_parse_string_literal(joined_raw)

        is_redir = new_arg.value.is_io_redir or last_arg.value.is_io_redir

        if string_literal is not None or (not in_between and not is_redir):
            if string_literal is not None:
                # we're appending to a partial string, e.g. `"a b`
                arg = string_literal
            else:
                # these args are adjacent and didn't match other rules, e.g. `a"b"`
                arg = CommandArg(joined_raw)

            # select which context to preserve
            cursor_context = None
            if relative_cursor is not None:
                # the cursor is in between
                cursor_context = len(last_arg.value.raw_value) + relative_cursor
            elif last_arg.cursor_context is not None:
                # the cursor is in the last arg
                cursor_context = last_arg.cursor_context
            elif new_arg.cursor_context is not None:
                # the cursor is in the new arg
                if isinstance(new_arg.cursor_context, int):
                    # the context is a relative cursor
                    cursor_context = (
                        len(last_arg.value.raw_value)
                        + len(in_between)
                        + new_arg.cursor_context
                    )
                else:
                    cursor_context = new_arg.cursor_context

            args[-1] = Spanned(
                value=arg,
                span=slice(last_arg.span.start, new_arg.span.stop),
                cursor_context=cursor_context,
            )
        else:
            args.append(new_arg)
        p[0] = args

    def p_error(self, p):
        if p is None:
            raise_parse_error("no further code")

        raise_parse_error(
            f"code: {p.value}",
            Location("input", p.lineno, p.lexpos - self.line_indices[p.lineno - 1]),
            self.current_input,
            self.current_input.splitlines(keepends=True),
        )

    # Utils:

    def try_expand_right(self, obj: Exp, new_right: int) -> Optional[Exp]:
        if obj.span is EMPTY_SPAN:
            new_span = slice(new_right, new_right)
        else:
            new_span = slice(obj.span.start, new_right)
        return self.try_expand_span(obj, new_span)

    def try_expand_left(self, obj: Exp, new_left: int) -> Optional[Exp]:
        if obj.span is EMPTY_SPAN:
            new_span = slice(new_left, new_left)
        else:
            new_span = slice(new_left, obj.span.stop)
        return self.try_expand_span(obj, new_span)

    def try_expand_span(self, obj: Exp, new_span: slice) -> Optional[Exp]:
        if obj.span.start <= new_span.start and new_span.stop <= obj.span.stop:
            # the new span doesn't expand the old one
            if obj.span is not EMPTY_SPAN:
                # EMPTY_SPAN is a special value for an empty element that isn't yet located anywhere
                return obj
        if obj.expansion_obj is ExpansionOperation.NEVER_EXPAND:
            return None
        elif isinstance(obj.value, CommandArg):
            return self.try_expand_arg_span(obj, new_span)
        elif isinstance(obj.value, CommandContext):
            return self.expand_command_span(obj, new_span)
        elif isinstance(obj.value, list):
            # obj is multiple commands
            return self.expand_commands_span(cast(Commands, obj), new_span)
        elif isinstance(obj.value, PythonContext):
            return self.try_expand_python_context(obj, new_span)  # type: ignore
        return None

    def expand_command_span(
        self, command: Spanned[CommandContext], new_span: slice
    ) -> Spanned[CommandContext]:
        """This is used when we know the command's real span is larger

        For example, only when we're done parsing ` echo hi`, we know the head whitespace is also part of the command.
        """
        is_empty_command = (
            command.span is EMPTY_SPAN
        )  # special span for an empty command in an unknown location

        new_arg_index = None
        if command.cursor_context is None and self.cursor_in_span(new_span):
            # the cursor is in the expanded span
            if is_empty_command or self.cursor < command.span.start:
                new_arg_index = 0
            elif self.cursor > command.span.stop:
                new_arg_index = len(command.value.args)
                if command.expansion_obj is not None:
                    # this command has a last argument that we should try to expand
                    assert isinstance(command.expansion_obj, Spanned) and isinstance(
                        command.expansion_obj.value, CommandArg
                    )
                    last_arg = cast(Spanned[CommandArg], command.expansion_obj)

                    expanded_arg = self.try_expand_right(last_arg, new_span.stop)
                    if expanded_arg is not None:
                        # arg was expanded successfully!
                        new_context, new_cursor_context = self.handle_command_arg(
                            expanded_arg
                        )
                        old_args = command.value.args
                        new_context = new_context._replace(
                            args=old_args[:-1],
                            arg_index=new_arg_index - 1,
                            subcmd_opening=command.value.subcmd_opening,
                        )
                        if new_cursor_context is None:
                            new_cursor_context = new_context
                        return Spanned(
                            value=new_context,
                            span=new_span,
                            cursor_context=new_cursor_context,
                            expansion_obj=expanded_arg,
                        )
                    # if the arg can't be expanded, the cursor just adds a new empty arg

        if new_arg_index is not None:
            new_context = command.value._replace(arg_index=new_arg_index)
            return Spanned(value=new_context, span=new_span, cursor_context=new_context)

        return command.replace(span=new_span)

    def expand_commands_span(self, commands: Commands, new_span: slice) -> Commands:
        """Like expand_command_span, but for multiple commands - expands the first command and the last command."""
        cursor_context = commands.cursor_context
        is_empty_command = commands.span is EMPTY_SPAN

        if is_empty_command or new_span.start < commands.span.start:
            # expand first command
            first_command: Spanned[CommandContext] = commands.value[0]
            commands.value[0] = first_command = (
                self.try_expand_left(first_command, new_span.start) or first_command
            )
            if first_command.cursor_context is not None:
                cursor_context = first_command.cursor_context

        if is_empty_command or new_span.stop > commands.span.stop:
            # expand last command
            last_command: Spanned[CommandContext] = commands.value[-1]
            commands.value[-1] = last_command = (
                self.try_expand_right(last_command, new_span.stop) or last_command
            )
            if last_command.cursor_context is not None:
                cursor_context = last_command.cursor_context

        return commands.replace(span=new_span, cursor_context=cursor_context)

    def try_expand_arg_span(
        self, arg: Spanned[CommandArg], new_span: slice
    ) -> Optional[Spanned[CommandArg]]:
        """Try to expand the arg to a new span. This will return None if the arg can't be expanded to the new span.

        For example, expanding `"hi   ` will work since the added whitespace is part of the arg, but `"hi"   ` won't work.
        Similarly, `$(hi ` can be expanded but `$(nice)  ` can't.
        """
        if arg.expansion_obj is ExpansionOperation.SIMPLE_ARG_EXPANSION.value:
            # this is a simple textual arg
            added_span = slice(arg.span.stop, new_span.stop)
            added_text = self.current_input[added_span]

            # handle line continuations between these args
            added_text, relative_cursor = self.process_string_segment(
                added_text, added_span
            )

            joined_raw = arg.value.raw_value + added_text
            string_literal = self.try_parse_string_literal(joined_raw)
            if string_literal is None:
                return None

            cursor_context = None
            if arg.cursor_context is not None:
                cursor_context = arg.cursor_context
            elif relative_cursor is not None:
                # the cursor is in the whitespace
                cursor_context = len(arg.value.raw_value) + relative_cursor
            return Spanned(string_literal, new_span, cursor_context)
        elif isinstance(arg.expansion_obj, Spanned):
            assert self.is_command_or_commands(arg.expansion_obj) or self.is_python(
                arg.expansion_obj
            )
            sub_expr = cast(ArgContext, arg.expansion_obj)

            # this arg is a subcommand or multiple subcommands, e.g. `$(a && b)`
            expanded_obj: Optional[ArgContext] = self.try_expand_span(  # type: ignore
                sub_expr, new_span
            )
            if expanded_obj is None:
                return None
            return self.sub_expression_arg(expanded_obj)
        else:
            # this shouldn't happen
            return None

    def try_expand_python_context(
        self, python_context: Spanned[PythonContext], new_span: slice
    ) -> Optional[Spanned[PythonContext]]:
        added_span = slice(python_context.span.stop, new_span.stop)
        added_code = self.current_input[added_span]
        new_code = python_context.value.multiline_code + added_code
        if python_context.cursor_context is None and self.cursor_in_span(added_span):
            new_cursor_index = (
                len(python_context.value.multiline_code)
                + self.cursor
                - added_span.start
            )
        else:
            new_cursor_index = python_context.value.cursor_index
        new_python_context = python_context.value._replace(
            multiline_code=new_code, cursor_index=new_cursor_index
        )

        if python_context.expansion_obj is not None:
            # the last command is expandable
            # if it were an `ExpansionOperation`, `try_expand` would caught it instead
            expandable = cast(ExpandableObject, python_context.expansion_obj)
            expanded_command: Optional[ExpandableObject] = self.try_expand_right(
                expandable, new_span.stop
            )  # type: ignore

            if (
                expanded_command is not None
                and expanded_command.cursor_context is not None
            ):
                return python_context.replace(
                    value=new_python_context,
                    span=new_span,
                    cursor_context=expanded_command.cursor_context,
                    expansion_obj=expanded_command,
                )

        # the last command can't be expanded, but the python code is still valid
        new_cursor_context: Optional[PythonContext] = None
        if self.cursor_in_span(new_span):
            new_cursor_context = new_python_context
        return python_context.replace(
            value=new_python_context, span=new_span, cursor_context=new_cursor_context
        )

    def handle_command_arg(
        self, arg: Spanned[CommandArg]
    ) -> tuple[CommandContext, Optional[Union[CommandContext, PythonContext]]]:
        """Create a command context from an arg which contains the cursor.
        Also return the internal cursor context if it exists.
        `args`, `arg_index`, and `subcmd_opening` aren't set by this function
        and need to be set by the caller via `_replace`.
        """
        assert self.cursor_in_span(arg.span)

        prefix = suffix = opening_quote = closing_quote = ""
        cursor_context = None
        is_after_closing_quote = False
        if self.cursor == arg.span.stop:
            # cursor is at the end of this arg

            if arg.cursor_context is not None and not isinstance(
                arg.cursor_context, int
            ):
                # this arg is already a context (e.g. a sub expression)
                cursor_context = arg.cursor_context

            elif arg.value.closing_quote:
                # appending to a quoted string, e.g. `ls "C:\\Wind"`
                is_after_closing_quote = True
                opening_quote = arg.value.opening_quote
                prefix = arg.value.value
                closing_quote = arg.value.closing_quote

            else:
                # appending to a partial string, e.g. `ls "C:\\Wind`
                prefix = arg.value.value
                opening_quote = arg.value.opening_quote

        elif self.cursor_in_span(arg.span):
            if arg.cursor_context is not None and not isinstance(
                arg.cursor_context, int
            ):
                # this arg is already a context (e.g. a sub expression)
                cursor_context = arg.cursor_context
            else:
                if arg.cursor_context is not None:
                    # this arg provides a relative cursor location
                    relative_location = arg.cursor_context
                else:
                    relative_location = self.cursor - arg.span.start

                raw_value = arg.value.raw_value
                if relative_location < len(arg.value.opening_quote):
                    # the cursor is inside the opening quote
                    prefix = arg.value.opening_quote[:relative_location]
                    suffix = raw_value[relative_location:]
                elif (
                    relative_location
                    >= len(arg.value.opening_quote) + len(arg.value.value) + 1
                ):
                    # the cursor is inside the closing quote
                    prefix = raw_value[:relative_location]
                    suffix = raw_value[relative_location:]
                else:
                    # the cursor is inside the string
                    opening_quote = arg.value.opening_quote
                    closing_quote = arg.value.closing_quote
                    location_in_value = relative_location - len(opening_quote)
                    prefix = arg.value.value[:location_in_value]
                    suffix = arg.value.value[location_in_value:]

        return (
            CommandContext(
                args=(),
                arg_index=-1,  # the caller needs to fill these
                prefix=prefix,
                suffix=suffix,
                opening_quote=opening_quote,
                closing_quote=closing_quote,
                is_after_closing_quote=is_after_closing_quote,
            ),
            cursor_context,
        )

    def sub_expression_arg(self, sub_expression: ArgContext) -> Spanned[CommandArg]:
        value = self.current_input[sub_expression.span]
        arg = sub_expression.replace(
            value=CommandArg(value),
            expansion_obj=sub_expression,
        )  # preserves the cursor_context and expansion_obj if it they exist
        return arg

    @staticmethod
    def try_parse_string_literal(raw_arg: str) -> Optional[CommandArg]:
        """Try to parse this as a single string literal. can be partial
        For example:
            "wow"
            "a b
            '''a b 'c' "d"
        """
        startix, endix, quote = check_for_partial_string(raw_arg)
        if startix != 0 or endix not in (
            None,  # the arg doesn't start with a string literal
            len(raw_arg),  # the string literal ends in the middle of the arg
        ):
            # xonsh won't treat it as a string literal
            return None
        else:
            if endix is None:
                # no closing quote
                return CommandArg(raw_arg[len(quote) : endix], opening_quote=quote)
            else:
                closing_quote_len = quote.count('"') + quote.count("'")
                return CommandArg(
                    value=raw_arg[len(quote) : -closing_quote_len],
                    closing_quote=raw_arg[-closing_quote_len:],
                    opening_quote=quote,
                )

    def process_string_segment(
        self, string: str, span: slice
    ) -> tuple[str, Optional[int]]:
        """Process a string segment:
        1. Return a relative_cursor if it's inside the span (for ``Spanned.cursor_context``).
        2. Handle line continuations in the string.
        """
        relative_cursor = None
        line_cont, replacement, diff = LINE_CONT_REPLACEMENT_DIFF

        if self.cursor_in_span(span):
            relative_cursor = self.cursor - span.start
            relative_cursor += string.count(line_cont, 0, relative_cursor) * diff

        string = string.replace(line_cont, replacement)

        return string, relative_cursor

    @staticmethod
    def is_command_or_commands(obj: Any) -> bool:
        if isinstance(obj, Spanned):
            if isinstance(obj.value, CommandContext):
                return True
            if isinstance(obj.value, list) and len(obj.value):
                first_element = obj.value[0]
                if isinstance(first_element, Spanned) and isinstance(
                    first_element.value, CommandContext
                ):
                    return True
        return False

    @staticmethod
    def is_python(obj: Any) -> bool:
        return isinstance(obj, Spanned) and isinstance(obj.value, PythonContext)

    def cursor_in_span(self, span: slice) -> bool:
        """Returns whether the cursor is in the span.
        The edge is included (if `self.cursor`` == ``stop``).
        """
        return span.start <= self.cursor <= span.stop
