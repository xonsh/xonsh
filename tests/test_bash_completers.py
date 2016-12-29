"""Tests delegation to bash completers"""
import pytest
import os

from xonsh.environ import Env

from xonsh.completers.bash import complete_from_bash

COMPLETION_DIR = os.path.join(os.path.dirname(__file__), 'bash_completion.d')
COMPLETION_FILE1 = os.path.join(COMPLETION_DIR, 'spam')
COMPLETION_FILE2 = os.path.join(COMPLETION_DIR, 'foo')

def test_single_completion_file(xonsh_builtins):
    """This tests an issue surfacing in Python 3.6:
    commonprefix() only works on indexable arguments, see http://bugs.python.org/issue28527
    """
    xonsh_builtins.__xonsh_env__ = Env(BASH_COMPLETIONS=[COMPLETION_FILE1])
    completions = complete_from_bash('spam --', 'spam --', 5, 5, None)
    assert completions == ({'--bacon ', '--sausage ', '--egg ', '--spam '}, 2)

def test_multiple_completion_files(xonsh_builtins):
    """Tests if all sources available in the environment are used, not just the first one"""
    xonsh_builtins.__xonsh_env__ = Env(BASH_COMPLETIONS=[COMPLETION_FILE1, COMPLETION_FILE2])
    completions = complete_from_bash('foo --', 'foo --', 5, 5, None)
    assert completions == ({'--bar ', '--baz ', '--qux '}, 2)
