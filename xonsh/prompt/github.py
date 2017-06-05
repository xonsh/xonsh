# -*- coding: utf-8 -*-
"""Informative github ci status prompt formatter, requires hub (brew install hub)"""

import builtins
import subprocess


def _check_output(*args, **kwargs):
    kwargs.update(dict(env=builtins.__xonsh_env__.detype(),
                       stderr=subprocess.DEVNULL,
                       timeout=builtins.__xonsh_env__['GITHUB_TIMEOUT'],
                       universal_newlines=True
                       ))
    return subprocess.check_output(*args, **kwargs)


def githubcistatus():
    """
    Return CI status for commit (HEAD)
    one of 'no status', 'pending', 'failure', 'success'
    """
    status = _check_output(['hub', 'ci-status'])
    return status.strip()


CISTATUS_COLORS = {
    'no status': '{NO_COLOR}',
    'pending': '{ORANGE}',
    'failure': '{RED}',
    'success': '{GREEN}'
}


def github_prompt():
    """Return str of colored build circle"""
    try:
        s = githubcistatus()
    except subprocess.SubprocessError:
        s = 'no status'

    try:
        ret = CISTATUS_COLORS[s]
    except KeyError:
        ret = '{NO_COLOR}'
    ret += '●'
    ret += '{NO_COLOR}'
    return ret
