#!/usr/bin/env python3
import os
import sys
import json
import socket
import webbrowser
import socketserver
from http import server
from pprint import pprint
from argparse import ArgumentParser


class XonshConfigHTTPRequestHandler(server.SimpleHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_POST(self):
        '''Reads post request body'''
        self._set_headers()
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)
        config = json.loads(post_body)
        print("Web Config Values:")
        pprint(config)
        self.wfile.write(b"received post request:<br>" + post_body)


def make_parser():
    p = ArgumentParser("xonfig-web")
    p.add_argument("--no-browser", action="store_false", dest="browser",
                   default=True, help="don't open browser")
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
        port += 1


if __name__ == "__main__":
    main()
