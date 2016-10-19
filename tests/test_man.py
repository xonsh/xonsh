# -*- coding: utf-8 -*-
import os

from xonsh.completers.man import complete_from_man

from tools import skip_if_on_windows


@skip_if_on_windows
def test_man_completion(monkeypatch, tmpdir, xonsh_builtins):
    tempdir = tmpdir.mkdir('test_man')
    monkeypatch.setitem(os.environ, 'MANPATH', os.path.dirname(os.path.abspath(__file__)))
    xonsh_builtins.__xonsh_env__.update({'XONSH_DATA_DIR': str(tempdir)})
    completions = complete_from_man('--', 'yes --', 4, 6,
                                    xonsh_builtins.__xonsh_env__)
    assert '--version' in completions
    assert '--help' in completions
