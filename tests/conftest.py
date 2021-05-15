import builtins
import glob
import os
import sys
import types
import typing as tp
from unittest.mock import MagicMock

import pytest

from xonsh.built_ins import XonshSession, XSH
from xonsh.execer import Execer
from xonsh.jobs import tasks
from xonsh.events import events
from xonsh.platform import ON_WINDOWS
from xonsh.parsers.completion_context import CompletionContextParser

from xonsh import commands_cache
from tools import DummyShell, sp, DummyEnv, DummyHistory


@pytest.fixture
def source_path():
    """Get the xonsh source path."""
    pwd = os.path.dirname(__file__)
    return os.path.dirname(pwd)


@pytest.fixture
def xonsh_execer(monkeypatch):
    """Initiate the Execer with a mocked nop `load_builtins`"""
    execer = Execer(unload=False)
    monkeypatch.setattr(XSH, "execer", execer)
    yield execer


@pytest.fixture
def patch_commands_cache_bins(xession, tmp_path, monkeypatch):
    def _factory(binaries: tp.List[str]):
        if not xession.env.get("PATH"):
            xession.env["PATH"] = [tmp_path]
        exec_mock = MagicMock(return_value=binaries)
        monkeypatch.setattr(commands_cache, "executables_in", exec_mock)
        cc = commands_cache.CommandsCache()
        xession.commands_cache = cc
        return cc

    return _factory


@pytest.fixture
def monkeypatch_stderr(monkeypatch):
    """Monkeypath sys.stderr with no ResourceWarning."""
    with open(os.devnull, "w") as fd:
        monkeypatch.setattr(sys, "stderr", fd)
        yield


@pytest.fixture
def xonsh_events():
    yield events
    for name, oldevent in vars(events).items():
        # Heavily based on transmogrification
        species = oldevent.species
        newevent = events._mkevent(name, species, species.__doc__)
        setattr(events, name, newevent)


@pytest.fixture
def xonsh_builtins(monkeypatch, xonsh_events) -> XonshSession:
    """Mock out most of the builtins xonsh attributes."""
    old_builtins = set(dir(builtins))
    XSH.load(
        execer=Execer(unload=False),
        ctx={},
        env=DummyEnv(),
        shell=DummyShell(),
        help=lambda x: x,
        aliases={},
    )
    if ON_WINDOWS:
        XSH.env["PATHEXT"] = [".EXE", ".BAT", ".CMD"]

    def locate_binary(self, name):
        return os.path.join(os.path.dirname(__file__), "bin", name)

    XSH.exit = False
    XSH.history = DummyHistory()
    XSH.subproc_captured = sp
    XSH.subproc_uncaptured = sp

    cc = XSH.commands_cache
    cc.orig_locate_binary = cc.locate_binary
    monkeypatch.setattr(cc, "locate_binary", types.MethodType(locate_binary, cc))
    XSH.subproc_captured_stdout = sp
    XSH.subproc_captured_inject = sp
    XSH.subproc_captured_object = sp
    XSH.subproc_captured_hiddenobject = sp
    # XSH.completers = None

    for attr, val in [
        ("evalx", eval),
        ("execx", None),
        ("compilex", None),
        # Unlike all the other stuff, this has to refer to the "real" one because all modules that would
        # be firing events on the global instance.
        ("events", xonsh_events),
    ]:
        monkeypatch.setattr(builtins, attr, val)
        monkeypatch.setattr(XSH.builtins, attr, val)

    # todo: remove using builtins for tests at all
    yield builtins
    XSH.unload()
    for attr in set(dir(builtins)) - old_builtins:
        if hasattr(builtins, attr):
            delattr(builtins, attr)
    tasks.clear()  # must to this to enable resetting all_jobs


@pytest.fixture
def xession(xonsh_builtins) -> XonshSession:
    return XSH


@pytest.fixture(scope="session")
def completion_context_parse():
    return CompletionContextParser().parse


def pytest_configure(config):
    """Abort test run if --flake8 requested, since it would hang on parser_test.py"""
    if config.getoption("--flake8", ""):
        pytest.exit("pytest-flake8 no longer supported, use flake8 instead.")
