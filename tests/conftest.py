import glob
import builtins
from traceback import format_list, extract_tb

import pytest
from tools import DummyShell, sp
import xonsh.built_ins
from xonsh.built_ins import ensure_list_of_strs
from xonsh.execer import Execer
from xonsh.tools import XonshBlockError
from xonsh.events import events
import glob



def _limited_traceback(excinfo):
    """ Return a formatted traceback with all the stack
        from this frame (i.e __file__) up removed
    """
    tb = extract_tb(excinfo.tb)
    try:
        idx = [__file__ in e for e in tb].index(True)
        return format_list(tb[idx+1:])
    except ValueError:
        return format_list(tb)

def pytest_collect_file(parent, path):
    if path.ext == ".xsh" and path.basename.startswith("test"):
        return XshFile(path, parent)

class XshFile(pytest.File):
    def collect(self):
        name = self.fspath.basename
        yield XshItem(name, self)

class XshItem(pytest.Item):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    def runtest(self):
        xonsh_main([str(self.parent.fspath), '--no-script-cache', '--no-rc'])

    def repr_failure(self, excinfo):
        """ called when self.runtest() raises an exception. """
        formatted_tb = _limited_traceback(excinfo)
        formatted_tb.insert(0, "Xonsh execution failed\n")
        return "".join(formatted_tb)

    def reportinfo(self):
        return self.fspath, 0, "usecase: %s" % self.name


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
    del builtins.__xonsh_subproc_captured__
    del builtins.__xonsh_subproc_uncaptured__
    del builtins.__xonsh_ensure_list_of_strs__
    del builtins.XonshBlockError
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases
    del builtins.events
