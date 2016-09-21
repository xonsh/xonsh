# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import sys
import ast
import builtins
import platform
import subprocess
from collections import defaultdict

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
    assert type(x) == type(y) , "Ast nodes do not have the same type: '%s' != '%s' " % (type(x), type(y))
    if isinstance(x, (ast.Expr, ast.FunctionDef, ast.ClassDef)):
        assert x.lineno == y.lineno, "Ast nodes do not have the same line number : %s != %s" % (x.lineno, y.lineno)
        assert x.col_offset == y.col_offset, "Ast nodes do not have the same column offset number : %s != %s" % (x.col_offset, y.col_offset)
    for (xname, xval), (yname, yval) in zip(ast.iter_fields(x),
                                            ast.iter_fields(y)):
        assert xname == yname, "Ast nodes fields differ : %s (of type %s) != %s (of type %s)" % (xname, type(xval), yname, type(yval))
        assert type(xval) == type(yval), "Ast nodes fields differ : %s (of type %s) != %s (of type %s)" % (xname, type(xval), yname, type(yval))
    for xchild, ychild in zip(ast.iter_child_nodes(x),
                              ast.iter_child_nodes(y)):
        assert nodes_equal(xchild, ychild) , "Ast node children differs"
    return True
