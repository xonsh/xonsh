"""Tests the xonfig command.
Actually, just a down payment on a full test.
Currently exercises only these options:
- xonfig info
- xonfig jupyter_kernel

"""

import io
import re

import pytest  # noqa F401
import requests

from xonsh.webconfig import file_writes
from xonsh.webconfig import main as web_main
from xonsh.xonfig import xonfig_main


def test_xonfig_help(capsys, xession):
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


class MockRequest:
    """Mock socket.socket for testing request handler"""

    def __init__(self, path: str):
        self._path = path
        self.data = b""
        self.content = []
        self.method = None
        self.handler = None

    def getsockname(self):
        return ("sockname",)

    def _request(self):
        web_main.XonshConfigHTTPRequestHandler(self, (0, 0), None)
        return self

    def get(self):
        self.method = "GET"
        self._request()
        return self.data.decode()

    def post(self, **data):
        self.method = "POST"
        if data:
            req = requests.Request(
                method=self.method, url=f"http://localhost{self._path}", data=data
            ).prepare()
            self.content = [f"{k}: {v}".encode() for k, v in req.headers.items()] + [
                b"",  # empty line to show end of headers
                (
                    req.body.encode()
                    if isinstance(req.body, str)
                    else b""
                    if req.body is None
                    else req.body
                ),
            ]
        self._request()
        return self.data.decode()

    def makefile(self, *args, **kwargs):
        if args[0] == "rb":
            body = f"{self.method} {self._path} HTTP/1.0".encode()
            if self.content:
                body = b"\n".join([body, *self.content])
            return io.BytesIO(body)
        elif args[0] == "wb":
            return io.BytesIO(b"")
        else:
            raise ValueError("Unknown file type to make", args, kwargs)

    def sendall(self, data):
        self.data = data


@pytest.fixture
def request_factory():
    from urllib import parse

    def factory(path, **params):
        if params:
            path = path + "?" + parse.urlencode(params)
        return MockRequest(path)

    return factory


@pytest.fixture
def rc_file(tmp_path, monkeypatch):
    file = tmp_path / "xonshrc"
    monkeypatch.setattr(file_writes, "RC_FILE", str(file))
    return file


class TestXonfigWeb:
    def test_colors_get(self, request_factory):
        resp = request_factory("/").get()
        assert "Colors" in resp

    def test_colors_post(self, request_factory, rc_file):
        resp = request_factory("/", selected="default").post()
        assert "$XONSH_COLOR_STYLE = 'default'" in rc_file.read_text()
        assert "302" in resp  # redirect

    def test_xontribs_get(self, request_factory):
        resp = request_factory("/xontribs").get()
        assert "Xontribs" in resp

    def test_xontribs_post(self, request_factory, rc_file, mocker):
        mocker.patch("xonsh.xontribs.xontribs_load", return_value=(None, None, None))
        resp = request_factory("/xontribs").post(xontrib1="")
        assert "xontrib load xontrib1" in rc_file.read_text()
        assert "302" in resp

    def test_prompts_get(self, request_factory):
        resp = request_factory("/prompts").get()
        assert "Prompts" in resp

    def test_prompts_post(self, request_factory, rc_file):
        resp = request_factory("/prompts").post(PROMPT="custom")
        assert "$PROMPT = 'custom'" in rc_file.read_text()
        assert "302" in resp

    def test_it_rewrites_correctly(self, request_factory, rc_file):
        rc_file.write_text(
            """
pre-lines
# XONSH WEBCONFIG START
$XONSH_COLOR_STYLE = 'abap'
# XONSH WEBCONFIG END
post
lines
"""
        )
        request_factory("/prompts").post(PROMPT="custom")
        assert (
            rc_file.read_text()
            == """
pre-lines
# XONSH WEBCONFIG START
$XONSH_COLOR_STYLE = 'abap'
$PROMPT = 'custom'
# XONSH WEBCONFIG END
post
lines
"""
        )


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
