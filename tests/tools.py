# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast
import platform
import subprocess
import contextlib
from collections import defaultdict
from collections.abc import MutableMapping

import pytest

from xonsh.built_ins import XSH
from xonsh.environ import Env
from xonsh.base_shell import BaseShell


VER_MAJOR_MINOR = sys.version_info[:2]
VER_FULL = sys.version_info[:3]
ON_DARWIN = platform.system() == "Darwin"
ON_WINDOWS = platform.system() == "Windows"
ON_MSYS = sys.platform == "msys"
ON_CONDA = True in [
    conda in pytest.__file__.lower() for conda in ["conda", "anaconda", "miniconda"]
]
ON_TRAVIS = "TRAVIS" in os.environ and "CI" in os.environ
ON_AZURE_PIPELINES = os.environ.get("TF_BUILD", "") == "True"
print("ON_AZURE_PIPELINES", repr(ON_AZURE_PIPELINES))
print("os.environ['TF_BUILD']", repr(os.environ.get("TF_BUILD", "")))
TEST_DIR = os.path.dirname(__file__)

# pytest skip decorators
skip_if_on_conda = pytest.mark.skipif(
    ON_CONDA, reason="Conda and virtualenv _really_ hate each other"
)

skip_if_on_msys = pytest.mark.skipif(
    ON_MSYS, reason="MSYS and virtualenv _really_ hate each other"
)

skip_if_on_windows = pytest.mark.skipif(ON_WINDOWS, reason="Unix stuff")

skip_if_on_azure_pipelines = pytest.mark.skipif(
    ON_AZURE_PIPELINES, reason="not suitable for azure"
)

skip_if_on_unix = pytest.mark.skipif(not ON_WINDOWS, reason="Windows stuff")

skip_if_on_darwin = pytest.mark.skipif(ON_DARWIN, reason="not Mac friendly")

skip_if_on_travis = pytest.mark.skipif(ON_TRAVIS, reason="not Travis CI friendly")

skip_if_pre_3_8 = pytest.mark.skipif(VER_FULL < (3, 8), reason="Python >= 3.8 feature")


def sp(cmd):
    return subprocess.check_output(cmd, universal_newlines=True)


class DummyStyler:
    styles = defaultdict(str)

    highlight_color = "#ffffff"
    background_color = "#000000"


class DummyBaseShell(BaseShell):
    def __init__(self):
        self.styler = DummyStyler()


class DummyShell:
    def settitle(self):
        pass

    _shell = None

    @property
    def shell(self):
        if self._shell is None:
            self._shell = DummyBaseShell()
        return self._shell


class DummyHistory:

    last_cmd_rtn = 0
    last_cmd_out = ""

    def append(self, x):
        pass

    def flush(self, *args, **kwargs):
        pass


class DummyEnv(MutableMapping):

    DEFAULTS = {
        "XONSH_DEBUG": 1,
        "XONSH_COLOR_STYLE": "default",
        "VC_BRANCH_TIMEOUT": 1,
    }

    def __init__(self, *args, **kwargs):
        self._d = self.DEFAULTS.copy()
        self._d.update(dict(*args, **kwargs))

    def detype(self):
        return {k: str(v) for k, v in self._d.items()}

    def __getitem__(self, k):
        if k is ...:
            return self
        else:
            return self._d[k]

    def __setitem__(self, k, v):
        assert k is not ...
        self._d[k] = v

    def __delitem__(self, k):
        assert k is not ...
        del self._d[k]

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        yield from self._d

    @contextlib.contextmanager
    def swap(self, other=None, **kwargs):
        old = {}
        # single positional argument should be a dict-like object
        if other is not None:
            for k, v in other.items():
                old[k] = self.get(k, NotImplemented)
                self[k] = v
        # kwargs could also have been sent in
        for k, v in kwargs.items():
            old[k] = self.get(k, NotImplemented)
            self[k] = v
        yield self
        # restore the values
        for k, v in old.items():
            if v is NotImplemented:
                del self[k]
            else:
                self[k] = v

    def is_manually_set(self, key):
        return False


#
# Execer tools
#


def check_exec(input, **kwargs):
    XSH.execer.exec(input, **kwargs)
    return True


def check_eval(input):
    XSH.env = Env(
        {
            "AUTO_CD": False,
            "XONSH_ENCODING": "utf-8",
            "XONSH_ENCODING_ERRORS": "strict",
            "PATH": [],
        }
    )
    if ON_WINDOWS:
        XSH.env["PATHEXT"] = [".COM", ".EXE", ".BAT", ".CMD"]
    XSH.execer.eval(input)
    return True


def check_parse(input):
    tree = XSH.execer.parse(input, ctx=None)
    return tree


#
# Parser tools
#


def nodes_equal(x, y):
    __tracebackhide__ = True
    assert type(x) == type(y), "Ast nodes do not have the same type: '%s' != '%s' " % (
        type(x),
        type(y),
    )
    if isinstance(x, (ast.Expr, ast.FunctionDef, ast.ClassDef)):
        assert (
            x.lineno == y.lineno
        ), "Ast nodes do not have the same line number : %s != %s" % (
            x.lineno,
            y.lineno,
        )
        assert (
            x.col_offset == y.col_offset
        ), "Ast nodes do not have the same column offset number : %s != %s" % (
            x.col_offset,
            y.col_offset,
        )
    for (xname, xval), (yname, yval) in zip(ast.iter_fields(x), ast.iter_fields(y)):
        assert (
            xname == yname
        ), "Ast nodes fields differ : %s (of type %s) != %s (of type %s)" % (
            xname,
            type(xval),
            yname,
            type(yval),
        )
        assert type(xval) == type(
            yval
        ), "Ast nodes fields differ : %s (of type %s) != %s (of type %s)" % (
            xname,
            type(xval),
            yname,
            type(yval),
        )
    for xchild, ychild in zip(ast.iter_child_nodes(x), ast.iter_child_nodes(y)):
        assert nodes_equal(xchild, ychild), "Ast node children differs"
    return True


def completions_from_result(results):
    if isinstance(results, tuple):
        results, lprefix = results
    if results is None:
        return set()
    return results
