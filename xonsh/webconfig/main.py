#!/usr/bin/env python3
import os
import sys
import json
import socket
import socketserver
from http import server
from pprint import pprint
from argparse import ArgumentParser


RENDERERS = []


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
    return ["$XONSH_COLOR_STYLE = {!r}".format(style)]


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
        with open(fname, "r") as f:
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
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_POST(self):
        """Reads post request body"""
        self._set_headers()
        content_len = int(self.headers.get("content-length", 0))
        post_body = self.rfile.read(content_len)
        config = json.loads(post_body)
        print("Web Config Values:")
        pprint(config)
        fname = insert_into_xonshrc(config)
        print("Wrote out to " + fname)
        self.wfile.write(b"received post request:<br>" + post_body)


def make_parser():
    p = ArgumentParser("xonfig web")
    p.add_argument(
        "--no-browser",
        action="store_false",
        dest="browser",
        default=True,
        help="don't open browser",
    )
    return p


def main(args=None):
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
                url = "http://localhost:{0}".format(port)
                print("Web config started at '{0}'. Hit Crtl+C to stop.".format(url))
                if ns.browser:
                    import webbrowser

                    webbrowser.open(url)
                httpd.serve_forever()
            break
        except socket.error:
            type, value = sys.exc_info()[:2]
            if "Address already in use" not in str(value):
                raise
        except KeyboardInterrupt:
            break
        port += 1


if __name__ == "__main__":
    main()
