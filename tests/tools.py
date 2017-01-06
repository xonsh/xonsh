# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast
import builtins
import platform
import subprocess
from collections import defaultdict
from collections.abc import MutableMapping

import pytest

from xonsh.environ import Env
from xonsh.base_shell import BaseShell


VER_3_4 = (3, 4)
VER_3_5 = (3, 5)
VER_MAJOR_MINOR = sys.version_info[:2]
VER_FULL = sys.version_info[:3]
ON_DARWIN = (platform.system() == 'Darwin')
ON_WINDOWS = (platform.system() == 'Windows')
ON_CONDA = True in [conda in pytest.__file__ for conda
                    in ['anaconda', 'miniconda']]

# pytest skip decorators
skip_if_py34 = pytest.mark.skipif(VER_MAJOR_MINOR < VER_3_5, reason="Py3.5+ only test")

skip_if_on_conda = pytest.mark.skipif(ON_CONDA,
                        reason="Conda and virtualenv _really_ hate each other")

skip_if_on_windows = pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')

skip_if_on_unix = pytest.mark.skipif(not ON_WINDOWS, reason='Windows stuff')

skip_if_on_darwin = pytest.mark.skipif(ON_DARWIN, reason='not Mac friendly')


def sp(cmd):
    return subprocess.check_output(cmd, universal_newlines=True)


class DummyStyler():
    styles = defaultdict(None.__class__)


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


class DummyCommandsCache:

    def locate_binary(self, name):
        return os.path.join(os.path.dirname(__file__), 'bin', name)

    def predict_threadable(self, cmd):
        return True


class DummyHistory:

    last_cmd_rtn = 0
    last_cmd_out = ''

    def append(self, x):
        pass


class DummyEnv(MutableMapping):

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)

    def detype(self):
        return {k: str(v) for k, v in self._d.items()}

    def __getitem__(self, k):
        return self._d[k]

    def __setitem__(self, k, v):
        self._d[k] = v

    def __delitem__(self, k):
        del self._d[k]

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        yield from self._d

#
# Execer tools
#


def check_exec(input, **kwargs):
    if not input.endswith('\n'):
        input += '\n'
    builtins.__xonsh_execer__.exec(input, **kwargs)
    return True


def check_eval(input):
    builtins.__xonsh_env__ = Env({'AUTO_CD': False, 'XONSH_ENCODING': 'utf-8',
                                  'XONSH_ENCODING_ERRORS': 'strict', 'PATH': []})
    if ON_WINDOWS:
        builtins.__xonsh_env__['PATHEXT'] = ['.COM', '.EXE', '.BAT', '.CMD']
    builtins.__xonsh_execer__.eval(input)
    return True


def check_parse(input):
    tree = builtins.__xonsh_execer__.parse(input, ctx=None)
    return tree

#
# Parser tools
#


def nodes_equal(x, y):
    __tracebackhide__ = True
    assert type(x) == type(y), "Ast nodes do not have the same type: '%s' != '%s' " % (type(x), type(y))
    if isinstance(x, (ast.Expr, ast.FunctionDef, ast.ClassDef)):
        assert x.lineno == y.lineno, "Ast nodes do not have the same line number : %s != %s" % (x.lineno, y.lineno)
        assert x.col_offset == y.col_offset, "Ast nodes do not have the same column offset number : %s != %s" % (x.col_offset, y.col_offset)
    for (xname, xval), (yname, yval) in zip(ast.iter_fields(x),
                                            ast.iter_fields(y)):
        assert xname == yname, "Ast nodes fields differ : %s (of type %s) != %s (of type %s)" % (xname, type(xval), yname, type(yval))
        assert type(xval) == type(yval), "Ast nodes fields differ : %s (of type %s) != %s (of type %s)" % (xname, type(xval), yname, type(yval))
    for xchild, ychild in zip(ast.iter_child_nodes(x),
                              ast.iter_child_nodes(y)):
        assert nodes_equal(xchild, ychild), "Ast node children differs"
    return True
