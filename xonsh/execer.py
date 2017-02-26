# -*- coding: utf-8 -*-
"""Implements the xonsh executer."""
import sys
import types
import inspect
import builtins
import collections.abc as cabc

from xonsh.ast import CtxAwareTransformer
from xonsh.parser import Parser
from xonsh.tools import (subproc_toks, find_next_break, get_logical_line,
                         replace_logical_line)
from xonsh.built_ins import load_builtins, unload_builtins


class Execer(object):
    """Executes xonsh code in a context."""

    def __init__(self, filename='<xonsh-code>', debug_level=0, parser_args=None,
                 unload=True, xonsh_ctx=None, scriptcache=True, cacheall=False):
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
        xonsh_ctx : dict or None, optional
            Xonsh xontext to load as builtins.__xonsh_ctx__
        scriptcache : bool, optional
            Whether or not to use a precompiled bytecode cache when execing
            code, default: True.
        cacheall : bool, optional
            Whether or not to cache all xonsh code, and not just files. If this
            is set to true, it will cache command line input too, default: False.
        """
        parser_args = parser_args or {}
        self.parser = Parser(**parser_args)
        self.filename = filename
        self.debug_level = debug_level
        self.unload = unload
        self.scriptcache = scriptcache
        self.cacheall = cacheall
        self.ctxtransformer = CtxAwareTransformer(self.parser)
        load_builtins(execer=self, ctx=xonsh_ctx)

    def __del__(self):
        if self.unload:
            unload_builtins()

    def parse(self, input, ctx, mode='exec', filename=None, transform=True):
        """Parses xonsh code in a context-aware fashion. For context-free
        parsing, please use the Parser class directly or pass in
        transform=False.
        """
        if filename is None:
            filename = self.filename
        if not transform:
            return self.parser.parse(input, filename=filename, mode=mode,
                                     debug_level=(self.debug_level > 2))

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
        tree = self.ctxtransformer.ctxvisit(tree, input, ctx, mode=mode,
                                            debug_level=self.debug_level)
        return tree

    def compile(self, input, mode='exec', glbs=None, locs=None, stacklevel=2,
                filename=None, transform=True):
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
        tree = self.parse(input, ctx, mode=mode, filename=filename,
                          transform=transform)
        if tree is None:
            return None  # handles comment only input
        code = compile(tree, filename, mode)
        return code

    def eval(self, input, glbs=None, locs=None, stacklevel=2,
             filename=None, transform=True):
        """Evaluates (and returns) xonsh code."""
        if isinstance(input, types.CodeType):
            code = input
        else:
            if filename is None:
                filename = self.filename
            code = self.compile(input=input,
                                glbs=glbs,
                                locs=locs,
                                mode='eval',
                                stacklevel=stacklevel,
                                filename=filename,
                                transform=transform)
        if code is None:
            return None  # handles comment only input
        return eval(code, glbs, locs)

    def exec(self, input, mode='exec', glbs=None, locs=None, stacklevel=2,
             filename=None, transform=True):
        """Execute xonsh code."""
        if isinstance(input, types.CodeType):
            code = input
        else:
            if filename is None:
                filename = self.filename
            code = self.compile(input=input,
                                glbs=glbs,
                                locs=locs,
                                mode=mode,
                                stacklevel=stacklevel,
                                filename=filename,
                                transform=transform)
        if code is None:
            return None  # handles comment only input
        return exec(code, glbs, locs)

    def _parse_ctx_free(self, input, mode='exec', filename=None):
        last_error_line = last_error_col = -1
        parsed = False
        original_error = None
        greedy = False
        if filename is None:
            filename = self.filename
        while not parsed:
            try:
                tree = self.parser.parse(input,
                                         filename=filename,
                                         mode=mode,
                                         debug_level=(self.debug_level > 2))
                parsed = True
            except IndentationError as e:
                if original_error is None:
                    raise e
                else:
                    raise original_error
            except SyntaxError as e:
                if original_error is None:
                    original_error = e
                if not greedy:
                    greedy = True
                elif (e.loc is None) or (last_error_line == e.loc.lineno and
                                         last_error_col in (e.loc.column + 1,
                                                            e.loc.column)):
                    raise original_error from None
                last_error_col = e.loc.column
                last_error_line = e.loc.lineno
                idx = last_error_line - 1
                lines = input.splitlines()
                line, nlogical = get_logical_line(lines, idx)
                if input.endswith('\n'):
                    lines.append('')
                if len(line.strip()) == 0:
                    # whitespace only lines are not valid syntax in Python's
                    # interactive mode='single', who knew?! Just ignore them.
                    # this might cause actual sytax errors to have bad line
                    # numbers reported, but should only affect interactive mode
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
                lexer = self.parser.lexer
                maxcol = None if greedy else find_next_break(line,
                                                             mincol=last_error_col,
                                                             lexer=lexer)
                sbpline = subproc_toks(line, returnline=True, greedy=greedy,
                                       maxcol=maxcol, lexer=lexer)
                if sbpline is None:
                    # subprocess line had no valid tokens,
                    if len(line.partition('#')[0].strip()) == 0:
                        # likely because it only contained a comment.
                        del lines[idx]
                        last_error_line = last_error_col = -1
                        input = '\n'.join(lines)
                        continue
                    elif not greedy:
                        greedy = True
                        continue
                    else:
                        # or for some other syntax error
                        raise original_error
                elif sbpline[last_error_col:].startswith('![![') or \
                        sbpline.lstrip().startswith('![!['):
                    # if we have already wrapped this in subproc tokens
                    # and it still doesn't work, adding more won't help
                    # anything
                    if not greedy:
                        greedy = True
                        continue
                    else:
                        raise original_error
                else:
                    # print some debugging info
                    if self.debug_level > 1:
                        msg = ('{0}:{1}:{2}{3} - {4}\n'
                               '{0}:{1}:{2}{3} + {5}')
                        mstr = '' if maxcol is None else ':' + str(maxcol)
                        msg = msg.format(self.filename, last_error_line,
                                         last_error_col, mstr, line, sbpline)
                        print(msg, file=sys.stderr)
                    # replace the line
                    replace_logical_line(lines, sbpline, idx, nlogical)
                last_error_col += 3
                input = '\n'.join(lines)
        return tree, input
