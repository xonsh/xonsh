#!/usr/bin/python

try:  # Python2
    import SimpleHTTPServer
except ImportError:  # Python3
    import http.server as SimpleHTTPServer
try:  # Python2
    import SocketServer
except ImportError:  # Python3
    import socketserver as SocketServer
import webbrowser
import subprocess
import re, json, socket, os, sys, cgi, select


def run_xonsh_cmd(text):
    from subprocess import PIPE

    p = subprocess.Popen(["xonsh"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate(text)
    return out, err


class XonshVar:
    """ A class that represents a variable """

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.universal = False
        self.exported = False

    def get_json_obj(self):
        # Return an array(3): name, value, flags
        flags = []
        if self.universal:
            flags.append("universal")
        if self.exported:
            flags.append("exported")
        return [self.name, self.value, ", ".join(flags)]


class XonshConfigHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_get_colors(self):
        "Look for xonsh_color_*"
        result = []
        out, err = run_xonsh_cmd("set")
        for match in re.finditer(r"xonsh_color_(\S+) (.+)", out):
            color_name, color_value = match.group(1, 2)
            result.append([color_name.strip(), color_value.strip()])
        print(result)
        return result

    def do_get_functions(self):
        out, err = run_xonsh_cmd("functions")
        out = out.strip()

        # Not sure why xonsh sometimes returns this with newlines
        if "\n" in out:
            return out.split("\n")
        else:
            return out.strip().split(", ")

    def do_get_variable_names(self, cmd):
        " Given a command like 'set -U' return all the variable names "
        out, err = run_xonsh_cmd(cmd)
        return out.split("\n")

    def do_get_variables(self):
        out, err = run_xonsh_cmd("set")

        # Put all the variables into a dictionary
        vars = {}
        for line in out.split("\n"):
            comps = line.split(" ", 1)
            if len(comps) < 2:
                continue
            xonsh_var = XonshVar(comps[0], comps[1])
            vars[xonsh_var.name] = xonsh_var

        # Mark universal variables
        for name in self.do_get_variable_names("set -nU"):
            if name in vars:
                vars[name].universal = True
        # Mark exported variables
        for name in self.do_get_variable_names("set -nx"):
            if name in vars:
                vars[name].exported = True

        return [vars[key].get_json_obj() for key in sorted(vars.keys(), key=str.lower)]

    def do_get_color_for_variable(self, name):
        "Return the color with the given name, or the empty string if there is none"
        out, err = run_xonsh_cmd("echo -n $" + name)
        return out

    def do_GET(self):
        p = self.path
        if p == "/colors/":
            output = self.do_get_colors()
        elif p == "/functions/":
            output = self.do_get_functions()
        elif p == "/variables/":
            output = self.do_get_variables()
        elif re.match(r"/color/(\w+)/", p):
            name = re.match(r"/color/(\w+)/", p).group(1)
            output = self.do_get_color_for_variable(name)
        else:
            return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

        # Return valid output
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.wfile.write("\n")

        # Output JSON
        print(len(output))
        print(output)
        json.dump(output, self.wfile)


where = os.path.dirname(sys.argv[0])
os.chdir(where)

PORT = 8000
while PORT <= 9000:
    try:
        Handler = XonshConfigHTTPRequestHandler
        httpd = SocketServer.TCPServer(("", PORT), Handler)
        # Success
        break
    except socket.error:
        type, value = sys.exc_info()[:2]
        if "Address already in use" not in value:
            break
    PORT += 1

if PORT > 9000:
    print("Unable to start a web server")
    sys.exit(-1)


url = "http://localhost:{0}".format(PORT)

print("Web config started at '{0}'. Hit enter to stop.".format(url))
webbrowser.open(url)

# Select on stdin and httpd
stdin_no = sys.stdin.fileno()
while True:
    ready_read = select.select([sys.stdin.fileno(), httpd.fileno()], [], [])
    if ready_read[0][0] < 1:
        print("Shutting down.")
        # Consume the newline so it doesn't get printed by the caller
        sys.stdin.readline()
        break
    else:
        httpd.handle_request()
