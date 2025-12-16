"""Lazy imports that may apply across the xonsh package."""

import importlib
import os

from xonsh.lib.lazyasd import LazyObject, lazyobject
from xonsh.platform import ON_DARWIN, ON_WINDOWS

pygments = LazyObject(
    lambda: importlib.import_module("pygments"), globals(), "pygments"
)
pyghooks = LazyObject(
    lambda: importlib.import_module("xonsh.pyghooks"), globals(), "pyghooks"
)


@lazyobject
def pty():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module("pty")


@lazyobject
def termios():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module("termios")


@lazyobject
def fcntl():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module("fcntl")


@lazyobject
def tty():
    if ON_WINDOWS:
        return
    else:
        return importlib.import_module("tty")


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
        import xonsh.platforms.winutils as m
    else:
        m = None
    return m


@lazyobject
def macutils():
    if ON_DARWIN:
        import xonsh.platforms.macutils as m
    else:
        m = None
    return m


@lazyobject
def terminal256():
    return importlib.import_module("pygments.formatters.terminal256")


@lazyobject
def html():
    return importlib.import_module("pygments.formatters.html")


@lazyobject
def os_listxattr():
    def dummy_listxattr(*args, **kwargs):
        return []

    return getattr(os, "listxattr", dummy_listxattr)
