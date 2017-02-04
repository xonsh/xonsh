"""Lazy imports that may apply across the xonsh package."""
import importlib

from xonsh.platform import ON_WINDOWS, HAS_JEDI
from xonsh.lazyasd import LazyObject, lazyobject

pygments = LazyObject(lambda: importlib.import_module('pygments'),
                      globals(), 'pygments')
pyghooks = LazyObject(lambda: importlib.import_module('xonsh.pyghooks'),
                      globals(), 'pyghooks')


@lazyobject
def pty():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module('pty')


@lazyobject
def termios():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module('termios')


@lazyobject
def fcntl():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module('fcntl')


@lazyobject
def tty():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module('tty')


@lazyobject
def _winapi():
    if ON_WINDOWS:
        import _winapi as m
    else:
        m = None
    return m


@lazyobject
def msvcrt():
    if ON_WINDOWS:
        import msvcrt as m
    else:
        m = None
    return m


@lazyobject
def winutils():
    if ON_WINDOWS:
        import xonsh.winutils as m
    else:
        m = None
    return m


@lazyobject
def terminal256():
    return importlib.import_module('pygments.formatters.terminal256')


@lazyobject
def jedi():
    if HAS_JEDI:
        import jedi as m
    else:
        m = None
    return m
