# -*- coding: utf-8 -*-
"""Interface for running Python functions as subprocess-mode commands.

Code for several helper methods in the `ProcProxy` class have been reproduced
without modification from `subprocess.py` in the Python 3.4.2 standard library.
The contents of `subprocess.py` (and, thus, the reproduced methods) are
Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se> and were
licensed to the Python Software foundation under a Contributor Agreement.
"""
import io
import os
import re
import sys
import time
import queue
import array
import ctypes
import signal
import inspect
import builtins
import functools
import threading
import subprocess
import collections.abc as cabc

from xonsh.platform import (ON_WINDOWS, ON_POSIX, CAN_RESIZE_WINDOW,
                            LFLAG, CC)
from xonsh.tools import (redirect_stdout, redirect_stderr, print_exception,
                         XonshCalledProcessError, findfirst, on_main_thread,
                         XonshError, format_std_prepost)
from xonsh.lazyasd import lazyobject, LazyObject
from xonsh.jobs import wait_for_active_job, give_terminal_to, _continue
from xonsh.lazyimps import fcntl, termios, _winapi, msvcrt, winutils
# these decorators are imported for users back-compatible
from xonsh.tools import unthreadable, uncapturable  # NOQA

# foreground has be deprecated
foreground = unthreadable


@lazyobject
def STDOUT_CAPTURE_KINDS():
    return frozenset(['stdout', 'object'])


# The following escape codes are xterm codes.
# See http://rtfm.etla.org/xterm/ctlseq.html for more.
MODE_NUMS = ('1049', '47', '1047')
START_ALTERNATE_MODE = LazyObject(
    lambda: frozenset('\x1b[?{0}h'.format(i).encode() for i in MODE_NUMS),
    globals(), 'START_ALTERNATE_MODE')
END_ALTERNATE_MODE = LazyObject(
    lambda: frozenset('\x1b[?{0}l'.format(i).encode() for i in MODE_NUMS),
    globals(), 'END_ALTERNATE_MODE')
ALTERNATE_MODE_FLAGS = LazyObject(
    lambda: tuple(START_ALTERNATE_MODE) + tuple(END_ALTERNATE_MODE),
    globals(), 'ALTERNATE_MODE_FLAGS')
RE_HIDDEN_BYTES = LazyObject(lambda: re.compile(b'(\001.*?\002)'),
                             globals(), 'RE_HIDDEN')


@lazyobject
def RE_VT100_ESCAPE():
    return re.compile(b'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')


@lazyobject
def RE_HIDE_ESCAPE():
    return re.compile(b'(' + RE_HIDDEN_BYTES.pattern +
                      b'|' + RE_VT100_ESCAPE.pattern + b')')


class QueueReader:
    """Provides a file-like interface to reading from a queue."""

    def __init__(self, fd, timeout=None):
        """
        Parameters
        ----------
        fd : int
            A file descriptor
        timeout : float or None, optional
            The queue reading timeout.
        """
        self.fd = fd
        self.timeout = timeout
        self.closed = False
        self.queue = queue.Queue()
        self.thread = None

    def close(self):
        """close the reader"""
        self.closed = True

    def is_fully_read(self):
        """Returns whether or not the queue is fully read and the reader is
        closed.
        """
        return (self.closed
                and (self.thread is None or not self.thread.is_alive())
                and self.queue.empty())

    def read_queue(self):
        """Reads a single chunk from the queue. This is blocking if
        the timeout is None and non-blocking otherwise.
        """
        try:
            return self.queue.get(block=True, timeout=self.timeout)
        except queue.Empty:
            return b''

    def read(self, size=-1):
        """Reads bytes from the file."""
        i = 0
        buf = b''
        while size < 0 or i != size:
            line = self.read_queue()
            if line:
                buf += line
            else:
                break
            i += len(line)
        return buf

    def readline(self, size=-1):
        """Reads a line, or a partial line from the file descriptor."""
        i = 0
        nl = b'\n'
        buf = b''
        while size < 0 or i != size:
            line = self.read_queue()
            if line:
                buf += line
                if line.endswith(nl):
                    break
            else:
                break
            i += len(line)
        return buf

    def _read_all_lines(self):
        """This reads all remaining lines in a blocking fashion."""
        lines = []
        while not self.is_fully_read():
            chunk = self.read_queue()
            lines.extend(chunk.splitlines(keepends=True))
        return lines

    def readlines(self, hint=-1):
        """Reads lines from the file descriptor. This is blocking for negative
        hints (i.e. read all the remaining lines) and non-blocking otherwise.
        """
        if hint == -1:
            return self._read_all_lines()
        lines = []
        while len(lines) != hint:
            chunk = self.read_queue()
            if not chunk:
                break
            lines.extend(chunk.splitlines(keepends=True))
        return lines

    def fileno(self):
        """Returns the file descriptor number."""
        return self.fd

    @staticmethod
    def readable():
        """Returns true, because this object is always readable."""
        return True

    def iterqueue(self):
        """Iterates through all remaining chunks in a blocking fashion."""
        while not self.is_fully_read():
            chunk = self.read_queue()
            if not chunk:
                continue
            yield chunk


def populate_fd_queue(reader, fd, queue):
    """Reads 1 kb of data from a file descriptor into a queue.
    If this ends or fails, it flags the calling reader object as closed.
    """
    while True:
        try:
            c = os.read(fd, 1024)
        except OSError:
            reader.closed = True
            break
        if c:
            queue.put(c)
        else:
            reader.closed = True
            break


class NonBlockingFDReader(QueueReader):
    """A class for reading characters from a file descriptor on a background
    thread. This has the advantages that the calling thread can close the
    file and that the reading does not block the calling thread.
    """

    def __init__(self, fd, timeout=None):
        """
        Parameters
        ----------
        fd : int
            A file descriptor
        timeout : float or None, optional
            The queue reading timeout.
        """
        super().__init__(fd, timeout=timeout)
        # start reading from stream
        self.thread = threading.Thread(target=populate_fd_queue,
                                       args=(self, self.fd, self.queue))
        self.thread.daemon = True
        self.thread.start()


def populate_buffer(reader, fd, buffer, chunksize):
    """Reads bytes from the file descriptor and copies them into a buffer.
    The reads happend in parallel, using pread(), and is thus only
    availabe on posix. If the read fails for any reason, the reader is
    flagged as closed.
    """
    offset = 0
    while True:
        try:
            buf = os.pread(fd, chunksize, offset)
        except OSError:
            reader.closed = True
            break
        if buf:
            buffer.write(buf)
            offset += len(buf)
        else:
            reader.closed = True
            break


class BufferedFDParallelReader:
    """Buffered, parallel background thread reader."""

    def __init__(self, fd, buffer=None, chunksize=1024):
        """
        Parameters
        ----------
        fd : int
            File descriptor from which to read.
        buffer : binary file-like or None, optional
            A buffer to write bytes into. If None, a new BytesIO object
            is created.
        chunksize : int, optional
            The max size of the parallel reads, default 1 kb.
        """
        self.fd = fd
        self.buffer = io.BytesIO() if buffer is None else buffer
        self.chunksize = chunksize
        self.closed = False
        # start reading from stream
        self.thread = threading.Thread(target=populate_buffer,
                                       args=(self, fd, self.buffer, chunksize))
        self.thread.daemon = True

        self.thread.start()


def _expand_console_buffer(cols, max_offset, expandsize, orig_posize, fd):
    # if we are getting close to the end of the console buffer,
    # expand it so that we can read from it successfully.
    if cols == 0:
        return orig_posize[-1], max_offset, orig_posize
    rows = ((max_offset + expandsize)//cols) + 1
    winutils.set_console_screen_buffer_size(cols, rows, fd=fd)
    orig_posize = orig_posize[:3] + (rows,)
    max_offset = (rows - 1) * cols
    return rows, max_offset, orig_posize


def populate_console(reader, fd, buffer, chunksize, queue, expandsize=None):
    """Reads bytes from the file descriptor and puts lines into the queue.
    The reads happend in parallel,
    using xonsh.winutils.read_console_output_character(),
    and is thus only available on windows. If the read fails for any reason,
    the reader is flagged as closed.
    """
    # OK, so this function is super annoying because Windows stores its
    # buffers as a 2D regular, dense array -- without trailing newlines.
    # Meanwhile, we want to add *lines* to the queue. Also, as is typical
    # with parallel reads, the entire buffer that you ask for may not be
    # filled. Thus we have to deal with the full generality.
    #   1. reads may end in the middle of a line
    #   2. excess whitespace at the end of a line may not be real, unless
    #   3. you haven't read to the end of the line yet!
    # So there are alignment issues everywhere.  Also, Windows will automatically
    # read past the current cursor position, even though there is presumably
    # nothing to see there.
    #
    # These chunked reads basically need to happen like this because,
    #   a. The default buffer size is HUGE for the console (90k lines x 120 cols)
    #      as so we can't just read in everything at the end and see what we
    #      care about without a noticible performance hit.
    #   b. Even with this huge size, it is still possible to write more lines than
    #      this, so we should scroll along with the console.
    # Unfortnately, because we do not have control over the terminal emulator,
    # It is not possible to compute how far back we should set the begining
    # read position because we don't know how many characters have been popped
    # off the top of the buffer. If we did somehow know this number we could do
    # something like the following:
    #
    #    new_offset = (y*cols) + x
    #    if new_offset == max_offset:
    #        new_offset -= scolled_offset
    #        x = new_offset%cols
    #        y = new_offset//cols
    #        continue
    #
    # So this method is imperfect and only works as long as the sceen has
    # room to expand to.  Thus the trick here is to expand the screen size
    # when we get close enough to the end of the screen. There remain some
    # async issues related to not being able to set the cursor position.
    # but they just affect the alignment / capture of the output of the
    # first command run after a screen resize.
    if expandsize is None:
        expandsize = 100 * chunksize
    x, y, cols, rows = posize = winutils.get_position_size(fd)
    pre_x = pre_y = -1
    orig_posize = posize
    offset = (cols*y) + x
    max_offset = (rows - 1) * cols
    # I believe that there is a bug in PTK that if we reset the
    # cursor position, the cursor on the next prompt is accidentally on
    # the next line.  If this is fixed, uncomment the following line.
    # if max_offset < offset + expandsize:
    #     rows, max_offset, orig_posize = _expand_console_buffer(
    #                                        cols, max_offset, expandsize,
    #                                        orig_posize, fd)
    #     winutils.set_console_cursor_position(x, y, fd=fd)
    while True:
        posize = winutils.get_position_size(fd)
        offset = (cols*y) + x
        if ((posize[1], posize[0]) <= (y, x) and posize[2:] == (cols, rows)) or \
                (pre_x == x and pre_y == y):
            # already at or ahead of the current cursor position.
            if reader.closed:
                break
            else:
                time.sleep(reader.timeout)
                continue
        elif max_offset <= offset + expandsize:
            ecb = _expand_console_buffer(cols, max_offset, expandsize,
                                         orig_posize, fd)
            rows, max_offset, orig_posize = ecb
            continue
        elif posize[2:] == (cols, rows):
            # cursor updated but screen size is the same.
            pass
        else:
            # screen size changed, which is offset preserving
            orig_posize = posize
            cols, rows = posize[2:]
            x = offset % cols
            y = offset // cols
            pre_x = pre_y = -1
            max_offset = (rows - 1) * cols
            continue
        try:
            buf = winutils.read_console_output_character(x=x, y=y, fd=fd,
                                                         buf=buffer,
                                                         bufsize=chunksize,
                                                         raw=True)
        except (OSError, IOError):
            reader.closed = True
            break
        # cursor position and offset
        if not reader.closed:
            buf = buf.rstrip()
        nread = len(buf)
        if nread == 0:
            time.sleep(reader.timeout)
            continue
        cur_x, cur_y = posize[0], posize[1]
        cur_offset = (cols*cur_y) + cur_x
        beg_offset = (cols*y) + x
        end_offset = beg_offset + nread
        if end_offset > cur_offset and cur_offset != max_offset:
            buf = buf[:cur_offset-end_offset]
        # convert to lines
        xshift = cols - x
        yshift = (nread // cols) + (1 if nread % cols > 0 else 0)
        lines = [buf[:xshift]]
        lines += [buf[l * cols + xshift:(l + 1) * cols + xshift]
                  for l in range(yshift)]
        lines = [line for line in lines if line]
        if not lines:
            time.sleep(reader.timeout)
            continue
        # put lines in the queue
        nl = b'\n'
        for line in lines[:-1]:
            queue.put(line.rstrip() + nl)
        if len(lines[-1]) == xshift:
            queue.put(lines[-1].rstrip() + nl)
        else:
            queue.put(lines[-1])
        # update x and y locations
        if (beg_offset + len(buf)) % cols == 0:
            new_offset = beg_offset + len(buf)
        else:
            new_offset = beg_offset + len(buf.rstrip())
        pre_x = x
        pre_y = y
        x = new_offset % cols
        y = new_offset // cols
        time.sleep(reader.timeout)


class ConsoleParallelReader(QueueReader):
    """Parallel reader for consoles that runs in a background thread.
    This is only needed, available, and useful on Windows.
    """

    def __init__(self, fd, buffer=None, chunksize=1024, timeout=None):
        """
        Parameters
        ----------
        fd : int
            Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
            and 2 for stderr.
        buffer : ctypes.c_wchar_p, optional
            An existing buffer to (re-)use.
        chunksize : int, optional
            The max size of the parallel reads, default 1 kb.
        timeout : float, optional
            The queue reading timeout.
        """
        timeout = timeout or builtins.__xonsh_env__.get('XONSH_PROC_FREQUENCY')
        super().__init__(fd, timeout=timeout)
        self._buffer = buffer  # this cannot be public
        if buffer is None:
            self._buffer = ctypes.c_char_p(b" " * chunksize)
        self.chunksize = chunksize
        # start reading from stream
        self.thread = threading.Thread(target=populate_console,
                                       args=(self, fd, self._buffer,
                                             chunksize, self.queue))
        self.thread.daemon = True
        self.thread.start()


def safe_fdclose(handle, cache=None):
    """Closes a file handle in the safest way possible, and potentially
    storing the result.
    """
    if cache is not None and cache.get(handle, False):
        return
    status = True
    if handle is None:
        pass
    elif isinstance(handle, int):
        if handle >= 3:
            # don't close stdin, stdout, stderr, -1
            try:
                os.close(handle)
            except OSError:
                status = False
    elif handle is sys.stdin or handle is sys.stdout or handle is sys.stderr:
        # don't close stdin, stdout, or stderr
        pass
    else:
        try:
            handle.close()
        except OSError:
            status = False
    if cache is not None:
        cache[handle] = status


def safe_flush(handle):
    """Attempts to safely flush a file handle, returns success bool."""
    status = True
    try:
        handle.flush()
    except OSError:
        status = False
    return status


def still_writable(fd):
    """Determines whether a file descriptior is still writable by trying to
    write an empty string and seeing if it fails.
    """
    try:
        os.write(fd, b'')
        status = True
    except OSError:
        status = False
    return status


class PopenThread(threading.Thread):
    """A thread for running and managing subprocess. This allows reading
    from the stdin, stdout, and stderr streams in a non-blocking fashion.

    This takes the same arguments and keyword arguments as regular Popen.
    This requires that the captured_stdout and captured_stderr attributes
    to be set following instantiation.
    """

    def __init__(self, *args, stdin=None, stdout=None, stderr=None, **kwargs):
        super().__init__()
        self.lock = threading.RLock()
        env = builtins.__xonsh_env__
        # stdin setup
        self.orig_stdin = stdin
        if stdin is None:
            self.stdin_fd = 0
        elif isinstance(stdin, int):
            self.stdin_fd = stdin
        else:
            self.stdin_fd = stdin.fileno()
        self.store_stdin = env.get('XONSH_STORE_STDIN')
        self.timeout = env.get('XONSH_PROC_FREQUENCY')
        self.in_alt_mode = False
        self.stdin_mode = None
        # stdout setup
        self.orig_stdout = stdout
        self.stdout_fd = 1 if stdout is None else stdout.fileno()
        self._set_pty_size()
        # stderr setup
        self.orig_stderr = stderr
        # Set some signal handles, if we can. Must come before process
        # is started to prevent deadlock on windows
        self.proc = None  # has to be here for closure for handles
        self.old_int_handler = self.old_winch_handler = None
        self.old_tstp_handler = self.old_quit_handler = None
        if on_main_thread():
            self.old_int_handler = signal.signal(signal.SIGINT,
                                                 self._signal_int)
            if ON_POSIX:
                self.old_tstp_handler = signal.signal(signal.SIGTSTP,
                                                      self._signal_tstp)
                self.old_quit_handler = signal.signal(signal.SIGQUIT,
                                                      self._signal_quit)
            if CAN_RESIZE_WINDOW:
                self.old_winch_handler = signal.signal(signal.SIGWINCH,
                                                       self._signal_winch)
        # start up process
        if ON_WINDOWS and stdout is not None:
            os.set_handle_inheritable(stdout.fileno(), False)
        self.proc = proc = subprocess.Popen(*args,
                                            stdin=stdin,
                                            stdout=stdout,
                                            stderr=stderr,
                                            **kwargs)
        self.pid = proc.pid
        self.universal_newlines = uninew = proc.universal_newlines
        if uninew:
            self.encoding = enc = env.get('XONSH_ENCODING')
            self.encoding_errors = err = env.get('XONSH_ENCODING_ERRORS')
            self.stdin = io.BytesIO()  # stdin is always bytes!
            self.stdout = io.TextIOWrapper(io.BytesIO(), encoding=enc, errors=err)
            self.stderr = io.TextIOWrapper(io.BytesIO(), encoding=enc, errors=err)
        else:
            self.encoding = self.encoding_errors = None
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
        self.suspended = False
        self.prevs_are_closed = False
        self.start()

    def run(self):
        """Runs the subprocess by performing a parallel read on stdin if allowed,
        and copying bytes from captured_stdout to stdout and bytes from
        captured_stderr to stderr.
        """
        proc = self.proc
        spec = self._wait_and_getattr('spec')
        # get stdin and apply parallel reader if needed.
        stdin = self.stdin
        if self.orig_stdin is None:
            origin = None
        elif ON_POSIX and self.store_stdin:
            origin = self.orig_stdin
            origfd = origin if isinstance(origin, int) else origin.fileno()
            origin = BufferedFDParallelReader(origfd, buffer=stdin)
        else:
            origin = None
        # get non-blocking stdout
        stdout = self.stdout.buffer if self.universal_newlines else self.stdout
        capout = spec.captured_stdout
        if capout is None:
            procout = None
        else:
            procout = NonBlockingFDReader(capout.fileno(), timeout=self.timeout)
        # get non-blocking stderr
        stderr = self.stderr.buffer if self.universal_newlines else self.stderr
        caperr = spec.captured_stderr
        if caperr is None:
            procerr = None
        else:
            procerr = NonBlockingFDReader(caperr.fileno(), timeout=self.timeout)
        # initial read from buffer
        self._read_write(procout, stdout, sys.__stdout__)
        self._read_write(procerr, stderr, sys.__stderr__)
        # loop over reads while process is running.
        i = j = cnt = 1
        while proc.poll() is None:
            # this is here for CPU performance reasons.
            if i + j == 0:
                cnt = min(cnt + 1, 1000)
                tout = self.timeout * cnt
                if procout is not None:
                    procout.timeout = tout
                if procerr is not None:
                    procerr.timeout = tout
            elif cnt == 1:
                pass
            else:
                cnt = 1
                if procout is not None:
                    procout.timeout = self.timeout
                if procerr is not None:
                    procerr.timeout = self.timeout
            # redirect some output!
            i = self._read_write(procout, stdout, sys.__stdout__)
            j = self._read_write(procerr, stderr, sys.__stderr__)
            if self.suspended:
                break
        if self.suspended:
            return
        # close files to send EOF to non-blocking reader.
        # capout & caperr seem to be needed only by Windows, while
        # orig_stdout & orig_stderr are need by posix and Windows.
        # Also, order seems to matter here,
        # with orig_* needed to be closed before cap*
        safe_fdclose(self.orig_stdout)
        safe_fdclose(self.orig_stderr)
        if ON_WINDOWS:
            safe_fdclose(capout)
            safe_fdclose(caperr)
        # read in the remaining data in a blocking fashion.
        while (procout is not None and not procout.is_fully_read()) or \
              (procerr is not None and not procerr.is_fully_read()):
            self._read_write(procout, stdout, sys.__stdout__)
            self._read_write(procerr, stderr, sys.__stderr__)
        # kill the process if it is still alive. Happens when piping.
        if proc.poll() is None:
            proc.terminate()

    def _wait_and_getattr(self, name):
        """make sure the instance has a certain attr, and return it."""
        while not hasattr(self, name):
            time.sleep(1e-7)
        return getattr(self, name)

    def _read_write(self, reader, writer, stdbuf):
        """Reads a chunk of bytes from a buffer and write into memory or back
        down to the standard buffer, as approriate. Returns the number of
        successful reads.
        """
        if reader is None:
            return 0
        i = -1
        for i, chunk in enumerate(iter(reader.read_queue, b'')):
            self._alt_mode_switch(chunk, writer, stdbuf)
        if i >= 0:
            writer.flush()
            stdbuf.flush()
        return i + 1

    def _alt_mode_switch(self, chunk, membuf, stdbuf):
        """Enables recursively switching between normal capturing mode
        and 'alt' mode, which passes through values to the standard
        buffer. Pagers, text editors, curses applications, etc. use
        alternate mode.
        """
        i, flag = findfirst(chunk, ALTERNATE_MODE_FLAGS)
        if flag is None:
            self._alt_mode_writer(chunk, membuf, stdbuf)
        else:
            # This code is executed when the child process switches the
            # terminal into or out of alternate mode. The line below assumes
            # that the user has opened vim, less, or similar, and writes writes
            # to stdin.
            j = i + len(flag)
            # write the first part of the chunk in the current mode.
            self._alt_mode_writer(chunk[:i], membuf, stdbuf)
            # switch modes
            # write the flag itself the current mode where alt mode is on
            # so that it is streamed to the termial ASAP.
            # this is needed for terminal emulators to find the correct
            # positions before and after alt mode.
            alt_mode = (flag in START_ALTERNATE_MODE)
            if alt_mode:
                self.in_alt_mode = alt_mode
                self._alt_mode_writer(flag, membuf, stdbuf)
                self._enable_cbreak_stdin()
            else:
                self._alt_mode_writer(flag, membuf, stdbuf)
                self.in_alt_mode = alt_mode
                self._disable_cbreak_stdin()
            # recurse this function, but without the current flag.
            self._alt_mode_switch(chunk[j:], membuf, stdbuf)

    def _alt_mode_writer(self, chunk, membuf, stdbuf):
        """Write bytes to the standard buffer if in alt mode or otherwise
        to the in-memory buffer.
        """
        if not chunk:
            pass  # don't write empty values
        elif self.in_alt_mode:
            stdbuf.buffer.write(chunk)
        else:
            with self.lock:
                p = membuf.tell()
                membuf.seek(0, io.SEEK_END)
                membuf.write(chunk)
                membuf.seek(p)

    #
    # Window resize handlers
    #

    def _signal_winch(self, signum, frame):
        """Signal handler for SIGWINCH - window size has changed."""
        self.send_signal(signal.SIGWINCH)
        self._set_pty_size()

    def _set_pty_size(self):
        """Sets the window size of the child pty based on the window size of
        our own controlling terminal.
        """
        if ON_WINDOWS or not os.isatty(self.stdout_fd):
            return
        # Get the terminal size of the real terminal, set it on the
        #       pseudoterminal.
        buf = array.array('h', [0, 0, 0, 0])
        # 1 = stdout here
        try:
            fcntl.ioctl(1, termios.TIOCGWINSZ, buf, True)
            fcntl.ioctl(self.stdout_fd, termios.TIOCSWINSZ, buf)
        except OSError:
            pass

    #
    # SIGINT handler
    #

    def _signal_int(self, signum, frame):
        """Signal handler for SIGINT - Ctrl+C may have been pressed."""
        self.send_signal(signum)
        if self.proc is not None and self.proc.poll() is not None:
            self._restore_sigint(frame=frame)
        if on_main_thread():
            signal.pthread_kill(threading.get_ident(), signal.SIGINT)

    def _restore_sigint(self, frame=None):
        old = self.old_int_handler
        if old is not None:
            if on_main_thread():
                signal.signal(signal.SIGINT, old)
            self.old_int_handler = None
        if frame is not None:
            self._disable_cbreak_stdin()
            if old is not None and old is not self._signal_int:
                old(signal.SIGINT, frame)

    #
    # SIGTSTP handler
    #

    def _signal_tstp(self, signum, frame):
        """Signal handler for suspending SIGTSTP - Ctrl+Z may have been pressed.
        """
        self.suspended = True
        self.send_signal(signum)
        self._restore_sigtstp(frame=frame)

    def _restore_sigtstp(self, frame=None):
        old = self.old_tstp_handler
        if old is not None:
            if on_main_thread():
                signal.signal(signal.SIGTSTP, old)
            self.old_tstp_handler = None
        if frame is not None:
            self._disable_cbreak_stdin()

    #
    # SIGQUIT handler
    #

    def _signal_quit(self, signum, frame):
        """Signal handler for quiting SIGQUIT - Ctrl+\ may have been pressed.
        """
        self.send_signal(signum)
        self._restore_sigquit(frame=frame)

    def _restore_sigquit(self, frame=None):
        old = self.old_quit_handler
        if old is not None:
            if on_main_thread():
                signal.signal(signal.SIGQUIT, old)
            self.old_quit_handler = None
        if frame is not None:
            self._disable_cbreak_stdin()

    #
    # cbreak mode handlers
    #

    def _enable_cbreak_stdin(self):
        if not ON_POSIX:
            return
        try:
            self.stdin_mode = termios.tcgetattr(self.stdin_fd)[:]
        except termios.error:
            # this can happen for cases where another process is controlling
            # xonsh's tty device, such as in testing.
            self.stdin_mode = None
            return
        new = self.stdin_mode[:]
        new[LFLAG] &= ~(termios.ECHO | termios.ICANON)
        new[CC][termios.VMIN] = 1
        new[CC][termios.VTIME] = 0
        try:
            # termios.TCSAFLUSH may be less reliable than termios.TCSANOW
            termios.tcsetattr(self.stdin_fd, termios.TCSANOW, new)
        except termios.error:
            self._disable_cbreak_stdin()

    def _disable_cbreak_stdin(self):
        if not ON_POSIX or self.stdin_mode is None:
            return
        new = self.stdin_mode[:]
        new[LFLAG] |= termios.ECHO | termios.ICANON
        new[CC][termios.VMIN] = 1
        new[CC][termios.VTIME] = 0
        try:
            termios.tcsetattr(self.stdin_fd, termios.TCSANOW, new)
        except termios.error:
            pass

    #
    # Dispatch methods
    #

    def poll(self):
        """Dispatches to Popen.returncode."""
        return self.proc.returncode

    def wait(self, timeout=None):
        """Dispatches to Popen.wait(), but also does process cleanup such as
        joining this thread and replacing the original window size signal
        handler.
        """
        self._disable_cbreak_stdin()
        rtn = self.proc.wait(timeout=timeout)
        self.join()
        # need to replace the old signal handlers somewhere...
        if self.old_winch_handler is not None and on_main_thread():
            signal.signal(signal.SIGWINCH, self.old_winch_handler)
            self.old_winch_handler = None
        self._restore_sigint()
        self._restore_sigtstp()
        self._restore_sigquit()
        return rtn

    @property
    def returncode(self):
        """Process return code."""
        return self.proc.returncode

    @returncode.setter
    def returncode(self, value):
        """Process return code."""
        self.proc.returncode = value

    @property
    def signal(self):
        """Process signal, or None."""
        s = getattr(self.proc, "signal", None)
        if s is None:
            rtn = self.returncode
            if rtn is not None and rtn != 0:
                s = (-1*rtn, rtn < 0 if ON_WINDOWS else os.WCOREDUMP(rtn))
        return s

    @signal.setter
    def signal(self, value):
        """Process signal, or None."""
        self.proc.signal = value

    def send_signal(self, signal):
        """Dispatches to Popen.send_signal()."""
        dt = 0.0
        while self.proc is None and dt < self.timeout:
            time.sleep(1e-7)
            dt += 1e-7
        if self.proc is None:
            return
        try:
            rtn = self.proc.send_signal(signal)
        except ProcessLookupError:
            # This can happen in the case of !(cmd) when the command has ended
            rtn = None
        return rtn

    def terminate(self):
        """Dispatches to Popen.terminate()."""
        return self.proc.terminate()

    def kill(self):
        """Dispatches to Popen.kill()."""
        return self.proc.kill()


class Handle(int):
    closed = False

    def Close(self, CloseHandle=None):
        CloseHandle = CloseHandle or _winapi.CloseHandle
        if not self.closed:
            self.closed = True
            CloseHandle(self)

    def Detach(self):
        if not self.closed:
            self.closed = True
            return int(self)
        raise ValueError("already closed")

    def __repr__(self):
        return "Handle(%d)" % int(self)

    __del__ = Close
    __str__ = __repr__


class FileThreadDispatcher:
    """Dispatches to different file handles depending on the
    current thread. Useful if you want file operation to go to differnt
    places for different threads.
    """

    def __init__(self, default=None):
        """
        Parameters
        ----------
        default : file-like or None, optional
            The file handle to write to if a thread cannot be found in
            the registery. If None, a new in-memory instance.

        Attributes
        ----------
        registry : dict
            Maps thread idents to file handles.
        """
        if default is None:
            default = io.TextIOWrapper(io.BytesIO())
        self.default = default
        self.registry = {}

    def register(self, handle):
        """Registers a file handle for the current thread. Returns self so
        that this method can be used in a with-statement.
        """
        self.registry[threading.get_ident()] = handle
        return self

    def deregister(self):
        """Removes the current thread from the registry."""
        del self.registry[threading.get_ident()]

    @property
    def available(self):
        """True if the thread is available in the registry."""
        return threading.get_ident() in self.registry

    @property
    def handle(self):
        """Gets the current handle for the thread."""
        return self.registry.get(threading.get_ident(), self.default)

    def __enter__(self):
        pass

    def __exit__(self, ex_type, ex_value, ex_traceback):
        self.deregister()

    #
    # io.TextIOBase interface
    #

    @property
    def encoding(self):
        """Gets the encoding for this thread's handle."""
        return self.handle.encoding

    @property
    def errors(self):
        """Gets the errors for this thread's handle."""
        return self.handle.errors

    @property
    def newlines(self):
        """Gets the newlines for this thread's handle."""
        return self.handle.newlines

    @property
    def buffer(self):
        """Gets the buffer for this thread's handle."""
        return self.handle.buffer

    def detach(self):
        """Detaches the buffer for the current thread."""
        return self.handle.detach()

    def read(self, size=None):
        """Reads from the handle for the current thread."""
        return self.handle.read(size)

    def readline(self, size=-1):
        """Reads a line from the handle for the current thread."""
        return self.handle.readline(size)

    def readlines(self, hint=-1):
        """Reads lines from the handle for the current thread."""
        return self.handle.readlines(hint)

    def seek(self, offset, whence=io.SEEK_SET):
        """Seeks the current file."""
        return self.handle.seek(offset, whence)

    def tell(self):
        """Reports the current position in the handle for the current thread."""
        return self.handle.tell()

    def write(self, s):
        """Writes to this thread's handle. This also flushes, just to be
        extra sure the string was written.
        """
        h = self.handle
        try:
            r = h.write(s)
            h.flush()
        except OSError:
            r = None
        return r

    @property
    def line_buffering(self):
        """Gets if line buffering for this thread's handle enabled."""
        return self.handle.line_buffering

    #
    # io.IOBase interface
    #

    def close(self):
        """Closes the current thread's handle."""
        return self.handle.close()

    @property
    def closed(self):
        """Is the thread's handle closed."""
        return self.handle.closed

    def fileno(self):
        """Returns the file descriptor for the current thread."""
        return self.handle.fileno()

    def flush(self):
        """Flushes the file descriptor for the current thread."""
        return safe_flush(self.handle)

    def isatty(self):
        """Returns if the file descriptor for the current thread is a tty."""
        return self.handle.isatty()

    def readable(self):
        """Returns if file descriptor for the current thread is readable."""
        return self.handle.readable()

    def seekable(self):
        """Returns if file descriptor for the current thread is seekable."""
        return self.handle.seekable()

    def truncate(self, size=None):
        """Truncates the file for for the current thread."""
        return self.handle.truncate()

    def writable(self, size=None):
        """Returns if file descriptor for the current thread is writable."""
        return self.handle.writable(size)

    def writelines(self):
        """Writes lines for the file descriptor for the current thread."""
        return self.handle.writelines()


# These should NOT be lazy since they *need* to get the true stdout from the
# main thread. Also their creation time should be neglibible.
STDOUT_DISPATCHER = FileThreadDispatcher(default=sys.stdout)
STDERR_DISPATCHER = FileThreadDispatcher(default=sys.stderr)


def parse_proxy_return(r, stdout, stderr):
    """Proxies may return a variety of outputs. This hanles them generally.

    Parameters
    ----------
    r : tuple, str, int, or None
        Return from proxy function
    stdout : file-like
        Current stdout stream
    stdout : file-like
        Current stderr stream

    Returns
    -------
    cmd_result : int
        The return code of the proxy
    """
    cmd_result = 0
    if isinstance(r, str):
        stdout.write(r)
        stdout.flush()
    elif isinstance(r, int):
        cmd_result = r
    elif isinstance(r, cabc.Sequence):
        rlen = len(r)
        if rlen > 0 and r[0] is not None:
            stdout.write(r[0])
            stdout.flush()
        if rlen > 1 and r[1] is not None:
            stderr.write(r[1])
            stderr.flush()
        if rlen > 2 and r[2] is not None:
            cmd_result = r[2]
    elif r is not None:
        # for the random object...
        stdout.write(str(r))
        stdout.flush()
    return cmd_result


def proxy_zero(f, args, stdin, stdout, stderr, spec):
    """Calls a proxy function which takes no parameters."""
    return f()


def proxy_one(f, args, stdin, stdout, stderr, spec):
    """Calls a proxy function which takes one parameter: args"""
    return f(args)


def proxy_two(f, args, stdin, stdout, stderr, spec):
    """Calls a proxy function which takes two parameter: args and stdin."""
    return f(args, stdin)


def proxy_three(f, args, stdin, stdout, stderr, spec):
    """Calls a proxy function which takes three parameter: args, stdin, stdout.
    """
    return f(args, stdin, stdout)


def proxy_four(f, args, stdin, stdout, stderr, spec):
    """Calls a proxy function which takes four parameter: args, stdin, stdout,
    and stderr.
    """
    return f(args, stdin, stdout, stderr)


PROXIES = (proxy_zero, proxy_one, proxy_two, proxy_three, proxy_four)


def partial_proxy(f):
    """Dispatches the approriate proxy function based on the number of args."""
    numargs = len(inspect.signature(f).parameters)
    if numargs < 5:
        return functools.partial(PROXIES[numargs], f)
    elif numargs == 5:
        # don't need to partial.
        return f
    else:
        e = 'Expected proxy with 5 or fewer arguments, not {}'
        raise XonshError(e.format(numargs))


class ProcProxyThread(threading.Thread):
    """
    Class representing a function to be run as a subprocess-mode command.
    """

    def __init__(self, f, args, stdin=None, stdout=None, stderr=None,
                 universal_newlines=False, env=None):
        """Parameters
        ----------
        f : function
            The function to be executed.
        args : list
            A (possibly empty) list containing the arguments that were given on
            the command line
        stdin : file-like, optional
            A file-like object representing stdin (input can be read from
            here).  If `stdin` is not provided or if it is explicitly set to
            `None`, then an instance of `io.StringIO` representing an empty
            file is used.
        stdout : file-like, optional
            A file-like object representing stdout (normal output can be
            written here).  If `stdout` is not provided or if it is explicitly
            set to `None`, then `sys.stdout` is used.
        stderr : file-like, optional
            A file-like object representing stderr (error output can be
            written here).  If `stderr` is not provided or if it is explicitly
            set to `None`, then `sys.stderr` is used.
        universal_newlines : bool, optional
            Whether or not to use universal newlines.
        env : Mapping, optiona            Environment mapping.
        """
        self.orig_f = f
        self.f = partial_proxy(f)
        self.args = args
        self.pid = None
        self.returncode = None
        self._closed_handle_cache = {}

        handles = self._get_handles(stdin, stdout, stderr)
        (self.p2cread, self.p2cwrite,
         self.c2pread, self.c2pwrite,
         self.errread, self.errwrite) = handles

        # default values
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.env = env or builtins.__xonsh_env__
        self._interrupted = False

        if ON_WINDOWS:
            if self.p2cwrite != -1:
                self.p2cwrite = msvcrt.open_osfhandle(self.p2cwrite.Detach(), 0)
            if self.c2pread != -1:
                self.c2pread = msvcrt.open_osfhandle(self.c2pread.Detach(), 0)
            if self.errread != -1:
                self.errread = msvcrt.open_osfhandle(self.errread.Detach(), 0)

        if self.p2cwrite != -1:
            self.stdin = io.open(self.p2cwrite, 'wb', -1)
            if universal_newlines:
                self.stdin = io.TextIOWrapper(self.stdin, write_through=True,
                                              line_buffering=False)
        elif isinstance(stdin, int) and stdin != 0:
            self.stdin = io.open(stdin, 'wb', -1)

        if self.c2pread != -1:
            self.stdout = io.open(self.c2pread, 'rb', -1)
            if universal_newlines:
                self.stdout = io.TextIOWrapper(self.stdout)

        if self.errread != -1:
            self.stderr = io.open(self.errread, 'rb', -1)
            if universal_newlines:
                self.stderr = io.TextIOWrapper(self.stderr)

        # Set some signal handles, if we can. Must come before process
        # is started to prevent deadlock on windows
        self.old_int_handler = None
        if on_main_thread():
            self.old_int_handler = signal.signal(signal.SIGINT,
                                                 self._signal_int)
        # start up the proc
        super().__init__()
        self.start()

    def __del__(self):
        self._restore_sigint()

    def run(self):
        """Set up input/output streams and execute the child function in a new
        thread.  This is part of the `threading.Thread` interface and should
        not be called directly.
        """
        if self.f is None:
            return
        spec = self._wait_and_getattr('spec')
        last_in_pipeline = spec.last_in_pipeline
        if last_in_pipeline:
            capout = spec.captured_stdout  # NOQA
            caperr = spec.captured_stderr  # NOQA
        env = builtins.__xonsh_env__
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')
        if ON_WINDOWS:
            if self.p2cread != -1:
                self.p2cread = msvcrt.open_osfhandle(self.p2cread.Detach(), 0)
            if self.c2pwrite != -1:
                self.c2pwrite = msvcrt.open_osfhandle(self.c2pwrite.Detach(), 0)
            if self.errwrite != -1:
                self.errwrite = msvcrt.open_osfhandle(self.errwrite.Detach(), 0)
        # get stdin
        if self.stdin is None:
            sp_stdin = None
        elif self.p2cread != -1:
            sp_stdin = io.TextIOWrapper(io.open(self.p2cread, 'rb', -1),
                                        encoding=enc, errors=err)
        else:
            sp_stdin = sys.stdin
        # stdout
        if self.c2pwrite != -1:
            sp_stdout = io.TextIOWrapper(io.open(self.c2pwrite, 'wb', -1),
                                         encoding=enc, errors=err)
        else:
            sp_stdout = sys.stdout
        # stderr
        if self.errwrite == self.c2pwrite:
            sp_stderr = sp_stdout
        elif self.errwrite != -1:
            sp_stderr = io.TextIOWrapper(io.open(self.errwrite, 'wb', -1),
                                         encoding=enc, errors=err)
        else:
            sp_stderr = sys.stderr
        # run the function itself
        try:
            with STDOUT_DISPATCHER.register(sp_stdout), \
                 STDERR_DISPATCHER.register(sp_stderr), \
                 redirect_stdout(STDOUT_DISPATCHER), \
                 redirect_stderr(STDERR_DISPATCHER):
                r = self.f(self.args, sp_stdin, sp_stdout, sp_stderr, spec)
        except SystemExit as e:
            r = e.code if isinstance(e.code, int) else int(bool(e.code))
        except OSError as e:
            status = still_writable(self.c2pwrite) and \
                     still_writable(self.errwrite)
            if status:
                # stdout and stderr are still writable, so error must
                # come from function itself.
                print_exception()
                r = 1
            else:
                # stdout and stderr are no longer writable, so error must
                # come from the fact that the next process in the pipeline
                # has closed the other side of the pipe. The function then
                # attempted to write to this side of the pipe anyway. This
                # is not truly an error and we should exit gracefully.
                r = 0
        except Exception:
            print_exception()
            r = 1
        safe_flush(sp_stdout)
        safe_flush(sp_stderr)
        self.returncode = parse_proxy_return(r, sp_stdout, sp_stderr)
        if not last_in_pipeline and not ON_WINDOWS:
            # mac requires us *not to* close the handles here while
            # windows requires us *to* close the handles here
            return
        # clean up
        # scopz: not sure why this is needed, but stdin cannot go here
        # and stdout & stderr must.
        handles = [self.stdout, self.stderr]
        for handle in handles:
            safe_fdclose(handle, cache=self._closed_handle_cache)

    def _wait_and_getattr(self, name):
        """make sure the instance has a certain attr, and return it."""
        while not hasattr(self, name):
            time.sleep(1e-7)
        return getattr(self, name)

    def poll(self):
        """Check if the function has completed.

        Returns
        -------
        None if the function is still executing, and the returncode otherwise
        """
        return self.returncode

    def wait(self, timeout=None):
        """Waits for the process to finish and returns the return code."""
        self.join()
        self._restore_sigint()
        return self.returncode

    #
    # SIGINT handler
    #

    def _signal_int(self, signum, frame):
        """Signal handler for SIGINT - Ctrl+C may have been pressed."""
        # check if we have already be interrupted to prevent infintie recurrsion
        if self._interrupted:
            return
        self._interrupted = True
        # close file handles here to stop an processes piped to us.
        handles = (self.p2cread, self.p2cwrite, self.c2pread, self.c2pwrite,
                   self.errread, self.errwrite)
        for handle in handles:
            safe_fdclose(handle)
        if self.poll() is not None:
            self._restore_sigint(frame=frame)
        if on_main_thread():
            signal.pthread_kill(threading.get_ident(), signal.SIGINT)

    def _restore_sigint(self, frame=None):
        old = self.old_int_handler
        if old is not None:
            if on_main_thread():
                signal.signal(signal.SIGINT, old)
            self.old_int_handler = None
        if frame is not None:
            if old is not None and old is not self._signal_int:
                old(signal.SIGINT, frame)
        if self._interrupted:
            self.returncode = 1

    # The code below (_get_devnull, _get_handles, and _make_inheritable) comes
    # from subprocess.py in the Python 3.4.2 Standard Library
    def _get_devnull(self):
        if not hasattr(self, '_devnull'):
            self._devnull = os.open(os.devnull, os.O_RDWR)
        return self._devnull

    if ON_WINDOWS:
        def _make_inheritable(self, handle):
            """Return a duplicate of handle, which is inheritable"""
            h = _winapi.DuplicateHandle(
                _winapi.GetCurrentProcess(), handle,
                _winapi.GetCurrentProcess(), 0, 1,
                _winapi.DUPLICATE_SAME_ACCESS)
            return Handle(h)

        def _get_handles(self, stdin, stdout, stderr):
            """Construct and return tuple with IO objects:
            p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
            """
            if stdin is None and stdout is None and stderr is None:
                return (-1, -1, -1, -1, -1, -1)

            p2cread, p2cwrite = -1, -1
            c2pread, c2pwrite = -1, -1
            errread, errwrite = -1, -1

            if stdin is None:
                p2cread = _winapi.GetStdHandle(_winapi.STD_INPUT_HANDLE)
                if p2cread is None:
                    p2cread, _ = _winapi.CreatePipe(None, 0)
                    p2cread = Handle(p2cread)
                    _winapi.CloseHandle(_)
            elif stdin == subprocess.PIPE:
                p2cread, p2cwrite = Handle(p2cread), Handle(p2cwrite)
            elif stdin == subprocess.DEVNULL:
                p2cread = msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stdin, int):
                p2cread = msvcrt.get_osfhandle(stdin)
            else:
                # Assuming file-like object
                p2cread = msvcrt.get_osfhandle(stdin.fileno())
            p2cread = self._make_inheritable(p2cread)

            if stdout is None:
                c2pwrite = _winapi.GetStdHandle(_winapi.STD_OUTPUT_HANDLE)
                if c2pwrite is None:
                    _, c2pwrite = _winapi.CreatePipe(None, 0)
                    c2pwrite = Handle(c2pwrite)
                    _winapi.CloseHandle(_)
            elif stdout == subprocess.PIPE:
                c2pread, c2pwrite = _winapi.CreatePipe(None, 0)
                c2pread, c2pwrite = Handle(c2pread), Handle(c2pwrite)
            elif stdout == subprocess.DEVNULL:
                c2pwrite = msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stdout, int):
                c2pwrite = msvcrt.get_osfhandle(stdout)
            else:
                # Assuming file-like object
                c2pwrite = msvcrt.get_osfhandle(stdout.fileno())
            c2pwrite = self._make_inheritable(c2pwrite)

            if stderr is None:
                errwrite = _winapi.GetStdHandle(_winapi.STD_ERROR_HANDLE)
                if errwrite is None:
                    _, errwrite = _winapi.CreatePipe(None, 0)
                    errwrite = Handle(errwrite)
                    _winapi.CloseHandle(_)
            elif stderr == subprocess.PIPE:
                errread, errwrite = _winapi.CreatePipe(None, 0)
                errread, errwrite = Handle(errread), Handle(errwrite)
            elif stderr == subprocess.STDOUT:
                errwrite = c2pwrite
            elif stderr == subprocess.DEVNULL:
                errwrite = msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stderr, int):
                errwrite = msvcrt.get_osfhandle(stderr)
            else:
                # Assuming file-like object
                errwrite = msvcrt.get_osfhandle(stderr.fileno())
            errwrite = self._make_inheritable(errwrite)

            return (p2cread, p2cwrite,
                    c2pread, c2pwrite,
                    errread, errwrite)

    else:
        # POSIX versions
        def _get_handles(self, stdin, stdout, stderr):
            """Construct and return tuple with IO objects:
            p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
            """
            p2cread, p2cwrite = -1, -1
            c2pread, c2pwrite = -1, -1
            errread, errwrite = -1, -1

            if stdin is None:
                pass
            elif stdin == subprocess.PIPE:
                p2cread, p2cwrite = os.pipe()
            elif stdin == subprocess.DEVNULL:
                p2cread = self._get_devnull()
            elif isinstance(stdin, int):
                p2cread = stdin
            else:
                # Assuming file-like object
                p2cread = stdin.fileno()

            if stdout is None:
                pass
            elif stdout == subprocess.PIPE:
                c2pread, c2pwrite = os.pipe()
            elif stdout == subprocess.DEVNULL:
                c2pwrite = self._get_devnull()
            elif isinstance(stdout, int):
                c2pwrite = stdout
            else:
                # Assuming file-like object
                c2pwrite = stdout.fileno()

            if stderr is None:
                pass
            elif stderr == subprocess.PIPE:
                errread, errwrite = os.pipe()
            elif stderr == subprocess.STDOUT:
                errwrite = c2pwrite
            elif stderr == subprocess.DEVNULL:
                errwrite = self._get_devnull()
            elif isinstance(stderr, int):
                errwrite = stderr
            else:
                # Assuming file-like object
                errwrite = stderr.fileno()

            return (p2cread, p2cwrite,
                    c2pread, c2pwrite,
                    errread, errwrite)


#
# Foreground Thread Process Proxies
#

class ProcProxy(object):
    """This is process proxy class that runs its alias functions on the
    same thread that it was called from, which is typically the main thread.
    This prevents the process from running on a background thread, but enables
    debugger and profiler tools (functions) be run on the same thread that they
    are attempting to debug.
    """

    def __init__(self, f, args, stdin=None, stdout=None, stderr=None,
                 universal_newlines=False, env=None):
        self.orig_f = f
        self.f = partial_proxy(f)
        self.args = args
        self.pid = os.getpid()
        self.returncode = None
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.universal_newlines = universal_newlines
        self.env = env

    def poll(self):
        """Check if the function has completed via the returncode or None.
        """
        return self.returncode

    def wait(self, timeout=None):
        """Runs the function and returns the result. Timeout argument only
        present for API compatability.
        """
        if self.f is None:
            return 0
        env = builtins.__xonsh_env__
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')
        spec = self._wait_and_getattr('spec')
        # set file handles
        if self.stdin is None:
            stdin = None
        else:
            if isinstance(self.stdin, int):
                inbuf = io.open(self.stdin, 'rb', -1)
            else:
                inbuf = self.stdin
            stdin = io.TextIOWrapper(inbuf, encoding=enc, errors=err)
        stdout = self._pick_buf(self.stdout, sys.stdout, enc, err)
        stderr = self._pick_buf(self.stderr, sys.stderr, enc, err)
        # run the actual function
        try:
            r = self.f(self.args, stdin, stdout, stderr, spec)
        except Exception:
            print_exception()
            r = 1
        self.returncode = parse_proxy_return(r, stdout, stderr)
        safe_flush(stdout)
        safe_flush(stderr)
        return self.returncode

    @staticmethod
    def _pick_buf(handle, sysbuf, enc, err):
        if handle is None or handle is sysbuf:
            buf = sysbuf
        elif isinstance(handle, int):
            if handle < 3:
                buf = sysbuf
            else:
                buf = io.TextIOWrapper(io.open(handle, 'wb', -1),
                                       encoding=enc, errors=err)
        elif hasattr(handle, 'encoding'):
            # must be a text stream, no need to wrap.
            buf = handle
        else:
            # must be a binary stream, should wrap it.
            buf = io.TextIOWrapper(handle, encoding=enc, errors=err)
        return buf

    def _wait_and_getattr(self, name):
        """make sure the instance has a certain attr, and return it."""
        while not hasattr(self, name):
            time.sleep(1e-7)
        return getattr(self, name)


@lazyobject
def SIGNAL_MESSAGES():
    sm = {
        signal.SIGABRT: 'Aborted',
        signal.SIGFPE: 'Floating point exception',
        signal.SIGILL: 'Illegal instructions',
        signal.SIGTERM: 'Terminated',
        signal.SIGSEGV: 'Segmentation fault',
        }
    if ON_POSIX:
        sm.update({
            signal.SIGQUIT: 'Quit',
            signal.SIGHUP: 'Hangup',
            signal.SIGKILL: 'Killed',
            })
    return sm


def safe_readlines(handle, hint=-1):
    """Attempts to read lines without throwing an error."""
    try:
        lines = handle.readlines(hint)
    except OSError:
        lines = []
    return lines


def safe_readable(handle):
    """Attempts to find if the handle is readable without throwing an error."""
    try:
        status = handle.readable()
    except (OSError, ValueError):
        status = False
    return status


def update_fg_process_group(pipeline_group, background):
    if background:
        return False
    if not ON_POSIX:
        return False
    env = builtins.__xonsh_env__
    if not env.get('XONSH_INTERACTIVE'):
        return False
    return give_terminal_to(pipeline_group)


class CommandPipeline:
    """Represents a subprocess-mode command pipeline."""

    attrnames = ("stdin", "stdout", "stderr", "pid", "returncode", "args",
                 "alias", "stdin_redirect", "stdout_redirect",
                 "stderr_redirect", "timestamps", "executed_cmd", 'input',
                 'output', 'errors')

    nonblocking = (io.BytesIO, NonBlockingFDReader, ConsoleParallelReader)

    def __init__(self, specs):
        """
        Parameters
        ----------
        specs : list of SubprocSpec
            Process sepcifications

        Attributes
        ----------
        spec : SubprocSpec
            The last specification in specs
        proc : Popen-like
            The process in procs
        ended : bool
            Boolean for if the command has stopped executing.
        input : str
            A string of the standard input.
        output : str
            A string of the standard output.
        errors : str
            A string of the standard error.
        lines : list of str
            The output lines
        starttime : floats or None
            Pipeline start timestamp.
        """
        self.starttime = None
        self.ended = False
        self.procs = []
        self.specs = specs
        self.spec = specs[-1]
        self.captured = specs[-1].captured
        self.input = self._output = self.errors = self.endtime = None
        self._closed_handle_cache = {}
        self.lines = []
        self._stderr_prefix = self._stderr_postfix = None
        self.term_pgid = None

        background = self.spec.background
        pipeline_group = None
        for spec in specs:
            if self.starttime is None:
                self.starttime = time.time()
            try:
                proc = spec.run(pipeline_group=pipeline_group)
            except XonshError:
                self._return_terminal()
                raise
            if proc.pid and pipeline_group is None and not spec.is_proxy and \
                    self.captured != 'object':
                pipeline_group = proc.pid
                if update_fg_process_group(pipeline_group, background):
                    self.term_pgid = pipeline_group
            self.procs.append(proc)
        self.proc = self.procs[-1]

    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += ', '.join(a + '=' + str(getattr(self, a)) for a in self.attrnames)
        s += ')'
        return s

    def __bool__(self):
        return self.returncode == 0

    def __len__(self):
        return len(self.procs)

    def __iter__(self):
        """Iterates through stdout and returns the lines, converting to
        strings and universal newlines if needed.
        """
        if self.ended:
            yield from iter(self.lines)
        else:
            yield from self.tee_stdout()

    def iterraw(self):
        """Iterates through the last stdout, and returns the lines
        exactly as found.
        """
        # get approriate handles
        spec = self.spec
        proc = self.proc
        timeout = builtins.__xonsh_env__.get('XONSH_PROC_FREQUENCY')
        # get the correct stdout
        stdout = proc.stdout
        if ((stdout is None or spec.stdout is None or not safe_readable(stdout))
                and spec.captured_stdout is not None):
            stdout = spec.captured_stdout
        if hasattr(stdout, 'buffer'):
            stdout = stdout.buffer
        if stdout is not None and not isinstance(stdout, self.nonblocking):
            stdout = NonBlockingFDReader(stdout.fileno(), timeout=timeout)
        if not stdout or self.captured == 'stdout' or not safe_readable(stdout) or \
                not spec.threadable:
            # we get here if the process is not threadable or the
            # class is the real Popen
            PrevProcCloser(pipeline=self)
            task = wait_for_active_job()
            if task is None or task['status'] != 'stopped':
                proc.wait()
                self._endtime()
                if self.captured == 'object':
                    self.end(tee_output=False)
                elif self.captured == 'hiddenobject' and stdout:
                    b = stdout.read()
                    lines = b.splitlines(keepends=True)
                    yield from lines
                    self.end(tee_output=False)
                elif self.captured == 'stdout':
                    b = stdout.read()
                    s = self._decode_uninew(b, universal_newlines=True)
                    self.lines = s.splitlines(keepends=True)
            raise StopIteration
        # get the correct stderr
        stderr = proc.stderr
        if ((stderr is None or spec.stderr is None or not safe_readable(stderr))
                and spec.captured_stderr is not None):
            stderr = spec.captured_stderr
        if hasattr(stderr, 'buffer'):
            stderr = stderr.buffer
        if stderr is not None and not isinstance(stderr, self.nonblocking):
            stderr = NonBlockingFDReader(stderr.fileno(), timeout=timeout)
        # read from process while it is running
        check_prev_done = len(self.procs) == 1
        prev_end_time = None
        i = j = cnt = 1
        while proc.poll() is None:
            if getattr(proc, 'suspended', False):
                return
            elif getattr(proc, 'in_alt_mode', False):
                time.sleep(0.1)  # probably not leaving any time soon
                continue
            elif not check_prev_done:
                # In the case of pipelines with more than one command
                # we should give the commands a little time
                # to start up fully. This is particularly true for
                # GNU Parallel, which has a long startup time.
                pass
            elif self._prev_procs_done():
                self._close_prev_procs()
                proc.prevs_are_closed = True
                break
            stdout_lines = safe_readlines(stdout, 1024)
            i = len(stdout_lines)
            if i != 0:
                yield from stdout_lines
            stderr_lines = safe_readlines(stderr, 1024)
            j = len(stderr_lines)
            if j != 0:
                self.stream_stderr(stderr_lines)
            if not check_prev_done:
                # if we are piping...
                if (stdout_lines or stderr_lines):
                    # see if we have some output.
                    check_prev_done = True
                elif prev_end_time is None:
                    # or see if we already know that the next-to-last
                    # proc in the pipeline has ended.
                    if self._prev_procs_done():
                        # if it has, record the time
                        prev_end_time = time.time()
                elif time.time() - prev_end_time >= 0.1:
                    # if we still don't have any output, even though the
                    # next-to-last proc has finished, wait a bit to make
                    # sure we have fully started up, etc.
                    check_prev_done = True
            # this is for CPU usage
            if i + j == 0:
                cnt = min(cnt + 1, 1000)
            else:
                cnt = 1
            time.sleep(timeout * cnt)
        # read from process now that it is over
        yield from safe_readlines(stdout)
        self.stream_stderr(safe_readlines(stderr))
        proc.wait()
        self._endtime()
        yield from safe_readlines(stdout)
        self.stream_stderr(safe_readlines(stderr))
        if self.captured == 'object':
            self.end(tee_output=False)

    def itercheck(self):
        """Iterates through the command lines and throws an error if the
        returncode is non-zero.
        """
        yield from self
        if self.returncode:
            # I included self, as providing access to stderr and other details
            # useful when instance isn't assigned to a variable in the shell.
            raise XonshCalledProcessError(self.returncode, self.executed_cmd,
                                          self.stdout, self.stderr, self)

    def tee_stdout(self):
        """Writes the process stdout to the output variable, line-by-line, and
        yields each line. This may optionally accept lines (in bytes) to iterate
        over, in which case it does not call iterraw().
        """
        env = builtins.__xonsh_env__
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')
        lines = self.lines
        stream = self.captured not in STDOUT_CAPTURE_KINDS
        if stream and not self.spec.stdout:
            stream = False
        stdout_has_buffer = hasattr(sys.stdout, 'buffer')
        nl = b'\n'
        cr = b'\r'
        crnl = b'\r\n'
        for line in self.iterraw():
            # write to stdout line ASAP, if needed
            if stream:
                if stdout_has_buffer:
                    sys.stdout.buffer.write(line)
                else:
                    sys.stdout.write(line.decode(encoding=enc, errors=err))
                sys.stdout.flush()
            # do some munging of the line before we return it
            if line.endswith(crnl):
                line = line[:-2] + nl
            elif line.endswith(cr):
                line = line[:-1] + nl
            line = RE_HIDE_ESCAPE.sub(b'', line)
            line = line.decode(encoding=enc, errors=err)
            # tee it up!
            lines.append(line)
            yield line

    def stream_stderr(self, lines):
        """Streams lines to sys.stderr and the errors attribute."""
        if not lines:
            return
        env = builtins.__xonsh_env__
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')
        b = b''.join(lines)
        if self.stderr_prefix:
            b = self.stderr_prefix + b
        if self.stderr_postfix:
            b += self.stderr_postfix
        stderr_has_buffer = hasattr(sys.stderr, 'buffer')
        # write bytes to std stream
        if stderr_has_buffer:
            sys.stderr.buffer.write(b)
        else:
            sys.stderr.write(b.decode(encoding=enc, errors=err))
        sys.stderr.flush()
        # do some munging of the line before we save it to the attr
        b = b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        b = RE_HIDE_ESCAPE.sub(b'', b)
        env = builtins.__xonsh_env__
        s = b.decode(encoding=env.get('XONSH_ENCODING'),
                     errors=env.get('XONSH_ENCODING_ERRORS'))
        # set the errors
        if self.errors is None:
            self.errors = s
        else:
            self.errors += s

    def _decode_uninew(self, b, universal_newlines=None):
        """Decode bytes into a str and apply universal newlines as needed."""
        if not b:
            return ''
        if isinstance(b, bytes):
            env = builtins.__xonsh_env__
            s = b.decode(encoding=env.get('XONSH_ENCODING'),
                         errors=env.get('XONSH_ENCODING_ERRORS'))
        else:
            s = b
        if universal_newlines or self.spec.universal_newlines:
            s = s.replace('\r\n', '\n').replace('\r', '\n')
        return s

    #
    # Ending methods
    #

    def end(self, tee_output=True):
        """
        End the pipeline, return the controlling terminal if needed.

        Main things done in self._end().
        """
        if self.ended:
            return
        self._end(tee_output=tee_output)
        self._return_terminal()

    def _end(self, tee_output):
        """Waits for the command to complete and then runs any closing and
        cleanup procedures that need to be run.
        """
        if tee_output:
            for _ in self.tee_stdout():
                pass
        self._endtime()
        # since we are driven by getting output, input may not be available
        # until the command has completed.
        self._set_input()
        self._close_prev_procs()
        self._close_proc()
        self._check_signal()
        self._apply_to_history()
        self.ended = True
        self._raise_subproc_error()

    def _return_terminal(self):
        if ON_WINDOWS or not ON_POSIX:
            return
        pgid = os.getpgid(0)
        if self.term_pgid is None or pgid == self.term_pgid:
            return
        if give_terminal_to(pgid):  # if gave term succeed
            self.term_pgid = pgid
            if hasattr(builtins, '__xonsh_shell__'):
                # restoring sanity could probably be called whenever we return
                # control to the shell. But it only seems to matter after a
                # ^Z event. This *has* to be called after we give the terminal
                # back to the shell.
                builtins.__xonsh_shell__.shell.restore_tty_sanity()

    def resume(self, job, tee_output=True):
        self.ended = False
        if give_terminal_to(job['pgrp']):
            self.term_pgid = job['pgrp']
        _continue(job)
        self.end(tee_output=tee_output)

    def _endtime(self):
        """Sets the closing timestamp if it hasn't been already."""
        if self.endtime is None:
            self.endtime = time.time()

    def _safe_close(self, handle):
        safe_fdclose(handle, cache=self._closed_handle_cache)

    def _prev_procs_done(self):
        """Boolean for if all previous processes have completed. If there
        is only a single process in the pipeline, this returns False.
        """
        for s, p in zip(self.specs[:-1], self.procs[:-1]):
            self._safe_close(p.stdin)
            self._safe_close(s.stdin)
            if p.poll() is None:
                return False
            self._safe_close(p.stdout)
            self._safe_close(s.stdout)
            self._safe_close(p.stderr)
            self._safe_close(s.stderr)
        return len(self) > 1

    def _close_prev_procs(self):
        """Closes all but the last proc's stdout."""
        for s, p in zip(self.specs[:-1], self.procs[:-1]):
            self._safe_close(s.stdin)
            self._safe_close(p.stdin)
            self._safe_close(s.stdout)
            self._safe_close(p.stdout)
            self._safe_close(s.stderr)
            self._safe_close(p.stderr)

    def _close_proc(self):
        """Closes last proc's stdout."""
        s = self.spec
        p = self.proc
        self._safe_close(s.stdin)
        self._safe_close(p.stdin)
        self._safe_close(s.stdout)
        self._safe_close(p.stdout)
        self._safe_close(s.stderr)
        self._safe_close(p.stderr)
        self._safe_close(s.captured_stdout)
        self._safe_close(s.captured_stderr)

    def _set_input(self):
        """Sets the input vaiable."""
        stdin = self.proc.stdin
        if stdin is None or isinstance(stdin, int) or stdin.closed or \
           not stdin.seekable() or not safe_readable(stdin):
            input = b''
        else:
            stdin.seek(0)
            input = stdin.read()
        self.input = self._decode_uninew(input)

    def _check_signal(self):
        """Checks if a signal was recieved and issues a message."""
        proc_signal = getattr(self.proc, 'signal', None)
        if proc_signal is None:
            return
        sig, core = proc_signal
        sig_str = SIGNAL_MESSAGES.get(sig)
        if sig_str:
            if core:
                sig_str += ' (core dumped)'
            print(sig_str, file=sys.stderr)
            if self.errors is not None:
                self.errors += sig_str + '\n'

    def _apply_to_history(self):
        """Applies the results to the current history object."""
        hist = builtins.__xonsh_history__
        if hist is not None:
            hist.last_cmd_rtn = self.proc.returncode

    def _raise_subproc_error(self):
        """Raises a subprocess error, if we are suppossed to."""
        spec = self.spec
        rtn = self.returncode
        if (not spec.is_proxy and
                rtn is not None and
                rtn > 0 and
                builtins.__xonsh_env__.get('RAISE_SUBPROC_ERROR')):
            raise subprocess.CalledProcessError(rtn, spec.cmd,
                                                output=self.output)

    #
    # Properties
    #

    @property
    def stdin(self):
        """Process stdin."""
        return self.proc.stdin

    @property
    def stdout(self):
        """Process stdout."""
        return self.proc.stdout

    @property
    def stderr(self):
        """Process stderr."""
        return self.proc.stderr

    @property
    def inp(self):
        """Creates normalized input string from args."""
        return ' '.join(self.args)

    @property
    def output(self):
        if self._output is None:
            self._output = ''.join(self.lines)
        return self._output

    @property
    def out(self):
        """Output value as a str."""
        self.end()
        return self.output

    @property
    def err(self):
        """Error messages as a string."""
        self.end()
        return self.errors

    @property
    def pid(self):
        """Process identifier."""
        return self.proc.pid

    @property
    def returncode(self):
        """Process return code, waits until command is completed."""
        self.end()
        return self.proc.returncode

    rtn = returncode

    @property
    def args(self):
        """Arguments to the process."""
        return self.spec.args

    @property
    def rtn(self):
        """Alias to return code."""
        return self.returncode

    @property
    def alias(self):
        """Alias the process used."""
        return self.spec.alias

    @property
    def stdin_redirect(self):
        """Redirection used for stdin."""
        stdin = self.spec.stdin
        name = getattr(stdin, 'name', '<stdin>')
        mode = getattr(stdin, 'mode', 'r')
        return [name, mode]

    @property
    def stdout_redirect(self):
        """Redirection used for stdout."""
        stdout = self.spec.stdout
        name = getattr(stdout, 'name', '<stdout>')
        mode = getattr(stdout, 'mode', 'a')
        return [name, mode]

    @property
    def stderr_redirect(self):
        """Redirection used for stderr."""
        stderr = self.spec.stderr
        name = getattr(stderr, 'name', '<stderr>')
        mode = getattr(stderr, 'mode', 'r')
        return [name, mode]

    @property
    def timestamps(self):
        """The start and end time stamps."""
        return [self.starttime, self.endtime]

    @property
    def executed_cmd(self):
        """The resolve and executed command."""
        return self.spec.cmd

    @property
    def stderr_prefix(self):
        """Prefix to print in front of stderr, as bytes."""
        p = self._stderr_prefix
        if p is None:
            env = builtins.__xonsh_env__
            t = env.get('XONSH_STDERR_PREFIX')
            s = format_std_prepost(t, env=env)
            p = s.encode(encoding=env.get('XONSH_ENCODING'),
                         errors=env.get('XONSH_ENCODING_ERRORS'))
            self._stderr_prefix = p
        return p

    @property
    def stderr_postfix(self):
        """Postfix to print after stderr, as bytes."""
        p = self._stderr_postfix
        if p is None:
            env = builtins.__xonsh_env__
            t = env.get('XONSH_STDERR_POSTFIX')
            s = format_std_prepost(t, env=env)
            p = s.encode(encoding=env.get('XONSH_ENCODING'),
                         errors=env.get('XONSH_ENCODING_ERRORS'))
            self._stderr_postfix = p
        return p


class HiddenCommandPipeline(CommandPipeline):
    def __repr__(self):
        return ''


def pause_call_resume(p, f, *args, **kwargs):
    """For a process p, this will call a function f with the remaining args and
    and kwargs. If the process cannot accept signals, the function will be called.

    Parameters
    ----------
    p : Popen object or similar
    f : callable
    args : remaining arguments
    kwargs : keyword arguments
    """
    can_send_signal = hasattr(p, 'send_signal') and ON_POSIX
    if can_send_signal:
        p.send_signal(signal.SIGSTOP)
    try:
        f(*args, **kwargs)
    except Exception:
        pass
    if can_send_signal:
        p.send_signal(signal.SIGCONT)


class PrevProcCloser(threading.Thread):
    """Previous process closer thread for pipelines whose last command
    is itself unthreadable. This makes sure that the pipeline is
    driven foreward and does not deadlock.
    """

    def __init__(self, pipeline):
        """
        Parameters
        ----------
        pipeline : CommandPipeline
            The pipeline whose prev procs we should close.
        """
        self.pipeline = pipeline
        super().__init__()
        self.daemon = True
        self.start()

    def run(self):
        """Runs the closing algorithim."""
        pipeline = self.pipeline
        check_prev_done = len(pipeline.procs) == 1
        if check_prev_done:
            return
        proc = pipeline.proc
        prev_end_time = None
        timeout = builtins.__xonsh_env__.get('XONSH_PROC_FREQUENCY')
        sleeptime = min(timeout * 1000, 0.1)
        while proc.poll() is None:
            if not check_prev_done:
                # In the case of pipelines with more than one command
                # we should give the commands a little time
                # to start up fully. This is particularly true for
                # GNU Parallel, which has a long startup time.
                pass
            elif pipeline._prev_procs_done():
                pipeline._close_prev_procs()
                proc.prevs_are_closed = True
                break
            if not check_prev_done:
                # if we are piping...
                if prev_end_time is None:
                    # or see if we already know that the next-to-last
                    # proc in the pipeline has ended.
                    if pipeline._prev_procs_done():
                        # if it has, record the time
                        prev_end_time = time.time()
                elif time.time() - prev_end_time >= 0.1:
                    # if we still don't have any output, even though the
                    # next-to-last proc has finished, wait a bit to make
                    # sure we have fully started up, etc.
                    check_prev_done = True
            # this is for CPU usage
            time.sleep(sleeptime)
