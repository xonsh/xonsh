"""Tests the xonfig command.
   Actually, just a down payment on a full test.
   Currently exercises only these options:
   - xonfig info
   - xonfig jupyter_kernel

"""
import io
import json
import os
import re
import sys

import pytest  # noqa F401

from xonsh.tools import ON_WINDOWS
from xonsh.webconfig import main as web_main
from xonsh.xonfig import xonfig_main


def test_xonfg_help(capsys, xession):
    """verify can invoke it, and usage knows about all the options"""
    with pytest.raises(SystemExit):
        xonfig_main(["-h"])
    capout = capsys.readouterr().out
    pat = re.compile(r"^usage:\s*xonfig[^\n]*{([\w,-]+)}", re.MULTILINE)
    m = pat.match(capout)
    assert m[1]
    verbs = {v.strip().lower() for v in m[1].split(",")}
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
def test_xonfig_info(args, xession):
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


def test_xonfig_kernel_with_jupyter(monkeypatch, capsys, fake_lib, xession):
    cap_args = None
    cap_spec = None

    import jupyter_client.kernelspec  # from fake_lib, hopefully.

    def mock_install_kernel_spec(*args, **kwargs):  # arg[0] is self
        nonlocal cap_args
        nonlocal cap_spec
        cap_args = dict(args=args, kw=kwargs)
        spec_file = os.path.join(args[1], "kernel.json")
        cap_spec = json.load(open(spec_file))

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


def test_xonfig_kernel_no_jupyter(capsys, xession):
    with pytest.raises(ImportError):
        rc = xonfig_main(["jupyter-kernel"])  # noqa F841


@pytest.fixture
def request_factory():
    class MockSocket:
        def getsockname(self):
            return ("sockname",)

        def sendall(self, data):
            self.data = data

    class MockRequest:
        _sock = MockSocket()

        def __init__(self, path: str, method: str):
            self._path = path
            self.data = b""
            self.method = method.upper()

        def makefile(self, *args, **kwargs):
            if args[0] == "rb":
                return io.BytesIO(f"{self.method} {self._path} HTTP/1.0".encode())
            elif args[0] == "wb":
                return io.BytesIO(b"")
            else:
                raise ValueError("Unknown file type to make", args, kwargs)

        def sendall(self, data):
            self.data = data

    return MockRequest


@pytest.fixture
def get_req(request_factory):
    from urllib import parse

    def factory(path, data: "dict[str, str]|None" = None):
        if data:
            path = path + "?" + parse.urlencode(data)
        request = request_factory(path, "get")
        handle = web_main.XonshConfigHTTPRequestHandler(request, (0, 0), None)
        return request, handle, request.data.decode()

    return factory


class TestXonfigWeb:
    def test_colors_get(self, get_req):
        _, _, resp = get_req("/")
        assert "Colors" in resp

    def test_xontribs_get(self, get_req):
        _, _, resp = get_req("/xontribs")
        assert "Xontribs" in resp

    def test_prompts_get(self, get_req):
        _, _, resp = get_req("/prompts")
        assert "Prompts" in resp
