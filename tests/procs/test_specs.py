"""Tests the xonsh.procs.specs"""
from subprocess import Popen

import pytest

from xonsh.procs.specs import cmds_to_specs

from xonsh.environ import Env
from xonsh.procs.posix import PopenThread
from xonsh.procs.proxies import ProcProxy, ProcProxyThread

from .tools import skip_if_on_windows


@skip_if_on_windows
def test_cmds_to_specs_thread_subproc(xonsh_builtins):
    env = xonsh_builtins.__xonsh__.env
    cmds = [["pwd"]]
    # First check that threadable subprocs become threadable
    env["THREAD_SUBPROCS"] = True
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is PopenThread
    # turn off threading and check we use Popen
    env["THREAD_SUBPROCS"] = False
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is Popen

    # now check the threadbility of callable aliases
    cmds = [[lambda: "Keras Selyrian"]]
    # check that threadable alias become threadable
    env["THREAD_SUBPROCS"] = True
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is ProcProxyThread
    # turn off threading and check we use ProcProxy
    env["THREAD_SUBPROCS"] = False
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is ProcProxy
