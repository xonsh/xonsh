"""Tools to replay xonsh history files."""
import time
import builtins

from xonsh.tools import swap
from xonsh import lazyjson
from xonsh.environ import Env
from xonsh.history import History


class Replayer(object):
    """Replays a xonsh history file."""

    def __init__(self, f, reopen=True):
        """
        Parameters
        ----------
        f : file handle or str
            Path to xonsh history file.
        reopen : bool, optional
            Whether new file handle should be opened for each load, passed directly into
            LazyJSON class.
        """
        self._lj = lazyjson.LazyJSON(f, reopen=reopen)

    def __del__(self):
        self._lj.close()

    def replay(self):
        """Replays the history specified, returns the history object where the code 
        was executed.
        """
        shell = builtins.__xonsh_shell__
        re_env = self._lj['env'].load()
        new_env = Env(**re_env)
        new_hist = History(env=re_env, locked=True, ts=[time.time(), None])
        with swap(builtins, '__xonsh_env__', new_env), \
             swap(builtins, '__xonsh_history__', new_hist):
            for cmd in self._lj['cmds']:
                inp = cmd['inp']
                #if inp == 'EOF\n':
                #    break
                shell.default(inp)
        new_hist.flush(at_exit=True)
        return new_hist

