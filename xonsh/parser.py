# -*- coding: utf-8 -*-
"""Implements the xonsh parser."""
import collections.abc as cabc
import sys

from xonsh.ast import CtxAwareTransformer
from xonsh.lazyasd import lazyobject
from xonsh.platform import PYTHON_VERSION_INFO
from xonsh.tools import (
    subproc_toks,
    find_next_break,
    get_logical_line,
    replace_logical_line,
    balanced_parens,
    starting_whitespace,
    ends_with_colon_token,
)


@lazyobject
def StrictParser():
    if PYTHON_VERSION_INFO > (3, 10):
        from xonsh.parsers.v310 import Parser as p
    elif PYTHON_VERSION_INFO > (3, 9):
        from xonsh.parsers.v39 import Parser as p
    elif PYTHON_VERSION_INFO > (3, 8):
        from xonsh.parsers.v38 import Parser as p
    else:
        from xonsh.parsers.v36 import Parser as p
    return p


class Parser:
    def __init__(self, **strict_parser_kwargs):
        self._strict_parser = StrictParser(**strict_parser_kwargs)
        self._ctx_transformer = CtxAwareTransformer(self._strict_parser)

    @property
    def lexer(self):
        # TODO refactor the usage of this attribute
        return self._strict_parser.lexer

    def parse(
        self, input, ctx, filename="<code>", mode="exec", transform=True, debug_level=0
    ):
        """Parses xonsh code in a context-aware fashion. For context-free
        parsing, please use the Parser class directly or pass in
        transform=False.
        """
        if not transform:
            return self._strict_parser.parse(
                input, filename=filename, mode=mode, debug_level=(debug_level >= 2)
            )

        # Parsing actually happens in a couple of phases. The first is a
        # shortcut for a context-free parser. Normally, all subprocess
        # lines should be wrapped in $(), to indicate that they are a
        # subproc. But that would be super annoying. Unfortunately, Python
        # mode - after indentation - is whitespace agnostic while, using
        # the Python token, subproc mode is whitespace aware. That is to say,
        # in Python mode "ls -l", "ls-l", and "ls - l" all parse to the
        # same AST because whitespace doesn't matter to the minus binary op.
        # However, these phases all have very different meaning in subproc
        # mode. The 'right' way to deal with this is to make the entire
        # grammar whitespace aware, and then ignore all of the whitespace
        # tokens for all of the Python rules. The lazy way implemented here
        # is to parse a line a second time with a $() wrapper if it fails
        # the first time. This is a context-free phase.
        tree, input = self._parse_ctx_free(input, mode=mode, filename=filename)
        if tree is None:
            return None

        # Now we need to perform context-aware AST transformation. This is
        # because the "ls -l" is valid Python. The only way that we know
        # it is not actually Python is by checking to see if the first token
        # (ls) is part of the execution context. If it isn't, then we will
        # assume that this line is supposed to be a subprocess line, assuming
        # it also is valid as a subprocess line.
        if ctx is None:
            ctx = set()
        elif isinstance(ctx, cabc.Mapping):
            ctx = set(ctx.keys())
        tree = self._ctx_transformer.ctxvisit(
            tree, input, ctx, mode=mode, debug_level=debug_level
        )
        return tree

    def _print_debug_wrapping(
        self,
        filename,
        line,
        sbpline,
        last_error_line,
        last_error_col,
        maxcol=None,
        debug_level=0,
    ):
        """print some debugging info if asked for."""
        if debug_level >= 1:
            msg = "{0}:{1}:{2}{3} - {4}\n" "{0}:{1}:{2}{3} + {5}"
            mstr = "" if maxcol is None else ":" + str(maxcol)
            msg = msg.format(
                filename, last_error_line, last_error_col, mstr, line, sbpline
            )
            print(msg, file=sys.stderr)

    def _parse_ctx_free(
        self, input, filename="<code>", mode="exec", logical_input=False, debug_level=0
    ):
        last_error_line = last_error_col = -1
        parsed = False
        original_error = None
        greedy = False
        if logical_input:
            beg_spaces = starting_whitespace(input)
            input = input[len(beg_spaces) :]
        while not parsed:
            try:
                tree = self._strict_parser.parse(
                    input,
                    filename=filename,
                    mode=mode,
                    debug_level=(debug_level >= 2),
                )
                parsed = True
            except IndentationError as e:
                if original_error is None:
                    raise e
                else:
                    raise original_error
            except SyntaxError as e:
                if original_error is None:
                    original_error = e
                if (e.loc is None) or (
                    last_error_line == e.loc.lineno
                    and last_error_col in (e.loc.column + 1, e.loc.column)
                ):
                    raise original_error from None
                elif last_error_line != e.loc.lineno:
                    original_error = e
                last_error_col = e.loc.column
                last_error_line = e.loc.lineno
                idx = last_error_line - 1
                lines = input.splitlines()
                if input.endswith("\n"):
                    lines.append("")
                line, nlogical, idx = get_logical_line(lines, idx)
                if nlogical > 1 and not logical_input:
                    _, sbpline = self._parse_ctx_free(
                        line, mode=mode, filename=filename, logical_input=True
                    )
                    self._print_debug_wrapping(
                        filename,
                        line,
                        sbpline,
                        last_error_line,
                        last_error_col,
                        maxcol=None,
                        debug_level=debug_level,
                    )
                    replace_logical_line(lines, sbpline, idx, nlogical)
                    last_error_col += 3
                    input = "\n".join(lines)
                    continue
                if len(line.strip()) == 0:
                    # whitespace only lines are not valid syntax in Python's
                    # interactive mode='single', who knew?! Just ignore them.
                    # this might cause actual syntax errors to have bad line
                    # numbers reported, but should only affect interactive mode
                    del lines[idx]
                    last_error_line = last_error_col = -1
                    input = "\n".join(lines)
                    continue

                if last_error_line > 1 and ends_with_colon_token(lines[idx - 1]):
                    # catch non-indented blocks and raise error.
                    prev_indent = len(lines[idx - 1]) - len(lines[idx - 1].lstrip())
                    curr_indent = len(lines[idx]) - len(lines[idx].lstrip())
                    if prev_indent == curr_indent:
                        raise original_error
                lexer = self._strict_parser.lexer
                maxcol = (
                    None
                    if greedy
                    else find_next_break(line, mincol=last_error_col, lexer=lexer)
                )
                if not greedy and maxcol in (e.loc.column + 1, e.loc.column):
                    # go greedy the first time if the syntax error was because
                    # we hit an end token out of place. This usually indicates
                    # a subshell or maybe a macro.
                    if not balanced_parens(line, maxcol=maxcol):
                        greedy = True
                        maxcol = None
                sbpline = subproc_toks(
                    line, returnline=True, greedy=greedy, maxcol=maxcol, lexer=lexer
                )
                if sbpline is None:
                    # subprocess line had no valid tokens,
                    if len(line.partition("#")[0].strip()) == 0:
                        # likely because it only contained a comment.
                        del lines[idx]
                        last_error_line = last_error_col = -1
                        input = "\n".join(lines)
                        continue
                    elif not greedy:
                        greedy = True
                        continue
                    else:
                        # or for some other syntax error
                        raise original_error
                elif sbpline[last_error_col:].startswith(
                    "![!["
                ) or sbpline.lstrip().startswith("![!["):
                    # if we have already wrapped this in subproc tokens
                    # and it still doesn't work, adding more won't help
                    # anything
                    if not greedy:
                        greedy = True
                        continue
                    else:
                        raise original_error
                # replace the line
                self._print_debug_wrapping(
                    filename,
                    line,
                    sbpline,
                    last_error_line,
                    last_error_col,
                    maxcol=maxcol,
                )
                replace_logical_line(lines, sbpline, idx, nlogical)
                last_error_col += 3
                input = "\n".join(lines)
        if logical_input:
            input = beg_spaces + input
        return tree, input
