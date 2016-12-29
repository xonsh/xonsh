"""Tests delegation to bash completers"""
import pytest
import os

from xonsh.environ import Env

from xonsh.completers.bash import complete_from_bash

COMPLETION_DIR = os.path.join(os.path.dirname(__file__), 'bash_completion.d')
COMPLETION_FILE = os.path.join(COMPLETION_DIR, 'spam')

def test_single_completion_file(xonsh_builtins):
    """This tests an issue surfacing in Python 3.6:
    commonprefix() only works on indexable arguments, see http://bugs.python.org/issue28527
    """
    xonsh_builtins.__xonsh_env__ = Env(BASH_COMPLETIONS=[COMPLETION_FILE])
    completions = complete_from_bash('spam --', 'spam --', 5, 5, None)
    assert completions == ({'--bacon ', '--sausage ', '--egg ', '--spam '}, 2)
