"""Tests the xonsh lexer."""
import ast
import copy
import os
import platform
import shutil
import subprocess
import sys
import threading
from collections import defaultdict

import pytest

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
TEST_DIR = os.path.dirname(__file__)

# pytest skip decorators
skip_if_on_conda = pytest.mark.skipif(
    ON_CONDA, reason="Conda and virtualenv _really_ hate each other"
)

skip_if_on_msys = pytest.mark.skipif(
    ON_MSYS, reason="MSYS and virtualenv _really_ hate each other"
)

skip_if_on_windows = pytest.mark.skipif(ON_WINDOWS, reason="Unix stuff")

skip_if_on_unix = pytest.mark.skipif(not ON_WINDOWS, reason="Windows stuff")

skip_if_on_darwin = pytest.mark.skipif(ON_DARWIN, reason="not Mac friendly")

skip_if_not_on_darwin = pytest.mark.skipif(not ON_DARWIN, reason="Mac only")

skip_if_on_travis = pytest.mark.skipif(ON_TRAVIS, reason="not Travis CI friendly")

skip_if_pre_3_8 = pytest.mark.skipif(VER_FULL < (3, 8), reason="Python >= 3.8 feature")

skip_if_pre_3_10 = pytest.mark.skipif(
    VER_FULL < (3, 10), reason="Python >= 3.10 feature"
)


def skip_if_not_has(exe: str):
    has_exe = shutil.which(exe)

    return pytest.mark.skipif(not has_exe, reason=f"{exe} is not available.")


def sp(cmd):
    return subprocess.check_output(cmd, universal_newlines=True)


class DummyStyler:
    styles: "dict[str, str]" = defaultdict(str)

    highlight_color = "#ffffff"
    background_color = "#000000"


class DummyBaseShell(BaseShell):
    def __init__(self):
        self.styler = DummyStyler()


class DummyShell:
    def settitle(self):
        pass

    _shell: "DummyBaseShell | None" = None

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


#
# Parser tools
#


def nodes_equal(x, y):
    __tracebackhide__ = True
    assert type(x) == type(
        y
    ), "Ast nodes do not have the same type: '{}' != '{}' ".format(
        type(x),
        type(y),
    )
    if isinstance(x, ast.Constant):
        assert (
            x.value == y.value
        ), f"Constant ast nodes do not have the same value: {repr(x.value)} != {repr(y.value)}"
    if isinstance(x, (ast.Expr, ast.FunctionDef, ast.ClassDef)):
        assert (
            x.lineno == y.lineno
        ), "Ast nodes do not have the same line number : {} != {}".format(
            x.lineno,
            y.lineno,
        )
        assert (
            x.col_offset == y.col_offset
        ), "Ast nodes do not have the same column offset number : {} != {}".format(
            x.col_offset,
            y.col_offset,
        )
    for (xname, xval), (yname, yval) in zip(ast.iter_fields(x), ast.iter_fields(y)):
        assert (
            xname == yname
        ), "Ast nodes fields differ : {} (of type {}) != {} (of type {})".format(
            xname,
            type(xval),
            yname,
            type(yval),
        )
        assert type(xval) == type(
            yval
        ), "Ast nodes fields differ : {} (of type {}) != {} (of type {})".format(
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


def copy_env(old):
    from xonsh.environ import Env, InternalEnvironDict

    env: Env = copy.copy(old)
    internal = InternalEnvironDict()
    internal._global = env._d._global.copy()
    internal._thread_local = threading.local()

    env._d = internal
    env._vars = env._vars.copy()
    env._detyped = None
    return env
