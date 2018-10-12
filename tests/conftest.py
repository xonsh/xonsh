import builtins
import glob
import os

import pytest

from xonsh.built_ins import (
    ensure_list_of_strs,
    XonshSession,
    pathsearch,
    globsearch,
    regexsearch,
    list_of_strs_or_callables,
    list_of_list_of_strs_outer_product,
    call_macro,
    enter_macro,
    path_literal,
    _BuiltIns,
)
from xonsh.execer import Execer
from xonsh.jobs import tasks
from xonsh.events import events
from xonsh.platform import ON_WINDOWS

from tools import DummyShell, sp, DummyCommandsCache, DummyEnv, DummyHistory


@pytest.fixture
def source_path():
    """Get the xonsh source path."""
    pwd = os.path.dirname(__file__)
    return os.path.dirname(pwd)


def ensure_attached_session(session):
    for i in range(1, 11):
        builtins.__xonsh__ = session
        if hasattr(builtins, "__xonsh__"):
            break
        # I have no idea why pytest fails to assign into the builtins module
        # sometimes, but the following globals trick seems to work -scopatz
        globals()["__builtins__"]["__xonsh__"] = session
        if hasattr(builtins, "__xonsh__"):
            break
    else:
        raise RuntimeError(
            "Could not attach xonsh session to builtins " "after many tries!"
        )


@pytest.fixture
def xonsh_execer(monkeypatch):
    """Initiate the Execer with a mocked nop `load_builtins`"""
    monkeypatch.setattr(
        "xonsh.built_ins.load_builtins.__code__",
        (lambda *args, **kwargs: None).__code__,
    )
    if not hasattr(builtins, "__xonsh__"):
        ensure_attached_session(XonshSession())
    execer = Execer(unload=False)
    builtins.__xonsh__.execer = execer
    return execer


@pytest.yield_fixture
def xonsh_events():
    yield events
    for name, oldevent in vars(events).items():
        # Heavily based on transmogrification
        species = oldevent.species
        newevent = events._mkevent(name, species, species.__doc__)
        setattr(events, name, newevent)


@pytest.yield_fixture
def xonsh_builtins(xonsh_events):
    """Mock out most of the builtins xonsh attributes."""
    old_builtins = set(dir(builtins))
    execer = getattr(getattr(builtins, "__xonsh__", None), "execer", None)
    session = XonshSession(execer=execer, ctx={})
    ensure_attached_session(session)
    builtins.__xonsh__.env = DummyEnv()
    if ON_WINDOWS:
        builtins.__xonsh__.env["PATHEXT"] = [".EXE", ".BAT", ".CMD"]
    builtins.__xonsh__.shell = DummyShell()
    builtins.__xonsh__.help = lambda x: x
    builtins.__xonsh__.glob = glob.glob
    builtins.__xonsh__.exit = False
    builtins.__xonsh__.superhelp = lambda x: x
    builtins.__xonsh__.pathsearch = pathsearch
    builtins.__xonsh__.globsearch = globsearch
    builtins.__xonsh__.regexsearch = regexsearch
    builtins.__xonsh__.regexpath = lambda x: []
    builtins.__xonsh__.expand_path = lambda x: x
    builtins.__xonsh__.subproc_captured = sp
    builtins.__xonsh__.subproc_uncaptured = sp
    builtins.__xonsh__.stdout_uncaptured = None
    builtins.__xonsh__.stderr_uncaptured = None
    builtins.__xonsh__.ensure_list_of_strs = ensure_list_of_strs
    builtins.__xonsh__.commands_cache = DummyCommandsCache()
    builtins.__xonsh__.all_jobs = {}
    builtins.__xonsh__.list_of_strs_or_callables = list_of_strs_or_callables
    builtins.__xonsh__.list_of_list_of_strs_outer_product = (
        list_of_list_of_strs_outer_product
    )
    builtins.__xonsh__.history = DummyHistory()
    builtins.__xonsh__.subproc_captured_stdout = sp
    builtins.__xonsh__.subproc_captured_inject = sp
    builtins.__xonsh__.subproc_captured_object = sp
    builtins.__xonsh__.subproc_captured_hiddenobject = sp
    builtins.__xonsh__.enter_macro = enter_macro
    builtins.__xonsh__.completers = None
    builtins.__xonsh__.call_macro = call_macro
    builtins.__xonsh__.enter_macro = enter_macro
    builtins.__xonsh__.path_literal = path_literal
    builtins.__xonsh__.builtins = _BuiltIns(execer=execer)
    builtins.evalx = eval
    builtins.execx = None
    builtins.compilex = None
    builtins.aliases = {}
    # Unlike all the other stuff, this has to refer to the "real" one because all modules that would
    # be firing events on the global instance.
    builtins.events = xonsh_events
    yield builtins
    for attr in set(dir(builtins)) - old_builtins:
        if hasattr(builtins, attr):
            delattr(builtins, attr)
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
            monkeypatch.setattr(win_unicode_console, "enable", lambda: None)
