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

from xonsh.built_ins import ensure_list_of_strs
from xonsh.environ import Env
builtins.__xonsh_env__ = Env()
from xonsh.base_shell import BaseShell
from xonsh.execer import Execer
from xonsh.tools import XonshBlockError


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


class FakeEnv(dict):
    pass

@contextmanager
def mock_xonsh_env(xenv):
    fenv = FakeEnv(xenv)
    fenv.detype = lambda: {}
    builtins.__xonsh_env__ = fenv
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
    builtins.XonshBlockError = XonshBlockError
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
    del builtins.XonshBlockError
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases


#
# Execer tools
#

DEBUG_LEVEL = 0
EXECER = None

def execer_setup():
    # only setup one parser
    global EXECER
    if EXECER is None:
        EXECER = Execer(debug_level=DEBUG_LEVEL, login=False)

def check_exec(input, **kwargs):
    with mock_xonsh_env(None):
        if not input.endswith('\n'):
            input += '\n'
        EXECER.debug_level = DEBUG_LEVEL
        EXECER.exec(input, **kwargs)

def check_eval(input):
    with mock_xonsh_env({'AUTO_CD': False, 'XONSH_ENCODING' :'utf-8',
                         'XONSH_ENCODING_ERRORS': 'strict', 'PATH': []}):
        EXECER.debug_level = DEBUG_LEVEL
        EXECER.eval(input)

def check_parse(input):
    with mock_xonsh_env(None):
        EXECER.debug_level = DEBUG_LEVEL
        tree = EXECER.parse(input, ctx=None)
    return tree

