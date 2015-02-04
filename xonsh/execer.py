"""Implements the xonsh executer"""
from __future__ import print_function, unicode_literals
import re
import os
from collections import Iterable, Sequence, Mapping

from xonsh import ast
from xonsh.parser import Parser
from xonsh.tools import subproc_line

class Execer(object):
    """Executes xonsh code in a context."""

    def __init__(self, filename='<xonsh-code>', debug_level=0, 
                 parser_args=None):
        """Parameters
        ----------
        filename : str, optional
            File we are to execute.
        debug_level : int, optional
            Debugging level to use in lexing and parsing.
        parser_args : dict, optional
            Arguments to pass down to the parser.
        """
        parser_args = parser_args or {}
        self.parser = Parser(**parser_args)
        self.filename = filename
        self.debug_level = debug_level
        self.ctxtransformer = ast.CtxAwareTransformer(parser)

    def parse(self, input, ctx):
        """Parses xonsh code in a context-aware fashion. For context-free
        parsing, please use the Parser class directly.
        """
        # Parsing actually happens in a couple of phases. The first is a
        # shortcut for a context-free parser. Nomrally, all subprocess
        # lines should be wrapped in $(), to indicate that they are a 
        # subproc. But that would be super annoying. Unfortnately, Python
        # mode - after indentation - is whitespace agnostic while, using 
        # the Python token, subproc mode is whitepsace aware. That is to say,
        # in Python mode "ls -l", "ls-l", and "ls - l" all parse to the 
        # same AST because whitespace doesn't matter to the minus binary op. 
        # However, these phases all have very different meaning in subproc
        # mode. The 'right' way to deal with this is to make the entire 
        # grammar whitespace aware, and then ignore all of the whitespace
        # tokens for all of the Python rules. The lazy way implemented here
        # is to parse a line a second time with a $() wrapper if it fails
        # the first time. This is a context-free phase.
        tree = self._parse_ctx_free(input)

        # Now we need to perform context-aware AST transformation. This is 
        # because the "ls -l" is valid Python. The only way that we know 
        # it is not actually Python is by checking to see if the first token
        # (ls) is part of the execution context. If it isn't, then we will 
        # assume that this line is suppossed to be a subprocess line, assuming
        # it also is valid as a subprocess line.
        tree = self.ctxtransformer.ctxvisit(tree, input, ctx)
        return tree

    def exec(self, input, globals=None, locals=None):
        """Execute xonsh code."""
        tree = self.parse(input, locals)
        code = compile(tree, self.filename, 'exec')
        #exec(code, globals, locals)

    def _parse_ctx_free(self, input):
        last_error_line = -1
        parsed = False
        while not parsed:
            try:
                tree = self.parser.parse(input, filename=self.filename, 
                                         debug_level=self.debug_level)
                parsed = True
            except SyntaxError as e:
                if last_error_line == e.loc.lineno:
                    raise
                last_error_line = e.loc.lineno
                idx = last_error_line - 1
                lines = input.splitlines()
                lines[idx] = subproc_line(lines[idx])
                input = '\n'.join(lines)
        return tree

