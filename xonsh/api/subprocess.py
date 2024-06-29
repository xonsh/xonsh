"""Xonsh extension of the standard library subprocess module, using xonsh for
subprocess calls"""

from xonsh.api.os import indir
from xonsh.built_ins import XSH, subproc_captured_hiddenobject, subproc_captured_stdout


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
