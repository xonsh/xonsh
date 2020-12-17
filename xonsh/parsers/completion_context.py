"""Implements the xonsh (tab-)completion context parser.
This parser is meant to parse a (possibly incomplete) command line.
"""
import os
import re
from typing import Optional, Tuple, List, NamedTuple, Generic, TypeVar, Union, Any

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


Commands = Spanned[List[Spanned[CommandContext]]]


def with_docstr(docstr):
    def decorator(func):
        func.__doc__ = docstr
        return func

    return decorator


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
    )
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

        self.error = None
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
        self.error = None

        try:
            context: Optional[CompletionContext] = self.parser.parse(
                input=multiline_text, lexer=self, debug=1 if self.debug else 0
            )
        except SyntaxError:
            if self.debug:
                raise
            context = None

        if self.debug and self.error is not None:
            raise self.error

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

            tok.lexpos = lexpos = self.line_indices[lineno] + tok.lexpos

            # for some reason the lexer simulates ``and`` / ``or`` values for ``&&` / ``||``
            if tok.type == "AND" and self.current_input[lexpos : lexpos + 2] == "&&":
                tok.value = "&&"
            elif tok.type == "OR" and self.current_input[lexpos : lexpos + 2] == "||":
                tok.value = "||"

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

        if spanned.cursor_context is None:
            complete_span = slice(0, len(self.current_input))
            if isinstance(spanned.value, list):
                spanned = self.expand_commands_span(spanned, complete_span)
            else:
                spanned = self.expand_command_span(spanned, complete_span)

        context = spanned.cursor_context

        if context is None or isinstance(context, int):
            # we got a relative cursor position, it's not a real context
            context = None
            if self.debug:
                self.error = SyntaxError(f"Failed to find cursor context in {spanned}")
        p[0] = context

    precedence = (
        ("left", *set(r for _, r in paren_pairs)),
        ("left", *multi_tokens),
        ("left", "SINGLE_COMMAND"),  # fictitious token (see p_command)
    )

    def p_command(self, p):
        """command : args %prec SINGLE_COMMAND
        | EOF
        """
        if p[1]:
            spanned_args: List[Spanned[CommandArg]] = p[1]
            span = slice(spanned_args[0].span.start, spanned_args[-1].span.stop)
        else:
            # EOF - we need to create an empty command
            spanned_args = []
            eof_position = p.lexpos(1)
            span = slice(
                eof_position, eof_position
            )  # this will be expanded in ``parse``
        p[0] = self.create_command(spanned_args, span)

    @with_docstr(
        f"""commands : {RULES_SEP.join(f"args {kwd} args" for kwd in multi_tokens)}
        | {RULES_SEP.join(f"args {kwd}" for kwd in multi_tokens)}
        | {RULES_SEP.join(f"{kwd} args" for kwd in multi_tokens)}
        | {RULES_SEP.join(f"{kwd}" for kwd in multi_tokens)}
    """
    )
    def p_multiple_commands_first(self, p):
        first_index, second_index = None, None
        if len(p) == 4:
            # args KWD args
            first_index, kwd_index, second_index = 1, 2, 3
        elif len(p) == 3:
            if isinstance(p[1], list):
                # args KWD
                first_index, kwd_index = 1, 2
            else:
                # KWD args
                kwd_index, second_index = 1, 2
        else:
            # KWD
            kwd_index = 1

        # create first command
        kwd_start = p.lexpos(kwd_index)
        if first_index is not None:
            first_args: List[Spanned[CommandArg]] = p[first_index]
            first_command = self.create_command(
                first_args, slice(first_args[0].span.start, kwd_start)
            )
        else:
            first_args = []
            first_command = self.create_command([], slice(kwd_start, kwd_start))

        # create second command
        kwd_stop = kwd_start + len(p[kwd_index])
        if second_index is not None:
            second_args: List[Spanned[CommandArg]] = p[second_index]
            second_command = self.create_command(
                second_args, slice(kwd_stop, second_args[-1].span.stop)
            )
        else:
            second_args = []
            second_command = self.create_command([], slice(kwd_stop, kwd_stop))

        commands_list = [first_command, second_command]

        kwd_span = slice(kwd_start, kwd_stop)
        if p[kwd_index] in ("and", "or") and self.cursor_in_span(kwd_span):
            # the cursor is in a space-separated multi keyword.
            # even if the cursor's at the edge, the keyword should be considered as a normal arg,
            # so let's trigger that flow:
            first_command = first_command.replace(cursor_context=None)
            second_command = second_command.replace(cursor_context=None)

        # resolve cursor context
        cursor_context = None
        if first_command.cursor_context is not None:
            cursor_context = first_command.cursor_context
        elif second_command.cursor_context is not None:
            cursor_context = second_command.cursor_context
        elif self.cursor_in_span(kwd_span):
            args = (
                first_args + [Spanned(CommandArg(p[kwd_index]), kwd_span)] + second_args
            )
            span = slice(first_command.span.start, second_command.span.stop)
            commands_list = [self.create_command(args, span)]
            cursor_context = commands_list[0].cursor_context

        commands: Commands = Spanned(
            commands_list,
            span=slice(first_command.span.start, second_command.span.stop),
            cursor_context=cursor_context,
        )
        p[0] = commands

    @with_docstr(
        f"""commands : {RULES_SEP.join(f"commands {kwd} args" for kwd in multi_tokens)}
        | {RULES_SEP.join(f"commands {kwd}" for kwd in multi_tokens)}"""
    )
    def p_multiple_commands_many(self, p):
        if len(p) == 4:
            # commands KWD args
            kwd_index = 2
            command_args: List[Spanned[CommandArg]] = p[3]
        else:
            # commands KWD
            kwd_index = 1
            command_args = []

        commands: Commands = p[1]

        # expand commands span
        kwd_start = p.lexpos(kwd_index)
        commands = self.expand_commands_span(
            commands, slice(commands.span.start, kwd_start)
        )

        # create new command
        kwd_stop = kwd_start + len(p[kwd_index])
        if command_args:
            new_command_span = slice(kwd_stop, command_args[-1].span.stop)
        else:
            new_command_span = slice(kwd_stop, kwd_stop)
        new_command = self.create_command(command_args, new_command_span)

        commands.value.append(new_command)

        kwd_span = slice(kwd_start, kwd_stop)
        if p[kwd_index] in ("and", "or") and self.cursor_in_span(kwd_span):
            # the cursor is in a space-separated multi keyword.
            # even if the cursor's at the edge, the keyword should be considered as a normal arg,
            # so let's trigger that flow:
            new_command = new_command.replace(cursor_context=None)
            commands = commands.replace(cursor_context=None)

        if new_command.cursor_context is not None:
            commands = commands.replace(cursor_context=new_command.cursor_context)
        elif commands.cursor_context is None and self.cursor_in_span(kwd_span):
            # the cursor is in the keyword.
            # join the last command with the new command and treat the keyword as a normal arg.
            new_command = commands.value.pop()
            last_command = commands.value.pop()
            middle_command = self.create_command(
                [Spanned(CommandArg(p[kwd_index]), kwd_span)], kwd_span
            )
            joined_command = Spanned(
                value=middle_command.value._replace(
                    args=last_command.value.args
                    + middle_command.value.args
                    + new_command.value.args,
                    arg_index=len(last_command.value.args)
                    + middle_command.value.arg_index,
                ),
                span=slice(last_command.span.start, new_command.span.stop),
            )
            context = joined_command.value
            joined_command.cursor_context = context
            commands.value.append(joined_command)
            commands = commands.replace(cursor_context=context)

        p[0] = commands

    @with_docstr(
        f"""sub_expression : {RULES_SEP.join(f"{l} args {r}" for l, r in paren_pairs)}
        | {RULES_SEP.join(f"{l} {r}" for l, r in paren_pairs)}
        | {RULES_SEP.join(f"{l} args EOF" for l, _ in paren_pairs)}
        | {RULES_SEP.join(f"{l} EOF" for l, _ in paren_pairs)}
    """
    )
    def p_subcommand(self, p):
        if len(p) == 4:
            # LPAREN args RPAREN/EOF
            spanned_args: List[Spanned[CommandArg]] = p[2]
            closing_token_index = 3
        else:
            # LPAREN RPAREN/EOF
            spanned_args: List[Spanned[CommandArg]] = []
            closing_token_index = 2

        subcmd_opening = p[1]

        outer_start = p.lexpos(1)
        inner_start = outer_start + len(subcmd_opening)
        inner_stop = p.lexpos(closing_token_index)
        outer_stop = inner_stop + len(p[closing_token_index])  # len(EOF) == 0
        inner_span = slice(inner_start, inner_stop)
        outer_span = slice(outer_start, outer_stop)

        command = self.create_command(spanned_args, inner_span, subcmd_opening)
        p[0] = command.replace(span=outer_span)

    @with_docstr(
        f"""sub_expression : {RULES_SEP.join(f"{l} commands {r}" for l, r in paren_pairs)}
        | {RULES_SEP.join(f"{l} commands EOF" for l, _ in paren_pairs)}
    """
    )
    def p_subcommand_multiple(self, p):
        # LPAREN commands RPAREN/EOF
        commands: Commands = p[2]

        subcmd_opening = p[1]

        outer_start = p.lexpos(1)
        inner_start = outer_start + len(subcmd_opening)
        inner_stop = p.lexpos(3)
        outer_stop = inner_stop + len(p[3])  # len(EOF) == 0
        inner_span = slice(inner_start, inner_stop)
        outer_span = slice(outer_start, outer_stop)

        commands = self.expand_commands_span(commands, inner_span)
        p[0] = commands.replace(span=outer_span)

    def create_command(
        self,
        spanned_args: List[Spanned[CommandArg]],
        span: slice,
        subcmd_opening: str = "",
    ) -> Spanned[CommandContext]:
        arg_index = -1
        prefix = suffix = opening_quote = closing_quote = ""
        cursor_context = None
        if self.cursor_in_span(span):
            for arg_index, arg in enumerate(spanned_args):
                if self.cursor < arg.span.start:
                    # an empty arg that will be inserted into arg_index
                    break
                if self.cursor == arg.span.stop:
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
                if self.cursor_in_span(arg.span):
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
        return Spanned(context, span, cursor_context)

    def p_sub_expression_arg(self, p):
        """arg : sub_expression"""
        sub_expression: Spanned[Any] = p[1]
        value = self.current_input[sub_expression.span]
        p[0] = sub_expression.replace(
            value=CommandArg(value)
        )  # preserves the cursor_context if it exists

    @with_docstr(f"""arg : {RULES_SEP.join({"ANY"} | used_tokens - multi_tokens)}""")
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
                return _new_token("EOF", "", (0, len(self.current_input)))
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
        if command.cursor_context is None and self.cursor_in_span(new_span):
            # the cursor is in the expanded span
            if self.cursor < command.span.start:
                new_arg_index = 0
            if self.cursor > command.span.stop:
                new_arg_index = len(command.value.args)

        if new_arg_index is not None:
            new_context = command.value._replace(arg_index=new_arg_index)
            return Spanned(value=new_context, span=new_span, cursor_context=new_context)

        return command.replace(span=new_span)

    def expand_commands_span(self, commands: Commands, new_span: slice) -> Commands:
        """Like expand_command_span, but for multiple commands - expands the first command and the last command."""
        cursor_context = commands.cursor_context

        if new_span.start < commands.span.start:
            # expand first command
            first_command = commands.value[0]
            commands.value[0] = first_command = self.expand_command_span(
                first_command, slice(new_span.start, first_command.span.stop)
            )
            if first_command.cursor_context is not None:
                cursor_context = first_command.cursor_context

        if new_span.stop > commands.span.stop:
            # expand last command
            last_command = commands.value[-1]
            commands.value[-1] = last_command = self.expand_command_span(
                last_command, slice(last_command.span.start, new_span.stop)
            )
            if last_command.cursor_context is not None:
                cursor_context = last_command.cursor_context

        return commands.replace(span=new_span, cursor_context=cursor_context)

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

        if self.cursor_in_span(span):
            relative_cursor = self.cursor - span.start
            relative_cursor += string.count(line_cont, 0, relative_cursor) * diff

        string = string.replace(line_cont, replacement)

        return string, relative_cursor

    def cursor_in_span(self, span: slice) -> bool:
        """Returns whether the cursor is in the span.
        The edge is included (if `self.cursor`` == ``stop``).
        """
        return span.start <= self.cursor <= span.stop
