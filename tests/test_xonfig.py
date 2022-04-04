"""Tests the xonfig command.
   Actually, just a down payment on a full test.
   Currently exercises only these options:
   - xonfig info
   - xonfig jupyter_kernel

"""
import io
import re

import pytest  # noqa F401

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
        "info",
        "styles",
        "wizard",
        "web",
        "colors",
        "tutorial",
    }


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


@pytest.mark.parametrize(
    "args",
    [
        ([]),
        (
            [
                "info",
            ]
        ),
    ],
)
def test_xonfig_info(args, xession):
    """info works, and reports no jupyter if none in environment"""
    capout = xonfig_main(args)
    assert capout.startswith("+---")
    assert capout.endswith("---+\n")
    pat = re.compile(r".*history backend\s+\|\s+", re.MULTILINE | re.IGNORECASE)
    m = pat.search(capout)
    assert m
