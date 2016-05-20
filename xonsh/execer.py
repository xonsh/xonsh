# -*- coding: utf-8 -*-
"""Implements the xonsh executer."""
import re
import types
import inspect
import builtins
from collections import Mapping

from xonsh import ast
from xonsh.parser import Parser
from xonsh.tools import (subproc_toks, END_TOK_TYPES, LPARENS,
    _is_not_lparen_and_rparen)
from xonsh.built_ins import load_builtins, unload_builtins


RE_END_TOKS = re.compile('(;|and|\&\&|or|\|\||\))')

class Execer(object):
    """Executes xonsh code in a context."""

    def __init__(self, filename='<xonsh-code>', debug_level=0, parser_args=None,
                 unload=True, config=None, login=True, xonsh_ctx=None):
        """Parameters
        ----------
        filename : str, optional
            File we are to execute.
        debug_level : int, optional
            Debugging level to use in lexing and parsing.
        parser_args : dict, optional
            Arguments to pass down to the parser.
        unload : bool, optional
            Whether or not to unload xonsh builtins upon deletion.
        config : str, optional
            Path to configuration file.
        xonsh_ctx : dict or None, optional
            Xonsh xontext to load as builtins.__xonsh_ctx__
        """
        parser_args = parser_args or {}
        self.parser = Parser(**parser_args)
        self.filename = filename
        self.debug_level = debug_level
        self.unload = unload
        self.ctxtransformer = ast.CtxAwareTransformer(self.parser)
        load_builtins(execer=self, config=config, login=login, ctx=xonsh_ctx)

    def __del__(self):
        if self.unload:
            unload_builtins()

    def parse(self, input, ctx, mode='exec'):
        """Parses xonsh code in a context-aware fashion. For context-free
        parsing, please use the Parser class directly.
        """
        if ctx is None:
            ctx = set()
        elif isinstance(ctx, Mapping):
            ctx = set(ctx.keys())

        # Parsing actually happens in a couple of phases. The first is a
        # shortcut for a context-free parser. Normally, all subprocess
        # lines should be wrapped in $(), to indicate that they are a
        # subproc. But that would be super annoying. Unfortnately, Python
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
        tree, input = self._parse_ctx_free(input, mode=mode)
        if tree is None:
            return None

        # Now we need to perform context-aware AST transformation. This is
        # because the "ls -l" is valid Python. The only way that we know
        # it is not actually Python is by checking to see if the first token
        # (ls) is part of the execution context. If it isn't, then we will
        # assume that this line is supposed to be a subprocess line, assuming
        # it also is valid as a subprocess line.
        tree = self.ctxtransformer.ctxvisit(tree, input, ctx, mode=mode)
        return tree

    def compile(self, input, mode='exec', glbs=None, locs=None, stacklevel=2,
                filename=None):
        """Compiles xonsh code into a Python code object, which may then
        be execed or evaled.
        """
        if filename is None:
            filename = self.filename
        if glbs is None or locs is None:
            frame = inspect.stack()[stacklevel][0]
            glbs = frame.f_globals if glbs is None else glbs
            locs = frame.f_locals if locs is None else locs
        ctx = set(dir(builtins)) | set(glbs.keys()) | set(locs.keys())
        tree = self.parse(input, ctx, mode=mode)
        if tree is None:
            return None  # handles comment only input
        code = compile(tree, filename, mode)
        return code

    def eval(self, input, glbs=None, locs=None, stacklevel=2):
        """Evaluates (and returns) xonsh code."""
        if isinstance(input, types.CodeType):
            code = input
        else:
            code = self.compile(input=input,
                                glbs=glbs,
                                locs=locs,
                                mode='eval',
                                stacklevel=stacklevel)
        if code is None:
            return None  # handles comment only input
        return eval(code, glbs, locs)

    def exec(self, input, mode='exec', glbs=None, locs=None, stacklevel=2):
        """Execute xonsh code."""
        if isinstance(input, types.CodeType):
            code = input
        else:
            code = self.compile(input=input,
                                glbs=glbs,
                                locs=locs,
                                mode=mode,
                                stacklevel=stacklevel)
        if code is None:
            return None  # handles comment only input
        return exec(code, glbs, locs)

    def _find_next_break(self, line, mincol):
        if mincol >= 1:
            line = line[mincol:]
        if RE_END_TOKS.search(line) is None:
            return None
        maxcol = None
        lparens = []
        self.parser.lexer.input(line)
        for tok in self.parser.lexer:
            if tok.type in LPARENS:
                lparens.append(tok.type)
            elif tok.type in END_TOK_TYPES:
                if _is_not_lparen_and_rparen(lparens, tok):
                    lparens.pop()
                else:
                    maxcol = tok.lexpos + mincol + 1
                    break
            elif tok.type == 'ERRORTOKEN' and ')' in tok.value:
                maxcol = tok.lexpos + mincol + 1
                break
        return maxcol

    def _parse_ctx_free(self, input, mode='exec'):
        last_error_line = last_error_col = -1
        parsed = False
        original_error = None
        while not parsed:
            try:
                tree = self.parser.parse(input,
                                         filename=self.filename,
                                         mode=mode,
                                         debug_level=self.debug_level)
                parsed = True
            except IndentationError as e:
                if original_error is None:
                    raise e
                else:
                    raise original_error
            except SyntaxError as e:
                if original_error is None:
                    original_error = e
                if (e.loc is None) or (last_error_line == e.loc.lineno and
                                       last_error_col in (e.loc.column + 1,
                                                          e.loc.column)):
                    raise original_error
                last_error_col = e.loc.column
                last_error_line = e.loc.lineno
                idx = last_error_line - 1
                lines = input.splitlines()
                line = lines[idx]
                if input.endswith('\n'):
                    lines.append('')
                if len(line.strip()) == 0:
                    # whitespace only lines are not valid syntax in Python's
                    # interactive mode='single', who knew?! Just ignore them.
                    # this might cause actual sytax errors to have bad line
                    # numbers reported, but should only effect interactive mode
                    del lines[idx]
                    last_error_line = last_error_col = -1
                    input = '\n'.join(lines)
                    continue

                if last_error_line > 1 and lines[idx-1].rstrip()[-1:] == ':':
                    # catch non-indented blocks and raise error.
                    prev_indent = len(lines[idx-1]) - len(lines[idx-1].lstrip())
                    curr_indent = len(lines[idx]) - len(lines[idx].lstrip())
                    if prev_indent == curr_indent:
                        raise original_error
                maxcol = self._find_next_break(line, last_error_col)
                sbpline = subproc_toks(line,
                                       returnline=True,
                                       maxcol=maxcol,
                                       lexer=self.parser.lexer)
                if sbpline is None:
                    # subprocess line had no valid tokens,
                    if len(line.partition('#')[0].strip()) == 0:
                        # likely because it only contained a comment.
                        del lines[idx]
                        last_error_line = last_error_col = -1
                        input = '\n'.join(lines)
                        continue
                    else:
                        # or for some other syntax error
                        raise original_error
                elif sbpline[last_error_col:].startswith('![![') or \
                     sbpline.lstrip().startswith('![!['):
                    # if we have already wrapped this in subproc tokens
                    # and it still doesn't work, adding more won't help
                    # anything
                    raise original_error
                else:
                    lines[idx] = sbpline
                last_error_col += 3
                input = '\n'.join(lines)
        return tree, input
