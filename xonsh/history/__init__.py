# -*- coding: utf-8 -*-
"""Implements the xonsh history object."""
import builtins
import time

from xonsh.history.dummy import History as DummyHistory
from xonsh.history.json import History as JsonHistory
from xonsh.history.json import history_main
from xonsh.history.sqlite import History as SqliteHistory

_BACKENDS = {
    'dummy': DummyHistory,
    'json': JsonHistory,
    'sqlite': SqliteHistory,
}


def get_history_backend(env, ts, locked, gc=True, filename=None):
    env = builtins.__xonsh_env__
    backend = env.get('XONSH_HISTORY_BACKEND', 'json')
    try:
        kls_history = _BACKENDS[backend]
    except KeyError:
        print('Unknown history backend: {}. Use Json version'.format(backend))
        kls_history = JsonHistory
    print('History backend: {}'.format(kls_history))
    return kls_history(
        env=env.detype(),
        ts=[time.time(), None],
        locked=True,
        gc=gc,
        filename=filename,
    )


def _hist_info(ns, hist, stdout, stderr):
    raise NotImplementedError()
