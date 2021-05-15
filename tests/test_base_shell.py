# -*- coding: utf-8 -*-
"""(A down payment on) Testing for ``xonsh.base_shell.BaseShell`` and associated classes"""
import os

from xonsh.environ import Env
from xonsh.base_shell import BaseShell
from xonsh.shell import transform_command


def test_pwd_tracks_cwd(xession, xonsh_execer, tmpdir_factory, monkeypatch):
    asubdir = str(tmpdir_factory.mktemp("asubdir"))
    cur_wd = os.getcwd()
    xession.env = Env(
        PWD=cur_wd, XONSH_CACHE_SCRIPTS=False, XONSH_CACHE_EVERYTHING=False
    )

    monkeypatch.setattr(xonsh_execer, "cacheall", False, raising=False)
    bc = BaseShell(xonsh_execer, None)

    assert os.getcwd() == cur_wd

    bc.default('os.chdir(r"' + asubdir + '")')

    assert os.path.abspath(os.getcwd()) == os.path.abspath(asubdir)
    assert os.path.abspath(os.getcwd()) == os.path.abspath(xession.env["PWD"])
    assert "OLDPWD" in xession.env
    assert os.path.abspath(cur_wd) == os.path.abspath(xession.env["OLDPWD"])


def test_transform(xession):
    @xession.builtins.events.on_transform_command
    def spam2egg(cmd, **_):
        if cmd == "spam":
            return "egg"
        else:
            return cmd

    assert transform_command("spam") == "egg"
    assert transform_command("egg") == "egg"
    assert transform_command("foo") == "foo"
