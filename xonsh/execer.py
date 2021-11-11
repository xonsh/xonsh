# -*- coding: utf-8 -*-
"""Implements the xonsh executer."""
import types
import inspect
import builtins

from xonsh.parser import Parser
from xonsh.built_ins import XSH


class Execer(object):
    """Executes xonsh code in a context."""

    def __init__(
        self,
        filename="<xonsh-code>",
        debug_level=0,
        parser_args=None,
        unload=True,
        xonsh_ctx=None,
        scriptcache=True,
        cacheall=False,
    ):
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
            Xonsh xontext to load as xonsh.built_ins.XSH.ctx
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
        self._default_filename = filename
        self.debug_level = debug_level
        self.unload = unload
        self.scriptcache = scriptcache
        self.cacheall = cacheall
        XSH.load(execer=self, ctx=xonsh_ctx)

    def __del__(self):
        if self.unload:
            XSH.unload()

    def compile(
        self,
        input,
        mode="exec",
        glbs=None,
        locs=None,
        stacklevel=2,
        filename=None,
        transform=True,
    ):
        """Compiles xonsh code into a Python code object, which may then
        be execed or evaled.
        """
        if filename is None:
            filename = self.filename
            self.filename = self._default_filename
        if glbs is None or locs is None:
            frame = inspect.currentframe()
            for _ in range(stacklevel):
                frame = frame.f_back
            glbs = frame.f_globals if glbs is None else glbs
            locs = frame.f_locals if locs is None else locs
        ctx = set(dir(builtins)) | set(glbs.keys()) | set(locs.keys())
        tree = self.parser.parse(
            input,
            ctx,
            mode=mode,
            filename=filename,
            transform=transform,
            debug_level=self.debug_level,
        )
        if tree is None:
            return None  # handles comment only input
        code = compile(tree, filename, mode)
        return code

    def eval(
        self, input, glbs=None, locs=None, stacklevel=2, filename=None, transform=True
    ):
        """Evaluates (and returns) xonsh code."""
        if glbs is None:
            glbs = {}
        if isinstance(input, types.CodeType):
            code = input
        else:
            input = input.rstrip("\n")
            if filename is None:
                filename = self.filename
            code = self.compile(
                input=input,
                glbs=glbs,
                locs=locs,
                mode="eval",
                stacklevel=stacklevel,
                filename=filename,
                transform=transform,
            )
        if code is None:
            return None  # handles comment only input
        return eval(code, glbs, locs)

    def exec(
        self,
        input,
        mode="exec",
        glbs=None,
        locs=None,
        stacklevel=2,
        filename=None,
        transform=True,
    ):
        """Execute xonsh code."""
        if glbs is None:
            glbs = {}
        if isinstance(input, types.CodeType):
            code = input
        else:
            if not input.endswith("\n"):
                input += "\n"
            if filename is None:
                filename = self.filename
            code = self.compile(
                input=input,
                glbs=glbs,
                locs=locs,
                mode=mode,
                stacklevel=stacklevel,
                filename=filename,
                transform=transform,
            )
        if code is None:
            return None  # handles comment only input
        return exec(code, glbs, locs)
