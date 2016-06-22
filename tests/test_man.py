# -*- coding: utf-8 -*-
import os
import tempfile

import pytest

from xonsh.tools import ON_WINDOWS
from xonsh.completers.man import complete_from_man

from tools import mock_xonsh_env

_OLD_MANPATH = None

def setup_module():
    global _OLD_MANPATH
    _OLD_MANPATH = os.environ.get('MANPATH', None)
    os.environ['MANPATH'] = os.path.dirname(os.path.abspath(__file__))


def teardown_module():
    global _OLD_MANPATH
    if _OLD_MANPATH is None:
        del os.environ['MANPATH']
    else:
        os.environ['MANPATH'] = _OLD_MANPATH


@pytest.mark.skipif(ON_WINDOWS, reason='No man completions on Windows')
def test_man_completion():
    with tempfile.TemporaryDirectory() as tempdir:
        with mock_xonsh_env({'XONSH_DATA_DIR': tempdir}):
            completions = complete_from_man('--', 'yes --', 4, 6, __xonsh_env__)
        assert ('--version' in completions)
        assert ('--help' in completions)
