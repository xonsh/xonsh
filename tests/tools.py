"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import builtins
import subprocess
from contextlib import contextmanager

def sp(cmd):
    return subprocess.check_output(cmd, universal_newlines=True)

@contextmanager
def mock_xonsh_env(xenv):
    builtins.__xonsh_env__ = xenv
    builtins.__xonsh_help__ = lambda x: x
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = lambda x: []
    builtins.__xonsh_subproc_captured__ = sp
    builtins.__xonsh_subproc_uncaptured__ = sp
    yield
    del builtins.__xonsh_env__
    del builtins.__xonsh_help__
    del builtins.__xonsh_superhelp__
    del builtins.__xonsh_regexpath__
    del builtins.__xonsh_subproc_captured__ 
    del builtins.__xonsh_subproc_uncaptured__ 

