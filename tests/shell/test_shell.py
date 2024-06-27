"""Testing for ``xonsh.shells.Shell``"""

import os

from xonsh.history.dummy import DummyHistory
from xonsh.history.json import JsonHistory
from xonsh.history.sqlite import SqliteHistory
from xonsh.shells.shell import Shell


def test_shell_with_json_history(xession, tmpdir_factory):
    """
    Check that shell successfully load JSON history from file.
    """
    tempdir = str(tmpdir_factory.mktemp("history"))

    history_file = os.path.join(tempdir, "history.json")
    h = JsonHistory(filename=history_file)
    h.append(
        {
            "inp": "echo Hello world 1\n",
            "rtn": 0,
            "ts": [1615887820.7329783, 1615887820.7513437],
        }
    )
    h.append(
        {
            "inp": "echo Hello world 2\n",
            "rtn": 0,
            "ts": [1615887820.7329783, 1615887820.7513437],
        }
    )
    h.flush()

    xession.env.update(
        dict(
            XONSH_DATA_DIR=tempdir,
            XONSH_INTERACTIVE=True,
            XONSH_HISTORY_BACKEND="json",
            XONSH_HISTORY_FILE=history_file,
            # XONSH_DEBUG=1  # to show errors
        )
    )

    Shell(xession.execer, shell_type="none")

    assert len([i for i in xession.history.all_items()]) == 2


def test_shell_with_sqlite_history(xession, tmpdir_factory):
    """
    Check that shell successfully load SQLite history from file.
    """
    tempdir = str(tmpdir_factory.mktemp("history"))

    history_file = os.path.join(tempdir, "history.db")
    h = SqliteHistory(filename=history_file)
    h.append(
        {
            "inp": "echo Hello world 1\n",
            "rtn": 0,
            "ts": [1615887820.7329783, 1615887820.7513437],
        }
    )
    h.append(
        {
            "inp": "echo Hello world 2\n",
            "rtn": 0,
            "ts": [1615887820.7329783, 1615887820.7513437],
        }
    )
    h.flush()

    xession.env.update(
        dict(
            XONSH_DATA_DIR=tempdir,
            XONSH_INTERACTIVE=True,
            XONSH_HISTORY_BACKEND="sqlite",
            XONSH_HISTORY_FILE=history_file,
            # XONSH_DEBUG=1  # to show errors
        )
    )

    Shell(xession.execer, shell_type="none")

    assert len([i for i in xession.history.all_items()]) == 2


def test_shell_with_dummy_history_in_not_interactive(xession):
    """
    Check that shell use Dummy history in not interactive mode.
    """
    xession.env["XONSH_INTERACTIVE"] = False
    xession.history = None
    Shell(xession.execer, shell_type="none")
    assert isinstance(xession.history, DummyHistory)
