"""Xonsh extension of the standard library subprocess module, using xonsh for
subprocess calls"""
from subprocess import CalledProcessError

from xonsh.tools import XonshCalledProcessError
from xonsh.lib.os import indir


def run(cmd, cwd=None, check=False):
    """Drop in replacement for ``subprocess.run`` like functionality"""
    if cwd is None:
        with ${...}.swap(RAISE_SUBPROC_ERROR=check):
            p = ![@(cmd)]
    else:
        with indir(cwd), ${...}.swap(RAISE_SUBPROC_ERROR=check):
            p = ![@(cmd)]
    return p


def check_call(cmd, cwd=None):
    """Drop in replacement for ``subprocess.check_call`` like functionality"""
    p = run(cmd, cwd=cwd, check=True)
    return p.returncode


def check_output(cmd, cwd=None):
    """Drop in replacement for ``subprocess.check_output`` like functionality"""
    p = run(cmd, cwd=cwd, check=True)
    # Note the encoding is to match the expected output of check_output
    return p.output.encode('utf-8')
