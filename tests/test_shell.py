# -*- coding: utf-8 -*-
"""Testing for ``xonsh.shell.Shell``"""
import os

from xonsh.environ import Env
from xonsh.shell import Shell
from xonsh.history.json import JsonHistory

def test_shell_with_json_history(xonsh_builtins, xonsh_execer, tmpdir_factory, monkeypatch):
    """
    Check that shell successfully load history from file.
    """
    tempdir = str(tmpdir_factory.mktemp("history"))

    history_file = os.path.join(tempdir, 'test_history.json')
    jh = JsonHistory(filename=history_file)
    jh.append({"inp": "echo Hello world 1\n", "rtn": 0, "ts": [1615887820.7329783, 1615887820.7513437]})
    jh.append({"inp": "echo Hello world 2\n", "rtn": 0, "ts": [1615887820.7329783, 1615887820.7513437]})
    jh.flush()

    xonsh_builtins.__xonsh__.env = Env(
        XONSH_DATA_DIR=tempdir,
        XONSH_INTERACTIVE=True,
        XONSH_HISTORY_BACKEND='json',
        XONSH_HISTORY_FILE=history_file,
        # XONSH_DEBUG=1  # to show errors
    )

    Shell(xonsh_execer, shell_type='none')

    assert len([i for i in xonsh_builtins.__xonsh__.history.all_items()]) == 2
