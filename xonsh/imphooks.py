# -*- coding: utf-8 -*-
"""Import hooks for importing xonsh source files.

This module registers the hooks it defines when it is imported.
"""
import builtins
import os
import sys
import types
from importlib.machinery import ModuleSpec
from importlib.abc import MetaPathFinder, SourceLoader

from xonsh.execer import Execer
from xonsh.platform import scandir


class XonshImportHook(MetaPathFinder, SourceLoader):
    """Implements the import hook for xonsh source files."""

    def __init__(self, *args, **kwargs):
        super(XonshImportHook, self).__init__(*args, **kwargs)
        self._filenames = {}
        self._execer = None

    @property
    def execer(self):
        if hasattr(builtins, '__xonsh_execer__'):
            execer = builtins.__xonsh_execer__
            if self._execer is not None:
                self._execer = None
        elif self._execer is None:
            self._execer = execer = Execer(unload=False)
        else:
            execer = self._execer
        return execer

    #
    # MetaPathFinder methods
    #
    def find_spec(self, fullname, path, target=None):
        """Finds the spec for a xonsh module if it exists."""
        dot = '.'
        spec = None
        path = sys.path if path is None else path
        if dot not in fullname and dot not in path:
            path = [dot] + path
        name = fullname.rsplit(dot, 1)[-1]
        fname = name + '.xsh'
        for p in path:
            if not isinstance(p, str):
                continue
            if not os.path.isdir(p) or not os.access(p, os.R_OK):
                continue
            if fname not in (x.name for x in scandir(p)):
                continue
            spec = ModuleSpec(fullname, self)
            self._filenames[fullname] = os.path.join(p, fname)
            break
        return spec

    #
    # SourceLoader methods
    #
    def create_module(self, spec):
        """Create a xonsh module with the appropriate attributes."""
        mod = types.ModuleType(spec.name)
        mod.__file__ = self.get_filename(spec.name)
        mod.__loader__ = self
        mod.__package__ = spec.parent or ''
        return mod

    def get_filename(self, fullname):
        """Returns the filename for a module's fullname."""
        return self._filenames[fullname]

    def get_data(self, path):
        """Gets the bytes for a path."""
        raise NotImplementedError

    def get_code(self, fullname):
        """Gets the code object for a xonsh file."""
        filename = self.get_filename(fullname)
        if filename is None:
            msg = "xonsh file {0!r} could not be found".format(fullname)
            raise ImportError(msg)
        with open(filename, 'r') as f:
            src = f.read()
        src = src if src.endswith('\n') else src + '\n'
        execer = self.execer
        execer.filename = filename
        ctx = {}  # dummy for modules
        code = execer.compile(src, glbs=ctx, locs=ctx)
        return code


def install_hook():
    """
    Install Xonsh import hook in `sys.metapath` in order for `.xsh` files to be
    importable.

    Can safely be called many times, will be no-op if a xonsh import hook is
    already present.
    """
    for hook in sys.meta_path:
        if isinstance(hook, XonshImportHook):
            break
    else:
        sys.meta_path.append(XonshImportHook())
