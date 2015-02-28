"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import builtins
import subprocess
import glob
from contextlib import contextmanager

def sp(cmd):
    return subprocess.check_output(cmd, universal_newlines=True)

@contextmanager
def mock_xonsh_env(xenv):
    builtins.__xonsh_env__ = xenv
    builtins.__xonsh_help__ = lambda x: x
    builtins.__xonsh_glob__ = glob.glob
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = lambda x: []
    builtins.__xonsh_subproc_captured__ = sp
    builtins.__xonsh_subproc_uncaptured__ = sp
    builtins.evalx = None
    builtins.execx = None
    builtins.compilex = None
    builtins.aliases = {}
    yield
    del builtins.__xonsh_env__
    del builtins.__xonsh_help__
    del builtins.__xonsh_glob__
    del builtins.__xonsh_superhelp__
    del builtins.__xonsh_regexpath__
    del builtins.__xonsh_subproc_captured__ 
    del builtins.__xonsh_subproc_uncaptured__ 
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases

