# -*- coding: utf-8 -*-
"""Tools to replay xonsh history files."""
import time
import builtins
from collections.abc import Mapping

from xonsh.tools import swap
from xonsh import lazyjson
from xonsh.environ import Env
from xonsh.history import History
from xonsh.history import _info as history_info

DEFAULT_MERGE_ENVS = ('replay', 'native')


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

    def replay(self, merge_envs=DEFAULT_MERGE_ENVS, target=None):
        """Replays the history specified, returns the history object where the code
        was executed.

        Parameters
        ----------
        merge_env : tuple of str or Mappings, optional
            Describes how to merge the environments, in order of increasing precednce.
            Available strings are 'replay' and 'native'. The 'replay' env comes from the
            history file that we are replaying. The 'native' env comes from what this
            instance of xonsh was started up with. Instead of a string, a dict or other
            mapping may be passed in as well. Defaults to ('replay', 'native').
        target : str, optional
            Path to new history file.
        """
        shell = builtins.__xonsh_shell__
        re_env = self._lj['env'].load()
        new_env = self._merge_envs(merge_envs, re_env)
        new_hist = History(env=new_env.detype(), locked=True, ts=[time.time(), None],
                           gc=False, filename=target)
        with swap(builtins, '__xonsh_env__', new_env), \
             swap(builtins, '__xonsh_history__', new_hist):
            for cmd in self._lj['cmds']:
                inp = cmd['inp']
                shell.default(inp)
                if builtins.__xonsh_exit__:  # prevent premature exit
                    builtins.__xonsh_exit__ = False
        new_hist.flush(at_exit=True)
        return new_hist

    def _merge_envs(self, merge_envs, re_env):
        new_env = {}
        for e in merge_envs:
            if e == 'replay':
                new_env.update(re_env)
            elif e == 'native':
                new_env.update(builtins.__xonsh_env__)
            elif isinstance(e, Mapping):
                new_env.update(e)
            else:
                raise TypeError('Type of env not understood: {0!r}'.format(e))
        new_env = Env(**new_env)
        return new_env


_REPLAY_PARSER = None

def _create_parser(p=None):
    global _REPLAY_PARSER
    p_was_none = (p is None)
    if _REPLAY_PARSER is not None and p_was_none:
        return _REPLAY_PARSER
    if p_was_none:
        from argparse import ArgumentParser
        p = ArgumentParser('replay', description='replays a xonsh history file')
    p.add_argument('--merge-envs', dest='merge_envs', default=DEFAULT_MERGE_ENVS,
                   nargs='+',
                   help="Describes how to merge the environments, in order of "
                        "increasing precedence. Available strings are 'replay' and "
                        "'native'. The 'replay' env comes from the history file that we "
                        "are replaying. The 'native' env comes from what this instance "
                        "of xonsh was started up with. One or more of these options may "
                        "be passed in. Defaults to '--merge-envs replay native'.")
    p.add_argument('--json', dest='json', default=False, action='store_true',
                   help='print history info in JSON format')
    p.add_argument('-o', '--target', dest='target', default=None,
                   help='path to new history file')
    p.add_argument('path', help='path to replay history file')
    if p_was_none:
        _REPLAY_PARSER = p
    return p


def _main_action(ns, h=None):
    replayer = Replayer(ns.path)
    hist = replayer.replay(merge_envs=ns.merge_envs, target=ns.target)
    print('----------------------------------------------------------------')
    print('Just replayed history, new history has the following information')
    print('----------------------------------------------------------------')
    history_info(ns, hist)


def main(args, stdin=None):
    """Acts as main function for replaying a xonsh history file."""
    parser = _create_parser()
    ns = parser.parse_args(args)
    _main_action(ns)
