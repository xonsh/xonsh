"""Python TCP PTY server.

Binds a PTY to a TCP port on the host it is ran on.
"""
import os
import sys
import pty
import socket


def spawn(port, argv):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', port))
    s.listen(1)
    (rem, addr) = s.accept()
    os.dup2(rem.fileno(),0)
    os.dup2(rem.fileno(),1)
    os.dup2(rem.fileno(),2)
    pty.spawn(argv)
    s.close()


def main(args=None):
    args = sys.argv if args is None else args
    port = int(args[1])
    argv = args[2:]
    spawn(port, argv)


if __name__ == "__main__":
    main()