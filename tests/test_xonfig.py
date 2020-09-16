# -*- coding: utf-8 -*-
"""Tests the xonfig command.
   Actually, just a down payment on a full test.
   Currently exercises only these options:
   - xonfig info
   - xonfig jupyter_kernel

"""
import re
import pytest  # noqa F401

import xonsh


from xonsh.xonfig import XONFIG_MAIN_ACTIONS, xonfig_main


def test_xonfg_help(capsys):
    """verify can invoke it, and usage knows about all the options"""
    with pytest.raises(SystemExit):
        xonfig_main(["-h"])
    capstr = capsys.readouterr()
    pat = re.compile(r"^usage:\s*xonfig[^\n]*{([\w,]+)}", re.MULTILINE)
    m = pat.match(capstr.out)
    assert m[1]
    verbs = set(v.strip().lower() for v in m[1].split(","))
    exp = set(v.lower() for v in XONFIG_MAIN_ACTIONS)
    assert verbs == exp


@pytest.mark.parametrize(
    "args", [([]), (["info",]),], # NOQA E231
)
def test_xonfig_info(args, capsys):
    """info works, and reports no jupyter if none in environment"""
    capout = xonfig_main(args)
    assert capout.startswith("+---")
    assert capout.endswith("---+\n")
    pat = re.compile(r".*on jupyter\s+\|\s+false", re.MULTILINE | re.IGNORECASE)
    m = pat.search(capout)
    assert m


# FIXME -- how to mock up a package (jupyter_client) that is not defined in current environment?

@pytest.fixture()
def fake_jc(monkeypatch):
    class KernelSpecManager:
        def install_kernel_spec(self, *args, **kwargs):
            return dict(args=args, kw=kwargs)

    monkeypatch.setattr(
        xonsh.xonfig, "KernelSpecManager", value=KernelSpecManager, raising=False
    )


def test_xonfig_kernel(fake_jc):
    capout = xonfig_main(["jupyter_kernel"])
    assert capout
