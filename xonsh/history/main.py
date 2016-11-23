# -*- coding: utf-8 -*-
"""Implements the xonsh history object."""
import builtins
import collections

from xonsh.history.dummy import DummyHistory
from xonsh.history.json import History
from xonsh.history.json import history_main
from xonsh.history.sqlite import SqliteHistory

HISTORY_BACKENDS = {
    'dummy': DummyHistory,
    'json': History,
    'sqlite': SqliteHistory,
}


def construct_history(env, ts, locked, gc=True, filename=None):
    env = builtins.__xonsh_env__
    backend = env.get('XONSH_HISTORY_BACKEND', 'json')
    if backend not in HISTORY_BACKENDS:
        print('Unknown history backend: {}. Use Json version'.format(backend))
        kls_history = History
    else:
        kls_history = HISTORY_BACKENDS[backend]
    return kls_history(
        env=env.detype(),
        ts=ts,
        locked=locked,
        gc=gc,
        filename=filename,
    )


def history_main(args=None, stdin=None, stdout=None, stderr=None):
    """This is the history command entry point."""
    hist = builtins.__xonsh_history__
    ns = _hist_parse_args(args)
    if ns:
        _HIST_MAIN_ACTIONS[ns.action](ns, hist, stdout, stderr)
