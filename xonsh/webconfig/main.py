#!/usr/bin/env python3
import contextlib
import json
import os
import socketserver
import string
import sys
import typing as tp
from email.message import EmailMessage
from http import HTTPStatus, server
from pathlib import Path
from pprint import pprint
from urllib import parse

from xonsh.built_ins import XSH
from xonsh.webconfig import tags as t
from xonsh.webconfig.file_writes import insert_into_xonshrc
from xonsh.webconfig.routes import Routes

RENDERERS: list[tp.Callable] = []


class XonshConfigHTTPRequestHandler(server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("directory", os.path.dirname(__file__))
        super().__init__(*args, **kwargs)

    def _write_headers(self, *headers: "tuple[str, str]"):
        for name, val in headers:
            self.send_header(name, val)
        self.end_headers()

    def _write_data(self, data: "bytes|dict|str"):
        if isinstance(data, bytes):
            content_type = "text/html"
        elif isinstance(data, dict):
            content_type = "application/json"
            data = json.dumps(data).encode()
        else:
            content_type = "text/html"
            data = str(data).encode()
        self._write_headers(
            ("Content-type", content_type),
            ("Content-Length", str(len(data))),
        )
        self.wfile.write(data)
        self.wfile.flush()

    def _send(
        self,
        data: "bytes|dict|str|None" = None,
        status: "None|int" = None,
        redirect: "str|None" = None,
    ):
        status = status or (HTTPStatus.FOUND if redirect else HTTPStatus.OK)
        self.send_response(status)
        if data:
            self._write_data(data)
        elif redirect:
            self._write_headers(
                ("Location", redirect),
            )

    def _read(self):
        content_len = int(self.headers.get("content-length", 0))
        return self.rfile.read(content_len)

    def render_get(self, route):
        try:
            webconfig = Path(__file__).parent
        except Exception:
            # in case of thread missing __file__ definition
            webconfig = Path.cwd()
        path = webconfig / "index.html"
        tmpl = string.Template(path.read_text())
        navlinks = t.to_str(route.get_nav_links())
        msgs = t.to_str(route.get_err_msgs())
        body = t.to_str(route.get())  # type: ignore
        data = tmpl.substitute(navlinks=navlinks, body=msgs + body)
        return self._send(data)

    def _get_route(self, method: str):
        url = parse.urlparse(self.path)
        route_cls = Routes.registry.get(url.path)
        if route_cls and hasattr(route_cls, method):
            params = parse.parse_qs(url.query)
            return route_cls(url=url, params=params, xsh=XSH)

    def do_GET(self) -> None:
        route = self._get_route("get")
        if route is not None:
            return self.render_get(route)
        return super().do_GET()

    def _read_form(self):
        msg = EmailMessage()
        msg["Content-Type"] = self.headers.get("content-type")
        if msg.get_content_type() == "application/x-www-form-urlencoded":
            data = parse.parse_qs(self._read(), keep_blank_values=True)
            for name, values in data.items():
                value = None
                if isinstance(name, bytes):
                    name = name.decode(encoding="utf-8")
                if isinstance(values, list) and values:
                    if isinstance(values[0], bytes):
                        value = values[0].decode(encoding="utf-8")
                yield name, value

    def do_POST(self):
        """Reads post request body"""
        route = self._get_route("post")
        if route is not None:
            # redirect after form submission
            data = dict(self._read_form())

            new_route = route.post(data) or route
            return self._send(redirect=new_route.path)
        post_body = self._read()
        config = json.loads(post_body)
        print("Web Config Values:")
        pprint(config)
        fname = insert_into_xonshrc(config)
        print("Wrote out to " + fname)
        self._send(b"received post request:<br>" + post_body)


def bind_server_to(
    port: int = 8421, handler_cls=XonshConfigHTTPRequestHandler, browser=False
):
    cls = socketserver.TCPServer
    # cls = socketserver.ThreadingTCPServer  # required ctrl+c twice ?

    cls.allow_reuse_address = True

    while port <= 9310:
        try:
            cls.allow_reuse_address = True

            httpd = cls(("", port), handler_cls)
            url = f"http://localhost:{port}"
            print(f"Web config started at '{url}'. Hit Ctrl+C to stop.")
            if browser:
                import webbrowser

                webbrowser.open(url)
            return httpd
        except OSError:
            type, value = sys.exc_info()[:2]
            if "Address already in use" not in str(value):
                raise
        except KeyboardInterrupt:
            break
        port += 1


def serve(browser=False):
    httpd = bind_server_to(browser=browser)

    with contextlib.suppress(KeyboardInterrupt):
        with httpd:
            httpd.serve_forever()


def main(browser=False):
    """standalone entry point for webconfig."""
    from xonsh.main import setup

    setup()
    serve(browser)


if __name__ == "__main__":
    # watchexec -r -e py -- python -m xonsh.webconfig --no-browser
    main()
