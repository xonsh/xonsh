"""Pytest plugin for testing Xonsh.

These fixture names are Public API and need to be handled carefully as there are Xontribs dependent on them for testing
"""

import importlib
import sys
from pathlib import Path
from traceback import extract_tb, format_list

import pytest

from xonsh.main import setup


def pytest_configure(config):
    setup()


def pytest_collection_modifyitems(items):
    """Move xsh test first to work around a bug in normal
    pytest cleanup. The order of tests are otherwise preserved.
    """
    items.sort(key=lambda item: -isinstance(item, XshFunction))


def _limited_traceback(excinfo):
    """Return a formatted traceback with all the stack
    from this frame (i.e __file__) up removed
    """
    tb = extract_tb(excinfo.tb)
    try:
        idx = [__file__ in e for e in tb].index(True)
        return format_list(tb[idx + 1 :])
    except ValueError:
        return format_list(tb)


def pytest_collect_file(file_path: Path, parent):
    if file_path.suffix.lower() == ".xsh" and file_path.name.startswith("test_"):
        return XshFile.from_parent(parent, path=file_path)


class XshFile(pytest.File):
    def collect(self):
        sys.path.append(str(self.path.parent))
        mod = importlib.import_module(self.path.stem)
        sys.path.pop(0)
        tests = [t for t in dir(mod) if t.startswith("test_")]
        for test_name in tests:
            obj = getattr(mod, test_name)
            if hasattr(obj, "__call__"):  # noqa
                yield XshFunction.from_parent(
                    self, name=test_name, test_func=obj, test_module=mod
                )


class XshFunction(pytest.Item):
    def __init__(self, name, parent, test_func, test_module):
        super().__init__(name, parent)
        self._test_func = test_func
        self._test_module = test_module

    def runtest(self, *args, **kwargs):
        self._test_func(*args, **kwargs)

    def repr_failure(self, excinfo, **_):
        """called when self.runtest() raises an exception."""
        formatted_tb = _limited_traceback(excinfo)
        formatted_tb.insert(0, "xonsh execution failed\n")
        formatted_tb.append(f"{excinfo.type.__name__}: {excinfo.value}")
        return "".join(formatted_tb)

    def reportinfo(self):
        return self.path, 0, f"xonsh test: {self.name}"
