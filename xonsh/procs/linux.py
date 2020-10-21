"""Linux-specific process tools."""
import os
import io
import sys
import time
import select
import socket
import argparse

import xonsh.lazyasd as xl
import xonsh.lazyimps as xli


@xl.lazyobject
def PTY_SERVER_PATH():
    return os.path.join(os.path.dirname(__file__), "pty_server.py")


# Maximum port value allowed
MAX_PTY_PORT = 65535
# This value is equal to `sum(map(ord, "xonsh")) * 64`, because why not
INITIAL_PTY_PORT = 35840


def _is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            #s.bind(("localhost", port))
        except socket.error as e:
            return False
    return True


def _find_next_open_port():
    """Gets the next valid port number."""
    for port in range(INITIAL_PTY_PORT, MAX_PTY_PORT):
        if _is_port_open(port):
            return port
    else:
        raise RuntimeError("No ports available for PTY subprocess command")


def serve_pty_command(command):
    """Starts up a PTY server for a specific command."""
    port = _find_next_open_port()
    os.spawnl(os.P_NOWAIT, sys.executable, PTY_SERVER_PATH, port, *command)
    return port


class PTY:
    def __init__(self):
        # open our controlling PTY
        child = 0
        pid = os.getpid()
        ptylink = os.readlink(f"/proc/{pid}/fd/{child}")
        self.pty = pty = io.open(ptylink, "rb+", buffering=0)

        # store our old termios settings so we can restore after
        # we are finished
        self.oldtermios = xli.termios.tcgetattr(self.pty)

        # get the current settings se we can modify them
        newattr = xli.termios.tcgetattr(self.pty)

        # set the terminal to uncanonical mode and turn off
        # input echo.
        newattr[3] &= ~xli.termios.ICANON & ~xli.termios.ECHO

        # don't handle ^C / ^Z / ^\
        newattr[6][xli.termios.VINTR] = b'\x00'
        newattr[6][xli.termios.VQUIT] = b'\x00'
        newattr[6][xli.termios.VSUSP] = b'\x00'

        # set our new attributes
        xli.termios.tcsetattr(self.pty, xli.termios.TCSADRAIN, newattr)

        # store the old fcntl flags
        self.oldflags = xli.fcntl.fcntl(self.pty, xli.fcntl.F_GETFL)
        # fcntl.fcntl(self.pty, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        # make the PTY non-blocking
        xli.fcntl.fcntl(self.pty, xli.fcntl.F_SETFL, self.oldflags | os.O_NONBLOCK)

    def read(self, size=8192):
        return self.pty.read(size)

    def write(self, data):
        ret = self.pty.write(data)
        self.pty.flush()
        return ret

    def fileno(self):
        return self.pty.fileno()

    def __del__(self):
        # restore the terminal settings on deletion
        xli.termios.tcsetattr(self.pty, xli.termios.TCSAFLUSH, self.oldtermios)
        xli.fcntl.fcntl(self.pty, xli.fcntl.F_SETFL, self.oldflags)


class PopenPTYClient:
    def __init__(self, args, bind=False, **kwargs):
        port = serve_pty_command(args)
        time.sleep(1)
        self.bind = bind
        self.addr = ("127.0.0.1", port)
        #self.addr = ("localhost", port)

        if self.bind:
            self.sock = socket.socket()
            self.sock.bind(self.addr)
            self.sock.listen(5)

        self.handle()

    def handle(self):
        if self.bind:
            sock, addr = self.sock.accept()
        else:
            addr = self.addr
            sock = socket.socket()
            sock.connect(addr)

        # create our PTY
        pty = PTY()

        # input buffers for the fd's
        buffers = [ [ sock, [] ], [ pty, [] ] ]
        def buffer_index(fd):
            for index, buffer in enumerate(buffers):
                if buffer[0] == fd:
                    return index

        readable_fds = [ sock, pty ]

        data = b" "
        all_data = b""
        # keep going until something deds
        while data:
            # if any of the fd's need to be written to, add them to the
            # writable_fds
            writable_fds = []
            for buffer in buffers:
                if buffer[1]:
                    writable_fds.append(buffer[0])

            r, w, x = select.select(readable_fds, writable_fds, [])

            # read from the fd's and store their input in the other fd's buffer
            for fd in r:
                buffer = buffers[buffer_index(fd) ^ 1][1]
                if hasattr(fd, "read"):
                    data = fd.read(8192)
                else:
                    data = fd.recv(8192)
                if data:
                    buffer.append(data)
                all_data += data

            # send data from each buffer onto the proper FD
            for fd in w:
                buffer = buffers[buffer_index(fd)][1]
                data = buffer[0]
                if hasattr(fd, "write"):
                    fd.write(data)
                else:
                    fd.send(data)
                buffer.remove(data)
                all_data += data

        # close the socket
        sock.close()
        with open("temp.txt", "wb") as f:
            f.write(all_data)

if __name__ == "__main__":
    # I could do this validation with regex.. but meh.
    def AddressString(value):
        address = value.split(":")

        if len(address) != 2:
            raise argparse.ArgumentTypeError("Address must be in format IP:Port.")

        if len(address[0].split(".")) != 4:
           raise argparse.ArgumentTypeError("Invalid IP length.")

        for octet in address[0].split("."):
            try:
                if int(octet) > 255 or int(octet) < 0:
                    raise argparse.ArgumentTypeError("Invalid octet in address.")
            except ValueError:
                raise argparse.ArgumentTypeError("Invalid octet in address.")

        try:
            address[1] = int(address[1])
            if address[1] < 0 or address[1] > 65535:
                raise argparse.ArgumentTypeError("Invalid port number")
        except ValueError:
            raise argparse.ArgumentTypeError("Invalid port number.")

        return tuple(address)

    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-b", "--bind", help="Reverse shell handler.",
                       action="store_true")
    group.add_argument("-c", "--connect", help="Bind shell handler.",
                       action="store_true")
    parser.add_argument("address", type=AddressString,
                        help="IP address/port to bind/connect to.")
    args = parser.parse_args()

    s = Shell(args.address, bind=args.bind)
    s.handle()
