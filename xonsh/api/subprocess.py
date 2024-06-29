"""Xonsh extension of the standard library subprocess module, using xonsh for
subprocess calls

Originally posted by @scopatz in https://github.com/xonsh/xonsh/issues/2726#issuecomment-406447196 :
    Recently @CJ-Wright has started up a ``xonsh.lib`` sub-package, which is usable from pure Python.
    This is meant as a standard library for xonsh and downstream tools.
    Currently there are some xonsh-ish wrappers around ``os`` and ``subprocess``.
    We'd love to see more contributions to this effort! So if there is something
    like ``sh()`` that you'd like to see, by all means please help us add it!
"""

from xonsh.built_ins import XSH, subproc_captured_hiddenobject, subproc_captured_stdout
from xonsh.api.os import indir


def run(cmd, cwd=None, check=False):
    """Drop in replacement for ``subprocess.run`` like functionality"""
    env = XSH.env
    if cwd is None:
        with env.swap(RAISE_SUBPROC_ERROR=check):
            p = subproc_captured_hiddenobject(cmd)
    else:
        with indir(cwd), env.swap(RAISE_SUBPROC_ERROR=check):
            p = subproc_captured_hiddenobject(cmd)
    return p


def check_call(cmd, cwd=None):
    """Drop in replacement for ``subprocess.check_call`` like functionality"""
    p = run(cmd, cwd=cwd, check=True)
    return p.returncode


def check_output(cmd, cwd=None):
    """Drop in replacement for ``subprocess.check_output`` like functionality"""
    env = XSH.env

    if cwd is None:
        with env.swap(RAISE_SUBPROC_ERROR=True):
            output = subproc_captured_stdout(cmd)
    else:
        with indir(cwd), env.swap(RAISE_SUBPROC_ERROR=True):
            output = subproc_captured_stdout(cmd)
    return output.encode("utf-8")
