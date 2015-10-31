"""This implements a psuedo-TTY that tees its output into a Python buffer.

This file was forked from a version distibuted under an MIT license and
Copyright (c) 2011 Joshua D. Bartlett. 
See http://sqizit.bartletts.id.au/2011/02/14/pseudo-terminals-in-python/ for 
more information.
"""
import io
import re
import os
import sys
import tty
import pty
import time
import array
import fcntl
import select
import signal
import termios
import tempfile
import threading

# The following escape codes are xterm codes.
# See http://rtfm.etla.org/xterm/ctlseq.html for more.
MODE_NUMS = ('1049', '47', '1047')
START_ALTERNATE_MODE = frozenset('\x1b[?{0}h'.format(i).encode() for i in MODE_NUMS)
END_ALTERNATE_MODE = frozenset('\x1b[?{0}l'.format(i).encode() for i in MODE_NUMS)
ALTERNATE_MODE_FLAGS = tuple(START_ALTERNATE_MODE) + tuple(END_ALTERNATE_MODE)

RE_HIDDEN = re.compile(b'(\001.*?\002)')
RE_COLOR = re.compile(b'\033\[\d+;?\d*m')

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


def _on_main_thread():
    """Checks if we are on the main thread or not. Duplicated from xonsh.tools 
    here so that this module only relies on the Python standrd library.
    """
    return threading.current_thread() is threading.main_thread()


def _find_error_code(e):
    """Gets the approriate error code for an exception e, see
    http://tldp.org/LDP/abs/html/exitcodes.html for exit codes.
    """
    if isinstance(e, PermissionError):
        code = 126
    elif isinstance(e, FileNotFoundError):
        code = 127
    else:
        code = 1
    return code


class TeePTY(object):
    """This class is a pseudo terminal that tees the stdout and stderr into a buffer."""

    def __init__(self, bufsize=1024, remove_color=True, encoding='utf-8', 
                 errors='strict'):
        """
        Parameters
        ----------
        bufsize : int, optional
            The buffer size to read from the root terminal to/from the tee'd terminal.
        remove_color : bool, optional
            Removes color codes from the tee'd buffer, though not the TTY.
        encoding : str, optional
            The encoding to use when decoding into a str.
        errors : str, optional
            The encoding error flag to use when decoding into a str.
        """
        self.bufsize = bufsize
        self.pid = self.master_fd = None
        self._in_alt_mode = False
        self.remove_color = remove_color
        self.encoding = encoding
        self.errors = errors
        self.buffer = io.BytesIO()
        self.returncode = None
        self._temp_stdin = None

    def __str__(self):
        return self.buffer.getvalue().decode(encoding=self.encoding, 
                                             errors=self.errors)

    def __del__(self):
        if self._temp_stdin is not None:
            self._temp_stdin.close()
            self._temp_stdin = None

    def spawn(self, argv=None, env=None, stdin=None, delay=None):
        """Create a spawned process. Based on the code for pty.spawn().
        This cannot be used except from the main thread.

        Parameters
        ----------
        argv : list of str, optional
            Arguments to pass in as subprocess. In None, will execute $SHELL.
        env : Mapping, optional
            Environment to pass execute in.
        delay : float, optional
            Delay timing before executing process if piping in data. The value
            is passed into time.sleep() so it is in [seconds]. If delay is None,
            its value will attempted to be looked up from the environment
            variable $TEEPTY_PIPE_DELAY, from the passed in env or os.environ.
            If not present or not positive valued, no delay is used.

        Returns
        -------
        returncode : int
            Return code for the spawned process.
        """
        assert self.master_fd is None
        self._in_alt_mode = False
        if not argv:
            argv = [os.environ.get('SHELL', 'sh')]
        argv = self._put_stdin_in_argv(argv, stdin)

        pid, master_fd = pty.fork()
        self.pid = pid
        self.master_fd = master_fd
        if pid == pty.CHILD:
            # determine if a piping delay is needed.
            if self._temp_stdin is not None:
                self._delay_for_pipe(env=env, delay=delay)
            # ok, go
            try:
                if env is None:
                    os.execvp(argv[0], argv)
                else:
                    os.execvpe(argv[0], argv, env)
            except OSError as e:
                os._exit(_find_error_code(e))
        else:
            self._pipe_stdin(stdin)

        on_main_thread = _on_main_thread()
        if on_main_thread:
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

        _, self.returncode = os.waitpid(pid, 0)
        os.close(master_fd)
        self.master_fd = None
        self._in_alt_mode = False
        if on_main_thread:
            signal.signal(signal.SIGWINCH, old_handler)
        return self.returncode

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
            except OSError as e:
                if e.errno == 4:  # Interrupted system call. 
                    continue      # This happens at terminal resize.
            if master_fd in rfds:
                data = os.read(master_fd, bufsize)
                self.write_stdout(data)
            if pty.STDIN_FILENO in rfds:
                data = os.read(pty.STDIN_FILENO, bufsize)
                self.write_stdin(data)

    def _sanatize_data(self, data):
        i, flag = _findfirst(data, ALTERNATE_MODE_FLAGS)
        if flag is None and self._in_alt_mode:
            return  b''
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
        data = RE_HIDDEN.sub(b'', data)
        if self.remove_color:
            data = RE_COLOR.sub(b'', data)
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

    def _stdin_filename(self, stdin):
        if stdin is None: 
            rtn = None
        elif isinstance(stdin, io.FileIO) and os.path.isfile(stdin.name):
            rtn = stdin.name
        elif isinstance(stdin, (io.BufferedIOBase, str, bytes)):
            self._temp_stdin = tsi = tempfile.NamedTemporaryFile()
            rtn = tsi.name
        else:
            raise ValueError('stdin not understood {0!r}'.format(stdin))
        return rtn

    def _put_stdin_in_argv(self, argv, stdin):
        stdin_filename = self._stdin_filename(stdin)
        if stdin_filename is None:
            return argv
        argv = list(argv)
        # a lone dash '-' argument means stdin
        if argv.count('-') == 0:
            argv.append(stdin_filename)
        else:
            argv[argv.index('-')] = stdin_filename
        return argv

    def _pipe_stdin(self, stdin):
        if stdin is None or isinstance(stdin, io.FileIO):
            return None
        tsi = self._temp_stdin
        bufsize = self.bufsize
        if isinstance(stdin, io.BufferedIOBase):
            buf = stdin.read(bufsize)
            while len(buf) != 0:
                tsi.write(buf)
                tsi.flush()
                buf = stdin.read(bufsize)
        elif isinstance(stdin, (str, bytes)):
            raw = stdin.encode() if isinstance(stdin, str) else stdin
            for i in range((len(raw)//bufsize) + 1):
                tsi.write(raw[i*bufsize:(i + 1)*bufsize])
                tsi.flush()
        else:
            raise ValueError('stdin not understood {0!r}'.format(stdin))

    def _delay_for_pipe(self, env=None, delay=None):
        # This delay is sometimes needed because the temporary stdin file that 
        # is being written (the pipe) may not have even hits its first flush()
        # call by the time the spawned process starts up and determines there 
        # is nothing in the file. The spawn can thus exit, without doing any
        # real work.  Consider the case of piping something into grep:
        #
        #   $ ps aux | grep root
        #
        # grep will exit on EOF and so there is a race between the buffersize 
        # and flushing the temporary file and grep.  However, this race is not
        # always meaningful. Pagers, for example, update when the file is written
        # to. So what is important is that we start the spawned process ASAP:
        #
        #   $ ps aux | less
        #
        # So there is a push-and-pull between the the competing objectives of
        # not blocking and letting the spawned process have enough to work with
        # such that it doesn't exit prematurely.  Unfortunately, there is no
        # way to know a priori how big the file is, how long the spawned process
        # will run for, etc. Thus as user-definable delay let's the user 
        # find something that works for them.
        if delay is None:
            delay = (env or os.environ).get('TEEPTY_PIPE_DELAY', -1.0)
        delay = float(delay)
        if 0.0 < delay:
            time.sleep(delay)
        

if __name__ == '__main__':
    tpty = TeePTY()
    tpty.spawn(sys.argv[1:])
    print('-=-'*10)
    print(tpty.buffer.getvalue())
    print('-=-'*10)
    print(tpty)
    print('-=-'*10)
    print('Returned with status {0}'.format(tpty.returncode))
