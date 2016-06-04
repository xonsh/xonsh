# -*- coding: utf-8 -*-
import os
import tempfile

import nose
from nose.tools import assert_true
from nose.plugins.skip import SkipTest

from xonsh.tools import ON_WINDOWS
from xonsh.completers.man import complete_from_man

from tools import mock_xonsh_env

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
    with tempfile.TemporaryDirectory() as tempdir:
        with mock_xonsh_env({'XONSH_DATA_DIR': tempdir}):
            completions = complete_from_man('--', 'yes --', 4, 6, __xonsh_env__)
        assert_true('--version' in completions)
        assert_true('--help' in completions)


if __name__ == '__main__':
    nose.runmodule()
