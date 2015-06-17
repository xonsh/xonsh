import os

import nose
from nose.tools import assert_true

from xonsh.completer import ManCompleter

os.environ['MANPATH'] = os.path.dirname(os.path.abspath(__file__))

def test_man_completion():
    man_completer = ManCompleter()
    completions = man_completer.option_complete('--', 'yes')
    assert_true('--version' in completions)
    assert_true('--help' in completions)


if __name__ == '__main__':
    nose.runmodule()
