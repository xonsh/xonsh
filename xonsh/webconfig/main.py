#!/usr/bin/env python3
from http import server
import socketserver
import webbrowser
import subprocess
import re, json, socket, os, sys, cgi, select


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
        print(post_body)
        self.wfile.write(b"received post request:<br>" + post_body)


def main():
    webconfig_dir = os.path.dirname(__file__)
    if webconfig_dir:
        os.chdir(webconfig_dir)

    PORT = 8421

    url = "http://localhost:{0}".format(PORT)
    print("Web config started at '{0}'. Hit enter to stop.".format(url))
    #webbrowser.open(url)

    Handler = XonshConfigHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
