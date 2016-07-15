import builtins
import pytest
from tests.tools import DummyShell, sp, XonshBlockError
import xonsh.built_ins
from xonsh.built_ins import ensure_list_of_strs
from xonsh.execer import Execer
import glob


@pytest.fixture
def xonsh_execer(monkeypatch):
    """Initiate the Execer with a mocked nop `load_builtins`"""
    monkeypatch.setattr(xonsh.built_ins, 'load_builtins', lambda *args, **kwargs: None)
    execer = Execer(login=False, unload=False)
    builtins.__xonsh_execer__ = execer
    return execer


@pytest.yield_fixture
def xonsh_builtins():
    """Mock out most of the builtins xonsh attributes."""
    builtins.__xonsh_env__ = {}
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
    builtins.__xonsh_ensure_list_of_strs__ = ensure_list_of_strs
    builtins.XonshBlockError = XonshBlockError
    builtins.__xonsh_subproc_captured_hiddenobject__ = sp
    builtins.evalx = eval
    builtins.execx = None
    builtins.compilex = None
    builtins.aliases = {}
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
    del builtins.__xonsh_subproc_captured__
    del builtins.__xonsh_subproc_uncaptured__
    del builtins.__xonsh_ensure_list_of_strs__
    del builtins.XonshBlockError
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases
