import builtins
import glob
import os

import pytest

import xonsh.built_ins

from xonsh.built_ins import ensure_list_of_strs
from xonsh.execer import Execer
from xonsh.tools import XonshBlockError
from xonsh.jobs import tasks
from xonsh.events import events
from xonsh.platform import ON_WINDOWS

from tools import DummyShell, sp, DummyCommandsCache, DummyEnv, DummyHistory


@pytest.fixture
def source_path():
    """Get the xonsh source path."""
    pwd = os.path.dirname(__file__)
    return os.path.dirname(pwd)


@pytest.fixture
def xonsh_execer(monkeypatch):
    """Initiate the Execer with a mocked nop `load_builtins`"""
    monkeypatch.setattr(xonsh.built_ins, 'load_builtins',
                        lambda *args, **kwargs: None)
    execer = Execer(login=False, unload=False)
    builtins.__xonsh_execer__ = execer
    return execer


@pytest.yield_fixture
def xonsh_builtins():
    """Mock out most of the builtins xonsh attributes."""
    builtins.__xonsh_env__ = DummyEnv()
    if ON_WINDOWS:
        builtins.__xonsh_env__['PATHEXT'] = ['.EXE', '.BAT', '.CMD']
    builtins.__xonsh_ctx__ = {}
    builtins.__xonsh_shell__ = DummyShell()
    builtins.__xonsh_help__ = lambda x: x
    builtins.__xonsh_glob__ = glob.glob
    builtins.__xonsh_exit__ = False
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = lambda x: []
    builtins.__xonsh_expand_path__ = lambda x: x
    builtins.__xonsh_subproc_captured__ = sp
    builtins.__xonsh_subproc_uncaptured__ = sp
    builtins.__xonsh_stdout_uncaptured__ = None
    builtins.__xonsh_stderr_uncaptured__ = None
    builtins.__xonsh_ensure_list_of_strs__ = ensure_list_of_strs
    builtins.__xonsh_commands_cache__ = DummyCommandsCache()
    builtins.__xonsh_all_jobs__ = {}
    builtins.__xonsh_history__ = DummyHistory()
    builtins.XonshBlockError = XonshBlockError
    builtins.__xonsh_subproc_captured_hiddenobject__ = sp
    builtins.evalx = eval
    builtins.execx = None
    builtins.compilex = None
    builtins.aliases = {}
    # Unlike all the other stuff, this has to refer to the "real" one because all modules that would
    # be firing events on the global instance.
    builtins.events = events
    yield builtins
    del builtins.__xonsh_env__
    del builtins.__xonsh_ctx__
    del builtins.__xonsh_shell__
    del builtins.__xonsh_help__
    del builtins.__xonsh_glob__
    del builtins.__xonsh_exit__
    del builtins.__xonsh_superhelp__
    del builtins.__xonsh_regexpath__
    del builtins.__xonsh_expand_path__
    del builtins.__xonsh_stdout_uncaptured__
    del builtins.__xonsh_stderr_uncaptured__
    del builtins.__xonsh_subproc_captured__
    del builtins.__xonsh_subproc_uncaptured__
    del builtins.__xonsh_ensure_list_of_strs__
    del builtins.__xonsh_commands_cache__
    del builtins.__xonsh_all_jobs__
    del builtins.__xonsh_history__
    del builtins.XonshBlockError
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases
    del builtins.events
    tasks.clear()  # must to this to enable resetting all_jobs


if ON_WINDOWS:
    try:
        import win_unicode_console
    except ImportError:
        pass
    else:
        @pytest.fixture(autouse=True)
        def disable_win_unicode_console(monkeypatch):
            """ Disable win_unicode_console if it is present since it collides with
            pytests ouptput capture"""
            monkeypatch.setattr(win_unicode_console, 'enable', lambda: None)
