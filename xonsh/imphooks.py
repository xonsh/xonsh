# -*- coding: utf-8 -*-
"""Import hooks for importing xonsh source files.

This module registers the hooks it defines when it is imported.
"""
import os
import re
import sys
import types
import builtins
import contextlib
import importlib
from importlib.machinery import ModuleSpec
from importlib.abc import MetaPathFinder, SourceLoader, Loader

from xonsh.events import events
from xonsh.execer import Execer
from xonsh.platform import scandir
from xonsh.lazyasd import lazyobject


@lazyobject
def ENCODING_LINE():
    # this regex comes from PEP 263
    # https://www.python.org/dev/peps/pep-0263/#defining-the-encoding
    return re.compile(b"^[ tv]*#.*?coding[:=][ t]*([-_.a-zA-Z0-9]+)")


def find_source_encoding(src):
    """Finds the source encoding given bytes representing a file. If
    no encoding is found, UTF-8 will be returned as per the docs
    https://docs.python.org/3/howto/unicode.html#unicode-literals-in-python-source-code
    """
    utf8 = "UTF-8"
    first, _, rest = src.partition(b"\n")
    m = ENCODING_LINE.match(first)
    if m is not None:
        return m.group(1).decode(utf8)
    second, _, _ = rest.partition(b"\n")
    m = ENCODING_LINE.match(second)
    if m is not None:
        return m.group(1).decode(utf8)
    return utf8


class XonshImportHook(MetaPathFinder, SourceLoader):
    """Implements the import hook for xonsh source files."""

    def __init__(self, *args, **kwargs):
        super(XonshImportHook, self).__init__(*args, **kwargs)
        self._filenames = {}
        self._execer = None

    @property
    def execer(self):
        if (
            hasattr(builtins, "__xonsh__")
            and hasattr(builtins.__xonsh__, "execer")
            and builtins.__xonsh__.execer is not None
        ):
            execer = builtins.__xonsh__.execer
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
        dot = "."
        spec = None
        path = sys.path if path is None else path
        if dot not in fullname and dot not in path:
            path = [dot] + path
        name = fullname.rsplit(dot, 1)[-1]
        fname = name + ".xsh"
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
        mod.__package__ = spec.parent or ""
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
        with open(filename, "rb") as f:
            src = f.read()
        enc = find_source_encoding(src)
        src = src.decode(encoding=enc)
        src = src if src.endswith("\n") else src + "\n"
        execer = self.execer
        execer.filename = filename
        ctx = {}  # dummy for modules
        code = execer.compile(src, glbs=ctx, locs=ctx)
        return code


#
# Import events
#
events.doc(
    "on_import_pre_find_spec",
    """
on_import_pre_find_spec(fullname: str, path: str, target: module or None) -> None

Fires before any import find_spec() calls have been executed. The parameters
here are the same as importlib.abc.MetaPathFinder.find_spec(). Namely,

:``fullname``: The full name of the module to import.
:``path``: None if a top-level import, otherwise the ``__path__`` of the parent
          package.
:``target``: Target module used to make a better guess about the package spec.
""",
)

events.doc(
    "on_import_post_find_spec",
    """
on_import_post_find_spec(spec, fullname, path, target) -> None

Fires after all import find_spec() calls have been executed. The parameters
here the spec and the arguments importlib.abc.MetaPathFinder.find_spec(). Namely,

:``spec``: A ModuleSpec object if the spec was found, or None if it was not.
:``fullname``: The full name of the module to import.
:``path``: None if a top-level import, otherwise the ``__path__`` of the parent
          package.
:``target``: Target module used to make a better guess about the package spec.
""",
)

events.doc(
    "on_import_pre_create_module",
    """
on_import_pre_create_module(spec: ModuleSpec) -> None

Fires right before a module is created by its loader. The only parameter
is the spec object. See importlib for more details.
""",
)

events.doc(
    "on_import_post_create_module",
    """
on_import_post_create_module(module: Module, spec: ModuleSpec) -> None

Fires after a module is created by its loader but before the loader returns it.
The parameters here are the module object itself and the spec object.
See importlib for more details.
""",
)

events.doc(
    "on_import_pre_exec_module",
    """
on_import_pre_exec_module(module: Module) -> None

Fires right before a module is executed by its loader. The only parameter
is the module itself. See importlib for more details.
""",
)

events.doc(
    "on_import_post_exec_module",
    """
on_import_post_create_module(module: Module) -> None

Fires after a module is executed by its loader but before the loader returns it.
The only parameter is the module itself. See importlib for more details.
""",
)


def _should_dispatch_xonsh_import_event_loader():
    """Figures out if we should dispatch to a load event"""
    return (
        len(events.on_import_pre_create_module) > 0
        or len(events.on_import_post_create_module) > 0
        or len(events.on_import_pre_exec_module) > 0
        or len(events.on_import_post_exec_module) > 0
    )


class XonshImportEventHook(MetaPathFinder):
    """Implements the import hook for firing xonsh events on import."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fullname_stack = []

    @contextlib.contextmanager
    def append_stack(self, fullname):
        """A context manager for appending and then removing a name from the
        fullname stack.
        """
        self._fullname_stack.append(fullname)
        yield
        del self._fullname_stack[-1]

    #
    # MetaPathFinder methods
    #
    def find_spec(self, fullname, path, target=None):
        """Finds the spec for a xonsh module if it exists."""
        if fullname in reversed(self._fullname_stack):
            # don't execute if we are already in the stack.
            return None
        npre = len(events.on_import_pre_find_spec)
        npost = len(events.on_import_post_find_spec)
        dispatch_load = _should_dispatch_xonsh_import_event_loader()
        if npre > 0:
            events.on_import_pre_find_spec.fire(
                fullname=fullname, path=path, target=target
            )
        elif npost == 0 and not dispatch_load:
            # no events to fire, proceed normally and prevent recursion
            return None
        # now find the spec
        with self.append_stack(fullname):
            spec = importlib.util.find_spec(fullname)
        # fire post event
        if npost > 0:
            events.on_import_post_find_spec.fire(
                spec=spec, fullname=fullname, path=path, target=target
            )
        if dispatch_load and spec is not None and hasattr(spec.loader, "create_module"):
            spec.loader = XonshImportEventLoader(spec.loader)
        return spec


class XonshImportEventLoader(Loader):
    """A class that dispatches loader calls to another loader and fires relevant
    xonsh events.
    """

    def __init__(self, loader):
        self.loader = loader

    #
    # Loader methods
    #
    def create_module(self, spec):
        """Creates and returns the module object."""
        events.on_import_pre_create_module.fire(spec=spec)
        mod = self.loader.create_module(spec)
        events.on_import_post_create_module.fire(module=mod, spec=spec)
        return mod

    def exec_module(self, module):
        """Executes the module in its own namespace."""
        events.on_import_pre_exec_module.fire(module=module)
        rtn = self.loader.exec_module(module)
        events.on_import_post_exec_module.fire(module=module)
        return rtn

    def load_module(self, fullname):
        """Legacy module loading, provided for backwards compatibility."""
        return self.loader.load_module(fullname)

    def module_repr(self, module):
        """Legacy module repr, provided for backwards compatibility."""
        return self.loader.module_repr(module)


def install_import_hooks():
    """
    Install Xonsh import hooks in ``sys.meta_path`` in order for ``.xsh`` files
    to be importable and import events to be fired.

    Can safely be called many times, will be no-op if xonsh import hooks are
    already present.
    """
    found_imp = found_event = False
    for hook in sys.meta_path:
        if isinstance(hook, XonshImportHook):
            found_imp = True
        elif isinstance(hook, XonshImportEventHook):
            found_event = True
    if not found_imp:
        sys.meta_path.append(XonshImportHook())
    if not found_event:
        sys.meta_path.insert(0, XonshImportEventHook())


# alias to deprecated name
install_hook = install_import_hooks
