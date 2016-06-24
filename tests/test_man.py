# -*- coding: utf-8 -*-
import os
import tempfile

import pytest

from xonsh.tools import ON_WINDOWS
from xonsh.completers.man import complete_from_man

from tools import skip_if_on_windows

# _OLD_MANPATH = None

# def setup_module():
#     global _OLD_MANPATH
#     _OLD_MANPATH = os.environ.get('MANPATH', None)
#     os.environ['MANPATH'] = 


# def teardown_module():
#     global _OLD_MANPATH
#     if _OLD_MANPATH is None:
#         del os.environ['MANPATH']
#     else:
#         os.environ['MANPATH'] = _OLD_MANPATH


@skip_if_on_windows
def test_man_completion(monkeypatch, tmpdir, xonsh_env):
    tempdir = tmpdir.mkdir('test_man')
    monkeypatch.setitem(os.environ, 'MANPATH', os.path.dirname(os.path.abspath(__file__)))
    xonsh_env.update({'XONSH_DATA_DIR': str(tempdir)})
    completions = complete_from_man('--', 'yes --', 4, 6, __xonsh_env__)
    assert ('--version' in completions)
    assert ('--help' in completions)

