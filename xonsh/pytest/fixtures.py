"""Fixtures that doesn't need XSH setup"""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

from xonsh import commands_cache
from xonsh.aliases import Aliases
from xonsh.built_ins import XSH, XonshSession
from xonsh.completer import Completer
from xonsh.events import events
from xonsh.execer import Execer
from xonsh.parsers.completion_context import CompletionContextParser
from xonsh.procs.jobs import get_tasks

from .tools import DummyHistory, DummyShell, copy_env, mock_env, sp


@pytest.fixture
def source_path():
    """Get the xonsh source path."""
    pwd = os.path.dirname(__file__)
    return os.path.dirname(pwd)


@pytest.fixture
def xonsh_execer(monkeypatch, xonsh_session):
    """Initiate the Execer with a mocked nop `load_builtins`"""
    yield xonsh_session.execer


@pytest.fixture
def xonsh_execer_exec(xonsh_execer):
    def factory(input, **kwargs):
        xonsh_execer.exec(input, **kwargs)
        return True

    return factory


@pytest.fixture
def xonsh_execer_parse(xonsh_execer):
    def factory(input):
        tree = XSH.execer.parse(input, ctx=None)
        return tree

    return factory


@pytest.fixture
def mock_executables_in(xession, tmp_path, monkeypatch):
    def _factory(binaries: list[str]):
        xession.env["PATH"] = [tmp_path]
        exec_mock = MagicMock(return_value=binaries)
        monkeypatch.setattr(commands_cache, "executables_in", exec_mock)
        return exec_mock

    return _factory


@pytest.fixture
def patch_locate_binary(monkeypatch):
    def locate_binary(self, name):
        return os.path.join(os.path.dirname(__file__), "bin", name)

    def factory(cc: commands_cache.CommandsCache):
        monkeypatch.setattr(cc, "locate_binary", types.MethodType(locate_binary, cc))
        return cc

    return factory


@pytest.fixture
def monkeypatch_stderr(monkeypatch):
    """Monkeypath sys.stderr with no ResourceWarning."""
    with open(os.devnull, "w") as fd:
        monkeypatch.setattr(sys, "stderr", fd)
        yield


@pytest.fixture(scope="module")
def xonsh_events():
    yield events
    for name, oldevent in vars(events).items():
        # Heavily based on transmogrification
        species = oldevent.species
        newevent = events._mkevent(name, species, species.__doc__)
        setattr(events, name, newevent)


@pytest.fixture(scope="session")
def session_env():
    """Env with initial values set from os.environ. But will not inherit XONSH specific variables"""
    from xonsh.environ import Env, default_env

    initial_vars = {
        "UPDATE_OS_ENVIRON": False,
        "XONSH_DEBUG": 1,
        "XONSH_COLOR_STYLE": "default",
        "VC_BRANCH_TIMEOUT": 1,
        "XONSH_ENCODING": "utf-8",
        "XONSH_ENCODING_ERRORS": "strict",
        "COMMANDS_CACHE_SAVE_INTERMEDIATE": False,
    }
    env = Env(initial_vars)
    for key, val in default_env().items():
        if (key not in env) or (key.endswith("PATH")):
            env[key] = val
    return env


@pytest.fixture(scope="session")
def session_execer():
    return Execer()


@pytest.fixture
def env(xonsh_session):
    """to easily set env variables function level"""
    return xonsh_session.env


@pytest.fixture(scope="module")
def module_xsh(xonsh_events, session_execer, session_env):
    XSH.load(
        ctx={},
        execer=session_execer,
        env=copy_env(session_env),
    )
    yield XSH
    XSH.unload()
    get_tasks().clear()  # must do this to enable resetting all_jobs


@pytest.fixture
def xonsh_session(module_xsh, monkeypatch, mocker, tmp_path):
    """a fixture to use where XonshSession is fully loaded without any mocks

    Use `env` fixture to set function level variables
    """
    env_ref = module_xsh.env
    mock_env(mocker, module_xsh.env)

    for var in (
        "XONSH_DATA_DIR",
        "XONSH_CACHE_DIR",
    ):
        module_xsh.env[var] = tmp_path
    yield module_xsh
    # if any tests update .env, we need to reset it
    module_xsh.env = env_ref


@pytest.fixture
def mock_xonsh_session(monkeypatch, xonsh_events, xonsh_session):
    """Mock out most of the builtins xonsh attributes."""

    # make sure that all other fixtures call this mock only one time
    session = []

    def factory(*attrs_to_skip: str):
        """

        Parameters
        ----------
        attrs_to_skip
            do not mock the given attributes

        Returns
        -------
        XonshSession
            with most of the attributes mocked out
        """
        if session:
            raise RuntimeError("The factory should be called only once per test")

        if "aliases" not in attrs_to_skip:
            monkeypatch.setattr(xonsh_session.commands_cache, "aliases", Aliases())

        for attr, val in [
            ("shell", DummyShell()),
            ("help", lambda x: x),
            ("exit", False),
            ("history", DummyHistory()),
            # ("subproc_captured", sp),
            ("subproc_uncaptured", sp),
            ("subproc_captured_stdout", sp),
            ("subproc_captured_inject", sp),
            ("subproc_captured_object", sp),
            ("subproc_captured_hiddenobject", sp),
        ]:
            if attr in attrs_to_skip:
                continue
            monkeypatch.setattr(xonsh_session, attr, val)

        for attr, val in [
            ("evalx", eval),
            ("execx", None),
            ("compilex", None),
            # Unlike all the other stuff, this has to refer to the "real" one because all modules that would
            # be firing events on the global instance.
            ("events", xonsh_events),
        ]:
            # attributes to builtins are dynamicProxy and should pickup the following
            monkeypatch.setattr(xonsh_session.builtins, attr, val)

        session.append(xonsh_session)
        return xonsh_session

    yield factory
    session.clear()


@pytest.fixture
def xession(mock_xonsh_session) -> XonshSession:
    """Mock out most of the builtins xonsh attributes."""
    return mock_xonsh_session()


@pytest.fixture
def xsh_with_aliases(mock_xonsh_session) -> XonshSession:
    """Xonsh mock-session with default set of aliases"""
    return mock_xonsh_session("aliases")


@pytest.fixture(scope="session")
def completion_context_parse():
    return CompletionContextParser().parse


@pytest.fixture(scope="session")
def completer_obj():
    return Completer()


@pytest.fixture
def check_completer(completer_obj):
    """Helper function to run completer and parse the results as set of strings"""
    completer = completer_obj

    def _factory(
        line: str, prefix: "None|str" = "", send_original=False, complete_fn=None
    ):
        """

        Parameters
        ----------
        line
        prefix
        send_original
            if True, return the original result from the completer (e.g. RichCompletion instances ...)
        complete_fn
            if given, use that to get the completions

        Returns
        -------
            completions as set of string if not send
        """
        if prefix is not None:
            line += " " + prefix
        if complete_fn is None:
            completions, _ = completer.complete_line(line)
        else:
            ctx = completer_obj.parse(line)
            out = complete_fn(ctx)
            if isinstance(out, tuple):
                completions = out[0]
            else:
                completions = out
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

    from xonsh.shells.ptk_shell import PromptToolkitShell

    out = DummyOutput()
    with create_pipe_input() as inp:
        shell = PromptToolkitShell(
            execer=xonsh_execer, ctx={}, ptk_args={"input": inp, "output": out}
        )
        yield inp, out, shell


@pytest.fixture
def readline_shell(xonsh_execer, tmpdir, mocker):
    from xonsh.shells.readline_shell import ReadlineShell

    inp_path = tmpdir / "in"
    inp = inp_path.open("w+")
    out_path = tmpdir / "out"
    out = out_path.open("w+")

    shell = ReadlineShell(execer=xonsh_execer, ctx={}, stdin=inp, stdout=out)
    mocker.patch.object(shell, "_load_remaining_input_into_queue")
    yield shell
    inp.close()
    out.close()


@pytest.fixture
def setup_import_hook(monkeypatch, xonsh_session):
    import copy

    from xonsh.imphooks import install_import_hooks

    old = copy.copy(sys.meta_path)
    install_import_hooks(xonsh_session.execer)
    yield xonsh_session
    sys.meta_path = old


@pytest.fixture
def load_xontrib():
    to_unload = []

    def wrapper(*names: str):
        from xonsh.xontribs import xontrib_data, xontribs_load

        xo_data = xontrib_data()

        for name in names:
            module = xo_data[name]["module"]
            if module not in sys.modules:
                to_unload.append(module)

            _, stderr, res = xontribs_load([module], full_module=True)
            if stderr:
                raise Exception(f"Failed to load xontrib: {stderr}")
        return

    yield wrapper

    for mod in to_unload:
        del sys.modules[mod]
