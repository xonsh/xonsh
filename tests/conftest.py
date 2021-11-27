import builtins
import os
import sys
import types
import typing as tp
from unittest.mock import MagicMock

import pytest

from xonsh.aliases import Aliases
from xonsh.built_ins import XonshSession, XSH
from xonsh.completer import Completer
from xonsh.execer import Execer
from xonsh.jobs import tasks
from xonsh.events import events
from xonsh.parsers.completion_context import CompletionContextParser

from xonsh import commands_cache
from tools import DummyShell, sp, DummyHistory

# todo: only two fixture, xonsh, and xonsh_mocked,
#   remove all xonsh_execer, builtins, aliases ...


@pytest.fixture
def source_path():
    """Get the xonsh source path."""
    pwd = os.path.dirname(__file__)
    return os.path.dirname(pwd)


@pytest.fixture
def xonsh_execer(monkeypatch):
    """Initiate the Execer with a mocked nop `load_builtins`"""
    execer = Execer()
    XSH.load(execer=execer)
    # TODO this monkeypatch *shouldn't* be useful now.
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


@pytest.fixture(scope="session")
def session_vars():
    """keep costly vars per session"""
    from xonsh.environ import Env, default_env
    from xonsh.commands_cache import CommandsCache

    execer = Execer()
    XSH.load(execer=execer)
    return {
        "execer": execer,
        "env": Env(default_env()),
        "commands_cache": CommandsCache(),
    }


@pytest.fixture
def env():
    from xonsh.environ import Env

    initial_vars = {
        "UPDATE_OS_ENVIRON": False,
        "XONSH_DEBUG": 1,
        "XONSH_COLOR_STYLE": "default",
        "VC_BRANCH_TIMEOUT": 1,
        "XONSH_ENCODING": "utf-8",
        "XONSH_ENCODING_ERRORS": "strict",
    }
    env = Env(initial_vars)
    return env


@pytest.fixture
def xonsh_builtins(monkeypatch, xonsh_events, session_vars, env):
    """Mock out most of the builtins xonsh attributes."""
    old_builtins = dict(vars(builtins).items())  # type: ignore

    XSH.load(ctx={}, **session_vars)

    def locate_binary(self, name):
        return os.path.join(os.path.dirname(__file__), "bin", name)

    for attr, val in [
        ("env", env),
        ("shell", DummyShell()),
        ("help", lambda x: x),
        ("aliases", Aliases()),
        ("exit", False),
        ("history", DummyHistory()),
        # ("subproc_captured", sp),
        ("subproc_uncaptured", sp),
        ("subproc_captured_stdout", sp),
        ("subproc_captured_inject", sp),
        ("subproc_captured_object", sp),
        ("subproc_captured_hiddenobject", sp),
    ]:
        monkeypatch.setattr(XSH, attr, val)

    cc = XSH.commands_cache
    monkeypatch.setattr(cc, "locate_binary", types.MethodType(locate_binary, cc))
    monkeypatch.setattr(cc, "_cmds_cache", {})

    for attr, val in [
        ("evalx", eval),
        ("execx", None),
        ("compilex", None),
        # Unlike all the other stuff, this has to refer to the "real" one because all modules that would
        # be firing events on the global instance.
        ("events", xonsh_events),
    ]:
        # attributes to builtins are dynamicProxy and should pickup the following
        monkeypatch.setattr(XSH.builtins, attr, val)

    # todo: remove using builtins for tests at all
    yield builtins
    XSH.unload()
    for attr in set(dir(builtins)) - set(old_builtins):
        if hasattr(builtins, attr):
            delattr(builtins, attr)
    for attr, old_value in old_builtins.items():
        setattr(builtins, attr, old_value)

    tasks.clear()  # must to this to enable resetting all_jobs


@pytest.fixture
def xession(xonsh_builtins) -> XonshSession:
    return XSH


@pytest.fixture
def xsh_with_aliases(xession, monkeypatch):
    from xonsh.aliases import Aliases, make_default_aliases

    xsh = xession
    monkeypatch.setattr(xsh, "aliases", Aliases(make_default_aliases()))
    return xsh


@pytest.fixture(scope="session")
def completion_context_parse():
    return CompletionContextParser().parse


@pytest.fixture
def check_completer(xession):
    """Helper function to run completer and parse the results as set of strings"""
    completer = Completer()

    def _factory(line: str, prefix="", send_original=False):
        completions, _ = completer.complete_line(line, prefix=prefix)
        values = {getattr(i, "value", i).strip() for i in completions}

        if send_original:
            # just return the bare completions without appended-space for easier assertions
            return values, completions

        return values

    return _factory


@pytest.fixture
def ptk_shell(xonsh_execer):
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from xonsh.ptk_shell.shell import PromptToolkitShell

    inp = create_pipe_input()
    out = DummyOutput()
    shell = PromptToolkitShell(
        execer=xonsh_execer, ctx={}, ptk_args={"input": inp, "output": out}
    )
    yield inp, out, shell
    inp.close()


@pytest.fixture
def readline_shell(xonsh_execer, tmpdir, mocker):
    from xonsh.readline_shell import ReadlineShell

    inp_path = tmpdir / "in"
    inp = inp_path.open("w+")
    out_path = tmpdir / "out"
    out = out_path.open("w+")

    shell = ReadlineShell(execer=xonsh_execer, ctx={}, stdin=inp, stdout=out)
    mocker.patch.object(shell, "_load_remaining_input_into_queue")
    yield shell
    inp.close()
    out.close()


def pytest_configure(config):
    """Abort test run if --flake8 requested, since it would hang on parser_test.py"""
    if config.getoption("--flake8", ""):
        pytest.exit("pytest-flake8 no longer supported, use flake8 instead.")


@pytest.fixture
def load_xontrib():
    to_unload = []

    def wrapper(*names: str):
        from xonsh.xontribs import xontribs_load

        for name in names:
            module = f"xontrib.{name}"
            if module not in sys.modules:
                to_unload.append(module)

            xontribs_load([name])
        return

    yield wrapper

    for mod in to_unload:
        del sys.modules[mod]
