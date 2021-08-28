# -*- coding: utf-8 -*-
"""Tests the xonfig command.
   Actually, just a down payment on a full test.
   Currently exercises only these options:
   - xonfig info
   - xonfig jupyter_kernel

"""
import os
import re
import sys
import json
import pytest  # noqa F401

from xonsh.tools import ON_WINDOWS
from xonsh.xonfig import xonfig_main


def test_xonfg_help(capsys, xonsh_builtins):
    """verify can invoke it, and usage knows about all the options"""
    with pytest.raises(SystemExit):
        xonfig_main(["-h"])
    capout = capsys.readouterr().out
    pat = re.compile(r"^usage:\s*xonfig[^\n]*{([\w,-]+)}", re.MULTILINE)
    m = pat.match(capout)
    assert m[1]
    verbs = set(v.strip().lower() for v in m[1].split(","))
    assert verbs == {
        "jupyter-kernel",
        "info",
        "styles",
        "wizard",
        "web",
        "colors",
        "tutorial",
    }


@pytest.mark.parametrize(
    "args",
    [
        ([]),
        (
            [
                "info",
            ]
        ),
    ],  # NOQA E231
)
def test_xonfig_info(args, xonsh_builtins):
    """info works, and reports no jupyter if none in environment"""
    capout = xonfig_main(args)
    assert capout.startswith("+---")
    assert capout.endswith("---+\n")
    pat = re.compile(r".*on jupyter\s+\|\s+false", re.MULTILINE | re.IGNORECASE)
    m = pat.search(capout)
    assert m


def strip_sep(path: str) -> str:
    """remove all path separators from argument"""
    retval = path.replace(os.sep, "")
    if ON_WINDOWS:
        retval = retval.replace(os.altsep, "")
    return retval


@pytest.fixture
def fake_lib(monkeypatch):
    """insulate sys.modules from hacking test modules may do with it.
    Apparently, monkeypath.syspath_prepend() doesn't flush
    imported modules, so they're still visible in other test cases.
    """

    # get absolute path to fake_lib, assuming this test file itself is in same folder.
    fake_lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fake_lib"))
    monkeypatch.syspath_prepend(fake_lib_path)
    yield

    # monkeypatch will have restored sys.path, but it's up to us to purge the imported modules
    fake_packages = tuple(f.name for f in os.scandir(fake_lib_path) if os.path.isdir(f))
    modules_to_delete = []

    for (m, mod) in sys.modules.items():
        if m.startswith(fake_packages):
            if mod.__file__.startswith(fake_lib_path):
                modules_to_delete.append(m)  # can't modify collection while iterating

    for m in modules_to_delete:
        del sys.modules[m]


def test_xonfig_kernel_with_jupyter(monkeypatch, capsys, fake_lib, xonsh_builtins):
    cap_args = None
    cap_spec = None

    import jupyter_client.kernelspec  # from fake_lib, hopefully.

    def mock_install_kernel_spec(*args, **kwargs):  # arg[0] is self
        nonlocal cap_args
        nonlocal cap_spec
        cap_args = dict(args=args, kw=kwargs)
        spec_file = os.path.join(args[1], "kernel.json")
        cap_spec = json.load(open(spec_file, "r"))

    def mock_get_kernel_spec(*args, **kwargs):
        raise jupyter_client.kernelspec.NoSuchKernel

    monkeypatch.setattr(
        jupyter_client.kernelspec.KernelSpecManager,
        "install_kernel_spec",
        value=mock_install_kernel_spec,
        raising=False,
    )
    monkeypatch.setattr(
        jupyter_client.kernelspec.KernelSpecManager,
        "get_kernel_spec",
        value=mock_get_kernel_spec,
        raising=False,
    )

    rc = xonfig_main(["jupyter-kernel"])
    assert rc == 0
    capout = capsys.readouterr().out
    assert "Jupyter" in capout
    assert "xonsh" == cap_args["args"][2]
    assert cap_spec
    assert cap_spec["language"] == "xonsh"
    assert strip_sep(cap_spec["argv"][0]) == strip_sep(sys.executable)
    assert cap_spec["argv"][2] == "xonsh.jupyter_kernel"


def test_xonfig_kernel_no_jupyter(capsys, xonsh_builtins):
    with pytest.raises(ImportError):
        rc = xonfig_main(["jupyter-kernel"])  # noqa F841
