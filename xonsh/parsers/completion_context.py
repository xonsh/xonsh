"""Implements the xonsh (tab-)completion context parser.
This parser is meant to parse a (possibly incomplete) command line.
"""
import os
import re
from typing import Optional, Tuple, List, Any, NamedTuple, Generic, TypeVar, Union

from xonsh.lazyasd import lazyobject
from xonsh.lexer import Lexer, _new_token
from xonsh.parsers.base import raise_parse_error, Location
from xonsh.ply.ply import yacc
from xonsh.tools import check_for_partial_string, get_line_continuation


class CommandArg(NamedTuple):
    value: str
    opening_quote: str = ""
    closing_quote: str = ""

    @property
    def raw_value(self):
        return f"{self.opening_quote}{self.value}{self.closing_quote}"


class CommandContext(NamedTuple):
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

T = TypeVar("T")


# can't use Generic + NamedTuple, can't use dataclasses for compatibility with python 3.6.


class Spanned(Generic[T]):
    def __init__(
        self,
        value: T,
        span: slice,
        cursor_context: Optional[Union[CompletionContext, int]] = None,
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
        """
        self.value = value
        self.span = span
        self.cursor_context = cursor_context

    def replace(self, **fields):
        kwargs = dict(
            value=self.value, span=self.span, cursor_context=self.cursor_context
        )
        kwargs.update(fields)
        return Spanned(**kwargs)

    def __repr__(self):
        return (
            f"Spanned({self.value}, {self.span}, cursor_context={self.cursor_context})"
        )


def with_docstr(docstr):
    def decorator(func):
        func.__doc__ = docstr
        return func

    return decorator


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
        self.line_indices = ()

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
        self.line_indices = (0,) + tuple(
            match.start() + 1 for match in NEWLINE_RE.finditer(multiline_text)
        )

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
            context = self.expand_command_span(context, slice(0, len(multiline_text)))

        if isinstance(context.cursor_context, int):
            # we got a relative cursor position, it's not a real context
            return None

        return context.cursor_context

    # Tokenizer:

    def input(self, s):
        return self.lexer.input(s)

    def token(self):
        """Simulate some lexer properties for the parser:
        * skip tokens from ``ignored_tokens``.
        * make ``lexpos`` absolute instead of per line.
        * set tokens that aren't in ``used_tokens`` to type ``ANY``.
        """
        while True:
            tok = self.lexer.token()

            if tok is None:
                return tok

            if tok.type in self.ignored_tokens:
                continue

            lineno = tok.lineno - 1  # tok.lineno is 1-indexed
            if lineno >= len(self.line_indices):
                raise SyntaxError(f"Invalid lexer state for token {tok} - bad lineno")

            tok.lexpos = self.line_indices[lineno] + tok.lexpos

            if tok.type in self.used_tokens:
                return tok

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
            start = spanned_args[0].span.start
            stop = spanned_args[-1].span.stop
            span = slice(start, stop)
        else:
            spanned_args: List[Spanned[CommandArg]] = p[2]
            subcmd_opening = p[1]
            outer_start = p.lexpos(1)
            start = outer_start + len(subcmd_opening)
            if p[3]:
                outer_stop = p.lexpos(3) + len(p[3])
                stop = outer_stop - 1  # without the closing paren
            else:
                stop = outer_stop = len(self.current_input)
            span = slice(outer_start, outer_stop)

        cursor = self.cursor
        if start <= cursor <= stop:
            for arg_index, arg in enumerate(spanned_args):
                if cursor < arg.span.start:
                    # an empty arg that will be inserted into arg_index
                    break
                if cursor == arg.span.stop:
                    # cursor is at the end of this arg
                    spanned_args.pop(arg_index)

                    if arg.cursor_context is not None and not isinstance(
                        arg.cursor_context, int
                    ):
                        # this arg is already a context (e.g. a sub expression)
                        cursor_context = arg.cursor_context
                        break

                    if arg.value.closing_quote:
                        # appending to a quoted string, e.g. `ls "C:\\Wind"`
                        # TODO: handle this better?
                        prefix = arg.value.raw_value
                    else:
                        # appending to a partial string, e.g. `ls "C:\\Wind`
                        prefix = arg.value.value
                        opening_quote = arg.value.opening_quote
                    break
                if arg.span.start <= cursor < arg.span.stop:
                    spanned_args.pop(arg_index)

                    if arg.cursor_context is not None:
                        if isinstance(arg.cursor_context, int):
                            # this arg provides a relative cursor location
                            relative_location = arg.cursor_context
                        else:
                            # this arg is already a context (e.g. a sub expression)
                            cursor_context = arg.cursor_context
                            break
                    else:
                        relative_location = cursor - arg.span.start

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
        value = self.current_input[sub_expression.span]
        p[0] = sub_expression.replace(
            value=CommandArg(value)
        )  # preserves the cursor_context if it exists

    @with_docstr("""arg : """ + "\n\t| ".join({"ANY"} | used_tokens))
    def p_any_token_arg(self, p):
        raw_arg: str = p[1]
        start = p.lexpos(1)
        stop = start + len(raw_arg)
        span = slice(start, stop)

        # handle line continuations
        raw_arg, relative_cursor = self.process_string_segment(raw_arg, span)

        arg = CompletionContextParser.try_parse_string_literal(raw_arg)
        if arg is None:
            arg = CommandArg(raw_arg)

        p[0] = Spanned(arg, span, cursor_context=relative_cursor)

    @staticmethod
    def p_args_first(p):
        """args : arg"""
        p[0] = [p[1]]

    def p_args_many(self, p):
        """args : args arg"""
        args: List[Spanned[CommandArg]] = p[1]
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

        if string_literal is not None or not in_between:
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
            if not self.got_eof:
                # Try to send an EOF token, it might match a rule (like sub_expression)
                self.got_eof = True
                self.parser.errok()
                return _new_token("EOF", "", (0, 0))
            raise_parse_error("no further code")

        raise_parse_error(
            "code: {0}".format(p.value),
            Location("input", p.lineno, p.lexpos - self.line_indices[p.lineno - 1]),
            self.current_input,
            self.current_input.splitlines(keepends=True),
        )

    # Utils:

    def expand_command_span(
        self, command: Spanned[CommandContext], new_span: slice
    ) -> Spanned[CommandContext]:
        """This is used when we know the command's real span is larger

        For example, only when we're done parsing ` echo hi`, we know the head whitespace is also part of the command.
        """
        if command.span.start <= new_span.start and new_span.stop <= command.span.stop:
            # the new span doesn't expand the old one
            return command

        new_arg_index = None
        if (
            command.cursor_context is None
            and new_span.start <= self.cursor <= new_span.stop
        ):
            # the cursor is in the expanded span
            if self.cursor < command.span.start:
                new_arg_index = 0
            if self.cursor > command.span.stop:
                new_arg_index = len(command.value.args)
            else:
                # TODO: Can this happen?
                pass

        if new_arg_index is not None:
            new_context = command.value._replace(arg_index=new_arg_index)
            return Spanned(value=new_context, span=new_span, cursor_context=new_context)

        return command.replace(span=new_span)

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
    ) -> Tuple[str, Optional[int]]:
        """Process a string segment:
        1. Return a relative_cursor if it's inside the span (for ``Spanned.cursor_context``).
        2. Handle line continuations in the string.
        """
        relative_cursor = None
        line_cont, replacement, diff = LINE_CONT_REPLACEMENT_DIFF

        if span.start <= self.cursor <= span.stop:
            relative_cursor = self.cursor - span.start
            relative_cursor += string.count(line_cont, 0, relative_cursor) * diff

        string = string.replace(line_cont, replacement)

        return string, relative_cursor
