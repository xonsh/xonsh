#!/usr/bin/env python3
import cgi
import contextlib
import os
import string
import sys
import json
import socketserver
from pathlib import Path
from urllib import parse
from http import server, HTTPStatus
from pprint import pprint
from argparse import ArgumentParser
import typing as tp
from xonsh.built_ins import XSH

from xonsh.webconfig import tags as t
from xonsh.webconfig.routes import Routes

RENDERERS: tp.List[tp.Callable] = []


def renderer(f):
    """Adds decorated function to renderers list."""
    RENDERERS.append(f)


@renderer
def prompt(config):
    return ["$PROMPT = {!r}".format(config["prompt"])]


@renderer
def colors(config):
    style = config["colors"]
    if style == "default":
        return []
    return [f"$XONSH_COLOR_STYLE = {style!r}"]


@renderer
def xontribs(config):
    xtribs = config["xontribs"]
    if not xtribs:
        return []
    return ["xontrib load " + " ".join(xtribs)]


def config_to_xonsh(
    config, prefix="# XONSH WEBCONFIG START", suffix="# XONSH WEBCONFIG END"
):
    """Turns config dict into xonsh code (str)."""
    lines = [prefix]
    for func in RENDERERS:
        lines.extend(func(config))
    lines.append(suffix)
    return "\n".join(lines)


def insert_into_xonshrc(
    config,
    xonshrc="~/.xonshrc",
    prefix="# XONSH WEBCONFIG START",
    suffix="# XONSH WEBCONFIG END",
):
    """Places a config dict into the xonshrc."""
    # get current contents
    fname = os.path.expanduser(xonshrc)
    if os.path.isfile(fname):
        with open(fname) as f:
            s = f.read()
        before, _, s = s.partition(prefix)
        _, _, after = s.partition(suffix)
    else:
        before = after = ""
        dname = os.path.dirname(fname)
        if dname:
            os.makedirs(dname, exist_ok=True)
    # compute new values
    new = config_to_xonsh(config, prefix=prefix, suffix=suffix)
    # write out the file
    with open(fname, "w", encoding="utf-8") as f:
        f.write(before + new + after)
    return fname


class XonshConfigHTTPRequestHandler(server.SimpleHTTPRequestHandler):
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
        path = Path.cwd() / "index.html"
        tmpl = string.Template(path.read_text())
        navlinks = t.to_str(route.get_nav_links())
        body = t.to_str(route.get())  # type: ignore
        data = tmpl.substitute(navlinks=navlinks, body=body)
        return self._send(data)

    def _get_route(self, method: str):
        url = parse.urlparse(self.path)
        route_cls = Routes.registry.get(url.path)
        if route_cls and hasattr(route_cls, method):
            params = parse.parse_qs(url.query)
            return route_cls(url=url, params=params, env=XSH.env or {})

    def do_GET(self) -> None:
        route = self._get_route("get")
        if route is not None:
            return self.render_get(route)
        return super().do_GET()

    def _read_form(self):
        ctype, pdict = cgi.parse_header(self.headers.get("content-type"))
        # if ctype == "multipart/form-data":
        # postvars = cgi.parse_multipart(self.rfile, pdict)
        if ctype == "application/x-www-form-urlencoded":
            return parse.parse_qs(self._read(), keep_blank_values=True)
        return {}

    def do_POST(self):
        """Reads post request body"""
        route = self._get_route("post")
        if route is not None:
            # redirect after form submission
            data = cgi.FieldStorage(
                self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"}
            )
            new_route = route.post(data) or route
            return self._send(redirect=new_route.path)
        post_body = self._read()
        config = json.loads(post_body)
        print("Web Config Values:")
        pprint(config)
        fname = insert_into_xonshrc(config)
        print("Wrote out to " + fname)
        self._send(b"received post request:<br>" + post_body)


def make_parser():
    p = ArgumentParser("xonfig web")
    p.add_argument(
        "--no-browser",
        "-n",
        action="store_false",
        dest="browser",
        default=True,
        help="don't open browser",
    )
    return p


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
            print(f"Web config started at '{url}'. Hit Crtl+C to stop.")
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


def main(args=None):
    from xonsh.main import setup

    setup()

    p = make_parser()
    ns = p.parse_args(args=args)

    webconfig_dir = os.path.dirname(__file__)
    if webconfig_dir:
        os.chdir(webconfig_dir)
    serve(ns.browser)


if __name__ == "__main__":
    # watchexec -r -e py -- python -m xonsh.webconfig --no-browser
    main()
