"""Prompt formatter for current jobs"""

import contextlib
import typing as tp

_current_cmds: tp.Optional[list] = None


@contextlib.contextmanager
def update_current_cmds(cmds):
    """Context manager that updates the information used by _current_job()"""
    global _current_cmds
    old_cmds = _current_cmds
    try:
        _current_cmds = cmds
        yield
    finally:
        _current_cmds = old_cmds


def _current_job():
    if _current_cmds is not None:
        cmd = _current_cmds[-1]
        s = cmd[0]
        if s == "sudo" and len(cmd) > 1:
            s = cmd[1]
        return s
