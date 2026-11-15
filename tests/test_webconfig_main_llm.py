"""Tests for the ``xonsh.webconfig.main`` HTTP server (``xonfig web``).

The server writes to the user's xonsh RC, so it must only accept requests
from its own page on the local machine (see xonsh/xonsh#6671).
"""

import http.client
import os
import threading

import pytest

from xonsh.webconfig import file_writes, main
from xonsh.webconfig.routes import Routes


class _RecordingRoute:
    path = "/test-post"
    posted: list = []

    def __init__(self, url, params, xsh):
        pass

    def post(self, data):
        self.posted.append(data)


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(file_writes, "RC_FILE", str(tmp_path / "xonshrc"))
    monkeypatch.setitem(Routes.registry, _RecordingRoute.path, _RecordingRoute)
    _RecordingRoute.posted = []
    httpd = main.bind_server_to(port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def _post(httpd, path, body, **headers):
    host, port = httpd.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    headers.setdefault("Host", f"localhost:{port}")
    conn.request("POST", path, body=body, headers=headers)
    status = conn.getresponse().status
    conn.close()
    return status


def _get(httpd, path, host=None):
    port = httpd.server_address[1]
    conn = http.client.HTTPConnection(httpd.server_address[0], port, timeout=5)
    conn.request("GET", path, headers={"Host": host or f"localhost:{port}"})
    status = conn.getresponse().status
    conn.close()
    return status


def _form_headers(httpd, origin=None):
    port = httpd.server_address[1]
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": origin or f"http://localhost:{port}",
    }


def test_binds_to_loopback_only(server):
    assert server.server_address[0] == "127.0.0.1"


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_same_origin_post_is_accepted(server, host):
    port = server.server_address[1]
    headers = _form_headers(server, origin=f"http://{host}:{port}")
    headers["Host"] = f"{host}:{port}"
    assert _post(server, _RecordingRoute.path, "a=1", **headers) == 302
    assert _RecordingRoute.posted == [{"a": "1"}]


def test_cross_origin_post_is_rejected(server):
    headers = _form_headers(server, origin="https://evil.example")
    assert _post(server, _RecordingRoute.path, "a=1", **headers) == 403
    assert _RecordingRoute.posted == []


def test_post_without_origin_is_rejected(server):
    headers = _form_headers(server)
    del headers["Origin"]
    assert _post(server, _RecordingRoute.path, "a=1", **headers) == 403
    assert _RecordingRoute.posted == []


def test_post_with_foreign_host_is_rejected(server):
    """DNS rebinding: the attacker's name resolves to 127.0.0.1."""
    port = server.server_address[1]
    origin = f"http://evil.example:{port}"
    headers = _form_headers(server, origin=origin)
    headers["Host"] = f"evil.example:{port}"
    assert _post(server, _RecordingRoute.path, "a=1", **headers) == 403
    assert _RecordingRoute.posted == []


def test_raw_json_post_does_not_write_rc(server):
    body = '{"xontribs": ["abbrevs\\nimport os; os.system(\\"touch PWNED\\")"]}'
    headers = _form_headers(server)
    headers["Content-Type"] = "text/plain"
    assert _post(server, "/anything", body, **headers) == 404
    assert not os.path.exists(file_writes.RC_FILE)


def test_get_with_own_host_is_served(server):
    assert _get(server, "/js/xonsh_sticker_mini.png") == 200


def test_get_with_foreign_host_is_rejected(server):
    """DNS rebinding must not let another page read aliases or variables."""
    port = server.server_address[1]
    assert _get(server, "/alias", host=f"evil.example:{port}") == 403
