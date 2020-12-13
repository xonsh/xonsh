"""Implements the xonsh (tab-)completion context parser.
This parser is meant to parse a (possibly incomplete) command line.
"""
import os
from typing import Optional, Tuple, List, Any, NamedTuple, Generic, TypeVar, Union

from xonsh.lexer import Lexer, _new_token
from xonsh.parsers.base import raise_parse_error, Location
from xonsh.ply.ply import yacc
from xonsh.tools import check_for_partial_string


class CommandArg(NamedTuple):
    value: str
    opening_quote: str = ""
    closing_quote: str = ""

    @property
    def raw_value(self):
        return f"{self.opening_quote}{self.value}{self.closing_quote}"


class CommandContext(NamedTuple):  # type: ignore
    args: Tuple[CommandArg, ...]
    arg_index: int = (
        -1
    )  # the current argument's index. ``-1`` if the cursor isn't in the command.

    # the current string arg
    prefix: str = ""
    suffix: str = ""
    opening_quote: str = ""
    closing_quote: str = ""

    # if this command is inside a subproc expression
    subcmd_opening: str = ""  # e.g. "$(", "![", etc


CompletionContext = Union[CommandContext]


class Span(NamedTuple):
    # inclusive on both ends
    first: int
    last: int

    def contains(self, index: int) -> bool:
        return self.first <= index <= self.last


T = TypeVar("T")


# can't use Generic + NamedTuple, can't use dataclasses for compatibility with python 3.6.


class Spanned(Generic[T]):
    def __init__(
        self, value: T, span: Span, cursor_context: Optional[CompletionContext] = None
    ):
        self.value = value
        self.span = span
        self.cursor_context = cursor_context

    def replace(self, **fields):
        kwargs = dict(
            value=self.value, span=self.span, cursor_context=self.cursor_context
        )
        kwargs.update(fields)
        return Spanned(**kwargs)


def with_docstr(docstr):
    def decorator(func):
        func.__doc__ = docstr
        return func

    return decorator


class CompletionContextParser:
    """A parser to construct a completion context."""

    used_tokens = {
        "STRING",
        # parens
        "DOLLAR_LPAREN",
        "DOLLAR_LBRACKET",
        "BANG_LPAREN",
        "BANG_LBRACKET",  # $ or !, ( or [
        "ATDOLLAR_LPAREN",  # @$(
        "RPAREN",
        "RBRACKET",  # ), ]
    }
    artificial_tokens = {"ANY", "EOF"}
    ignored_tokens = {"INDENT", "DEDENT", "WS"}

    def __init__(
        self,
        yacc_optimize=True,
        yacc_table="xonsh.completion_parser_table",
        debug=False,
        outputdir=None,
    ):
        self.cursor = 0
        self.got_eof = False
        self.current_input = ""

        self.debug = debug
        self.lexer = Lexer(tolerant=True)
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
            outputdir = os.path.dirname(os.path.realpath(__file__))
        yacc_kwargs["outputdir"] = outputdir

        # create parser on main thread, it's small and should be fast
        self.parser = yacc.yacc(**yacc_kwargs)

    def parse(
        self, multiline_text: str, cursor_index: int
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
        self.got_eof = False
        self.current_input = multiline_text

        try:
            context: Optional[Spanned[Any]] = self.parser.parse(
                input=multiline_text, lexer=self, debug=1 if self.debug else 0
            )
        except SyntaxError:
            if self.debug:
                raise
            context = None

        if context is None:
            return None

        if isinstance(context.value, CommandContext) and not context.cursor_context:
            context = self.expand_command_span(context, Span(0, len(multiline_text)))

        return context.cursor_context

    # Tokenizer:

    def input(self, s):
        return self.lexer.input(s)

    def token(self):
        while True:
            tok = self.lexer.token()

            if tok is None:
                return tok

            if tok.type in self.used_tokens:
                return tok

            if tok.type in self.ignored_tokens:
                continue

            tok.type = "ANY"
            return tok

    # Grammar:

    def p_command(self, p):
        """command : args

        sub_expression : DOLLAR_LPAREN args RPAREN
            |   DOLLAR_LPAREN args EOF
            |   BANG_LPAREN args RPAREN
            |   BANG_LPAREN args EOF
            |   ATDOLLAR_LPAREN args RPAREN
            |   ATDOLLAR_LPAREN args EOF
            |   DOLLAR_LBRACKET args RBRACKET
            |   DOLLAR_LBRACKET args EOF
            |   BANG_LBRACKET args RBRACKET
            |   BANG_LBRACKET args EOF
        """
        arg_index = -1
        prefix = suffix = opening_quote = closing_quote = subcmd_opening = ""
        cursor_context = None

        if len(p) == 2:
            spanned_args: List[Spanned[CommandArg]] = p[1]
            first = spanned_args[0].span.first
            last = spanned_args[-1].span.last
            span = Span(first, last)
        else:
            spanned_args: List[Spanned[CommandArg]] = p[2]
            subcmd_opening = p[1]
            outer_first = p.lexpos(1)
            first = outer_first + len(subcmd_opening)
            if p[3]:
                outer_last = p.lexpos(3) + len(p[3]) - 1
                last = outer_last - 1  # without the closing paren
            else:
                last = outer_last = len(self.current_input)
            span = Span(outer_first, outer_last)

        cursor = self.cursor
        if first <= cursor <= last + 1:
            for arg_index, arg in enumerate(spanned_args):
                if cursor < arg.span.first:
                    # an empty arg that will be inserted into arg_index
                    break
                if cursor == arg.span.last + 1:
                    # cursor is at the end of this arg
                    spanned_args.pop(arg_index)
                    prefix = arg.value.raw_value
                    break
                if arg.span.contains(cursor):
                    spanned_args.pop(arg_index)

                    if arg.cursor_context is not None:
                        # this arg is already a context (e.g. a sub expression)
                        cursor_context = arg.cursor_context
                        break

                    relative_location = cursor - arg.span.first
                    raw_value = arg.value.raw_value
                    if relative_location < len(arg.value.opening_quote):
                        # the cursor is inside the opening quote
                        prefix = arg.value.opening_quote[:relative_location]
                        suffix = raw_value[relative_location:]
                    elif relative_location >= len(arg.value.opening_quote) + len(
                        arg.value.value
                    ):
                        # the cursor is inside the closing quote
                        # TODO: handle appending to a quoted string
                        prefix = raw_value[:relative_location]
                        suffix = raw_value[relative_location:]
                    else:
                        # the cursor is inside the string
                        opening_quote = arg.value.opening_quote
                        closing_quote = arg.value.closing_quote
                        location_in_value = relative_location - len(opening_quote)
                        prefix = arg.value.value[:location_in_value]
                        suffix = arg.value.value[location_in_value:]
                    break
            else:
                # cursor is at a new arg that will be appended
                arg_index = len(spanned_args)

        args = tuple(arg.value for arg in spanned_args)
        context = CommandContext(
            args,
            arg_index,
            prefix,
            suffix,
            opening_quote,
            closing_quote,
            subcmd_opening,
        )
        if cursor_context is None and arg_index != -1:
            cursor_context = context
        p[0] = Spanned(context, span, cursor_context)

    def p_sub_expression_arg(self, p):
        """arg : sub_expression"""
        sub_expression: Spanned[CompletionContext] = p[1]
        value = self.current_input[
            sub_expression.span.first : sub_expression.span.last + 1
        ]
        p[0] = sub_expression.replace(
            value=CommandArg(value)
        )  # preserves the cursor_context if it exists

    @staticmethod
    def p_string_arg(p):
        """arg : STRING"""
        raw_arg = p[1]

        startix, endix, quote = check_for_partial_string(raw_arg)
        if startix != 0 or endix not in (  # the arg doesn't start with a string literal
            None,
            len(raw_arg),
        ):  # the string literal ends in the middle of the arg
            # xonsh won't treat it as a string literal
            arg = CommandArg(raw_arg)
        else:
            if endix is None:
                # no closing quote
                arg = CommandArg(raw_arg[len(quote) : endix], opening_quote=quote)
            else:
                closing_quote_len = quote.count('"') + quote.count("'")
                arg = CommandArg(
                    value=raw_arg[len(quote) : -closing_quote_len],
                    closing_quote=raw_arg[-closing_quote_len:],
                    opening_quote=quote,
                )

        first = p.lexpos(1)
        last = first + len(raw_arg) - 1
        p[0] = Spanned(arg, Span(first, last))

    @staticmethod
    @with_docstr("""arg : """ + "\n\t| ".join({"ANY"} | used_tokens - {"STRING"}))
    def p_any_arg(p):
        first = p.lexpos(1)
        last = first + len(p[1]) - 1
        p[0] = Spanned(CommandArg(p[1]), Span(first, last))

    @staticmethod
    def p_args_first(p):
        """args : arg"""
        p[0] = [p[1]]

    @staticmethod
    def p_args_many(p):
        """args : args arg"""
        args: List[Spanned[CommandArg]] = p[1]
        new_arg: Spanned[CommandArg] = p[2]
        last_arg: Spanned[CommandArg] = args[-1]

        if last_arg.span.last + 1 == new_arg.span.first:
            # these args are adjacent

            # select which context to preserve
            cursor_context = None
            if last_arg.cursor_context is not None:
                cursor_context = last_arg.cursor_context
            elif new_arg.cursor_context is not None:
                cursor_context = new_arg.cursor_context

            args[-1] = Spanned(
                value=CommandArg(last_arg.value.raw_value + new_arg.value.raw_value),
                span=Span(last_arg.span.first, new_arg.span.last),
                cursor_context=cursor_context,
            )
        else:
            args.append(new_arg)
        p[0] = args

    def p_error(self, p):
        if p is None:
            if not self.got_eof:
                # Try to send an EOF token, it might match a rule (like sub_expression)
                self.got_eof = True
                self.parser.errok()
                return _new_token("EOF", "", (0, 0))
            raise_parse_error("no further code")

        raise_parse_error(
            "code: {0}".format(p.value),
            Location("input", p.lineno, p.lexpos),
            self.current_input,
            self.current_input.splitlines(keepends=True),
        )

    # Utils:

    def expand_command_span(
        self, command: Spanned[CommandContext], new_span: Span
    ) -> Spanned[CommandContext]:
        """This is used when we know the command's real span is larger

        For example, only when we're done parsing ` echo hi`, we know the head whitespace is also part of the command.
        """
        if command.span.first <= new_span.first and new_span.last <= command.span.last:
            # the new span doesn't expand the old one
            return command

        new_arg_index = None
        if command.cursor_context is None and new_span.contains(self.cursor):
            # the cursor is in the expanded span
            if self.cursor < command.span.first:
                new_arg_index = 0
            if self.cursor > command.span.last + 1:
                new_arg_index = len(command.value.args)
            else:
                # TODO: Can this happen?
                pass

        if new_arg_index is not None:
            new_context = command.value._replace(arg_index=new_arg_index)
            return Spanned(value=new_context, span=new_span, cursor_context=new_context)

        return command.replace(span=new_span)
