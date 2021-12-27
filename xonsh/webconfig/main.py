#!/usr/bin/env python3
import os
import string
import sys
import json
import socketserver
from pathlib import Path
from urllib import parse
from http import server
from pprint import pprint
from argparse import ArgumentParser
import typing as tp

from . import tags as t
from . import xonsh_data

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
    def _send(self, data: "bytes|dict|str", status=200):
        self.send_response(status)

        if isinstance(data, bytes):
            content_type = "text/html"
        elif isinstance(data, dict):
            content_type = "application/json"
            data = json.dumps(data).encode()
        else:
            content_type = "text/html"
            data = str(data).encode()

        self.send_header("Content-type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def _read(self):
        content_len = int(self.headers.get("content-length", 0))
        return self.rfile.read(content_len)

    def do_GET(self) -> None:
        url = parse.urlparse(self.path)
        if url.path == "/data.json":
            colors = list(xonsh_data.render_colors())
            prompts = list(xonsh_data.render_prompts())
            return self._send(
                {
                    "xontribs": list(xonsh_data.render_xontribs()),
                    "colors": colors,
                    "prompts": prompts,
                    "colorValue": colors[0],
                    "promptValue": prompts[0],
                }
            )
        if url.path == "/":
            path = Path(__file__).with_name("index.html")
            tmpl = string.Template(path.read_text())
            navlinks = [
                t.nav_item()[
                    t.nav_link(href="/")["Colors"],
                ],
                t.nav_item()[
                    t.nav_link(href="/")["Prompts"],
                ],
                t.nav_item()[
                    t.nav_link(href="/")["Xontribs"],
                ],
            ]

            data = tmpl.substitute(navlinks=t.to_str(navlinks), body="")
            return self._send(data)
        return super().do_GET()

    def do_POST(self):
        """Reads post request body"""
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


def main(args=None):
    from xonsh.main import setup

    setup()

    p = make_parser()
    ns = p.parse_args(args=args)

    webconfig_dir = os.path.dirname(__file__)
    if webconfig_dir:
        os.chdir(webconfig_dir)

    port = 8421
    Handler = XonshConfigHTTPRequestHandler
    while port <= 9310:
        try:
            with socketserver.TCPServer(("", port), Handler) as httpd:
                url = f"http://localhost:{port}"
                print(f"Web config started at '{url}'. Hit Crtl+C to stop.")
                if ns.browser:
                    import webbrowser

                    webbrowser.open(url)
                httpd.serve_forever()
            break
        except OSError:
            type, value = sys.exc_info()[:2]
            if "Address already in use" not in str(value):
                raise
        except KeyboardInterrupt:
            break
        port += 1


if __name__ == "__main__":
    # watchexec -r -e py -- python -m xonsh.webconfig --no-browser
    main()
