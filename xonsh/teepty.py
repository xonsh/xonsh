"""This implements a psuedo-TTY that tees its output into a Python buffer.

This file was forked from a version distibuted under an MIT license and
Copyright (c) 2011 Joshua D. Bartlett. 
See http://sqizit.bartletts.id.au/2011/02/14/pseudo-terminals-in-python/ for 
more information.
"""
import io
import os
import sys
import tty
import pty
import array
import fcntl
import select
import signal
import termios

# The following escape codes are xterm codes.
# See http://rtfm.etla.org/xterm/ctlseq.html for more.
MODE_NUMS = ('1049', '47', '1047')
START_ALTERNATE_MODE = frozenset('\x1b[?{0}h'.format(i).encode() for i in MODE_NUMS)
END_ALTERNATE_MODE = frozenset('\x1b[?{0}l'.format(i).encode() for i in MODE_NUMS)
ALTERNATE_MODE_FLAGS = tuple(START_ALTERNATE_MODE) + tuple(END_ALTERNATE_MODE)

def _findfirst(s, substrs):
    """Finds whichever of the given substrings occurs first in the given string
    and returns that substring, or returns None if no such strings occur.
    """
    i = len(s)
    result = None
    for substr in substrs:
        pos = s.find(substr)
        if -1 < pos < i:
            i = pos
            result = substr
    return i, result


class TeePTY(object):
    """This class is a pseudo terminal that tees the stdout and stderr into a buffer."""

    def __init__(self, bufsize=1024):
        """
        Parameters
        ----------
        bufsize : int, optional
            The buffer size to read from the root terminal to/from the tee'd terminal.
        """
        self.bufsize = bufsize
        self.pid = self.master_fd = None
        self._in_alt_mode = False
        self.buffer = io.BytesIO()

    def __str__(self):
        return self.buffer.getvalue().decode()

    def spawn(self, argv=None):
        """Create a spawned process. Based on the code for pty.spawn().

        Parameters
        ----------
        argv : list of str, optional
            Arguments to pass in as subprocess. In None, will execute $SHELL.
        """
        assert self.master_fd is None
        if not argv:
            argv = [os.environ.get('SHELL', 'sh')]

        pid, master_fd = pty.fork()
        self.pid = pid
        self.master_fd = master_fd
        if pid == pty.CHILD:
            os.execlp(argv[0], *argv)

        old_handler = signal.signal(signal.SIGWINCH, self._signal_winch)
        try:
            mode = tty.tcgetattr(pty.STDIN_FILENO)
            tty.setraw(pty.STDIN_FILENO)
            restore = True
        except tty.error:    # This is the same as termios.error
            restore = False
        self._init_fd()
        try:
            self._copy()
        except (IOError, OSError):
            if restore:
                tty.tcsetattr(pty.STDIN_FILENO, tty.TCSAFLUSH, mode)

        os.close(master_fd)
        self.pid = self.master_fd = None
        signal.signal(signal.SIGWINCH, old_handler)

    def _init_fd(self):
        """Called once when the pty is first set up."""
        self._set_pty_size()

    def _signal_winch(self, signum, frame):
        """Signal handler for SIGWINCH - window size has changed."""
        self._set_pty_size()

    def _set_pty_size(self):
        """Sets the window size of the child pty based on the window size of 
        our own controlling terminal.
        """
        assert self.master_fd is not None
        # Get the terminal size of the real terminal, set it on the
        #       pseudoterminal.
        buf = array.array('h', [0, 0, 0, 0])
        fcntl.ioctl(pty.STDOUT_FILENO, termios.TIOCGWINSZ, buf, True)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, buf)

    def _copy(self):
        """Main select loop. Passes all data to self.master_read() or self.stdin_read().
        """
        assert self.master_fd is not None
        master_fd = self.master_fd
        bufsize = self.bufsize
        while True:
            try:
                rfds, wfds, xfds = select.select([master_fd, pty.STDIN_FILENO], [], [])
            except select.error as e:
                if e[0] == 4:   # Interrupted system call.
                    continue

            if master_fd in rfds:
                data = os.read(master_fd, bufsize)
                self.write_stdout(data)
            if pty.STDIN_FILENO in rfds:
                data = os.read(pty.STDIN_FILENO, bufsize)
                self.write_stdin(data)

    def _sanatize_data(self, data):
        i, flag = _findfirst(data, ALTERNATE_MODE_FLAGS)
        if flag is None and self._in_alt_mode:
            data = b''
        elif flag is not None:
            if flag in START_ALTERNATE_MODE:
                # This code is executed when the child process switches the terminal into
                # alternate mode. The line below assumes that the user has opened vim, 
                # less, or similar, and writes writes to stdin.
                d0 = data[:i] 
                self._in_alt_mode = True
                d1 = self._sanatize_data(data[i+len(flag):])
                data = d0 + d1
            elif flag in END_ALTERNATE_MODE:
                # This code is executed when the child process switches the terminal back
                # out of alternate mode. The line below assumes that the user has 
                # returned to the command prompt.
                self._in_alt_mode = False
                data = self._sanatize_data(data[i+len(flag):])
        return data

    def write_stdout(self, data):
        """Writes to stdout as if the child process had written the data (bytes)."""
        os.write(pty.STDOUT_FILENO, data)  # write to real terminal
        # tee to buffer
        data = self._sanatize_data(data)
        if len(data) > 0:
            self.buffer.write(data)

    def write_stdin(self, data):
        """Writes to the child process from its controlling terminal."""
        master_fd = self.master_fd
        assert master_fd is not None
        while len(data) > 0:
            n = os.write(master_fd, data)
            data = data[n:]


if __name__ == '__main__':
    tpty = TeePTY()
    tpty.spawn(sys.argv[1:])
    print(tpty.buffer.getvalue())
    print(tpty)
