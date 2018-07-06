"""Xonsh extension of the standard library subprocess module, using xonsh for
subprocess calls"""
from xonsh.tools import XonshCalledProcessError as CalledProcessError
from xonsh.lib.os import indir


def run(cmd, cwd=None, check=False):
    """Drop in replacement for ``subprocess.run`` like functionality"""
    if cwd is None:
        cwd = '.'
    with indir(cwd), ${...}.swap(RAISE_SUBPROC_ERROR=check):
        p = ![@(cmd)]
    return p


def check_call(cmd, cwd=None):
    """Drop in replacement for ``subprocess.check_call`` like functionality"""
    p = run(cmd, cwd=cwd, check=True)
    return p.returncode
