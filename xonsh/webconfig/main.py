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

    port = 8421
    Handler = XonshConfigHTTPRequestHandler
    while port <= 9310:
        try:
            with socketserver.TCPServer(("", port), Handler) as httpd:
                url = "http://localhost:{0}".format(port)
                #webbrowser.open(url)
                print("Web config started at '{0}'. Hit Crtl+C to stop.".format(url))
                httpd.serve_forever()
            break
        except socket.error:
            type, value = sys.exc_info()[:2]
            if "Address already in use" not in value:
                raise
        port += 1


if __name__ == "__main__":
    main()
