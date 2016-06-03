# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import sys
import glob
import builtins
import platform
import subprocess
from collections import defaultdict
from contextlib import contextmanager

from nose.plugins.skip import SkipTest

from xonsh.built_ins import ensure_list_of_strs
builtins.__xonsh_env__ = {}
from xonsh.base_shell import BaseShell


VER_3_4 = (3, 4)
VER_3_5 = (3, 5)
VER_MAJOR_MINOR = sys.version_info[:2]
VER_FULL = sys.version_info[:3]
ON_MAC = (platform.system() == 'Darwin')

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


@contextmanager
def mock_xonsh_env(xenv):
    builtins.__xonsh_env__ = xenv
    builtins.__xonsh_ctx__ = {}
    builtins.__xonsh_shell__ = DummyShell()
    builtins.__xonsh_help__ = lambda x: x
    builtins.__xonsh_glob__ = glob.glob
    builtins.__xonsh_exit__ = False
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = lambda x: []
    builtins.__xonsh_expand_path__ = lambda x: x
    builtins.__xonsh_subproc_captured__ = sp
    builtins.__xonsh_subproc_uncaptured__ = sp
    builtins.__xonsh_ensure_list_of_strs__ = ensure_list_of_strs
    builtins.evalx = eval
    builtins.execx = None
    builtins.compilex = None
    builtins.aliases = {}
    yield
    del builtins.__xonsh_env__
    del builtins.__xonsh_ctx__
    del builtins.__xonsh_shell__
    del builtins.__xonsh_help__
    del builtins.__xonsh_glob__
    del builtins.__xonsh_exit__
    del builtins.__xonsh_superhelp__
    del builtins.__xonsh_regexpath__
    del builtins.__xonsh_expand_path__
    del builtins.__xonsh_subproc_captured__
    del builtins.__xonsh_subproc_uncaptured__
    del builtins.__xonsh_ensure_list_of_strs__
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases


def skipper():
    """Raises SkipTest"""
    raise SkipTest

def skip_if(cond):
    """Skips a test under a given condition."""
    def dec(f):
        if cond:
            return skipper
        else:
            return f
    return dec
