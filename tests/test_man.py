# -*- coding: utf-8 -*-
import os

import nose
from nose.tools import assert_true
from nose.plugins.skip import SkipTest

from xonsh.tools import ON_WINDOWS
from xonsh.completer import ManCompleter

from tests.tools import mock_xonsh_env

_OLD_MANPATH = None

def setup():
    global _OLD_MANPATH
    _OLD_MANPATH = os.environ.get('MANPATH', None)
    os.environ['MANPATH'] = os.path.dirname(os.path.abspath(__file__))


def teardown():
    global _OLD_MANPATH
    if _OLD_MANPATH is None:
        del os.environ['MANPATH']
    else:
        os.environ['MANPATH'] = _OLD_MANPATH


def test_man_completion():
    if ON_WINDOWS:
        raise SkipTest
    with mock_xonsh_env({}):
        man_completer = ManCompleter()
        completions = man_completer.option_complete('--', 'yes')
    assert_true('--version' in completions)
    assert_true('--help' in completions)


if __name__ == '__main__':
    nose.runmodule()
