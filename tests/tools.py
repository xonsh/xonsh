# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import sys
import builtins
import platform
import subprocess
from collections import defaultdict

import pytest

from xonsh.environ import Env
from xonsh.base_shell import BaseShell
from xonsh.tools import XonshBlockError  # noqa: F401


VER_3_4 = (3, 4)
VER_3_5 = (3, 5)
VER_MAJOR_MINOR = sys.version_info[:2]
VER_FULL = sys.version_info[:3]
ON_DARWIN = (platform.system() == 'Darwin')
ON_WINDOWS = (platform.system() == 'Windows')


# pytest skip decorators
skip_if_py34 = pytest.mark.skipif(VER_MAJOR_MINOR < VER_3_5, reason="Py3.5+ only test")

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
