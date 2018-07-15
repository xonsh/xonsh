# -*- coding: utf-8 -*-
"""Pytest plugin for testing xsh files."""
import sys
import importlib
from traceback import format_list, extract_tb

import pytest

from xonsh.imphooks import install_import_hooks


def pytest_configure(config):
    install_import_hooks()


def pytest_collection_modifyitems(items):
    items.sort(key=lambda x: 0 if isinstance(x, XshFunction) else 1)


def _limited_traceback(excinfo):
    """ Return a formatted traceback with all the stack
        from this frame (i.e __file__) up removed
    """
    tb = extract_tb(excinfo.tb)
    try:
        idx = [__file__ in e for e in tb].index(True)
        return format_list(tb[idx + 1:])
    except ValueError:
        return format_list(tb)


def pytest_collect_file(parent, path):
    if path.ext.lower() == ".xsh" and path.basename.startswith("test_"):
        return XshFile(path, parent)


class XshFile(pytest.File):
    def collect(self):
        sys.path.append(self.fspath.dirname)
        mod = importlib.import_module(self.fspath.purebasename)
        sys.path.pop(0)
        tests = [t for t in dir(mod) if t.startswith('test_')]
        for test_name in tests:
            obj = getattr(mod, test_name)
            if hasattr(obj, '__call__'):
                yield XshFunction(name=test_name, parent=self,
                                  test_func=obj, test_module=mod)


class XshFunction(pytest.Item):
    def __init__(self, name, parent, test_func, test_module):
        super().__init__(name, parent)
        self._test_func = test_func
        self._test_module = test_module

    def runtest(self, *args, **kwargs):
        self._test_func(*args, **kwargs)

    def repr_failure(self, excinfo):
        """ called when self.runtest() raises an exception. """
        formatted_tb = _limited_traceback(excinfo)
        formatted_tb.insert(0, "xonsh execution failed\n")
        formatted_tb.append('{}: {}'.format(excinfo.type.__name__, excinfo.value))
        return "".join(formatted_tb)

    def reportinfo(self):
        return self.fspath, 0, "xonsh test: {}".format(self.name)
