"""File handle readers and related tools."""

import ctypes
import io
import os
import queue
import sys
import threading
import time

import xonsh.lib.lazyimps as xli
from xonsh.built_ins import XSH


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
        return (
            self.closed
            and (self.thread is None or not self.thread.is_alive())
            and self.queue.empty()
        )

    def read_queue(self):
        """Reads a single chunk from the queue. This is blocking if
        the timeout is None and non-blocking otherwise.
        """
        try:
            return self.queue.get(block=True, timeout=self.timeout)
        except queue.Empty:
            return b""

    def read(self, size=-1):
        """Reads bytes from the file."""
        buf = bytearray()
        while size < 0 or len(buf) != size:
            line = self.read_queue()
            if line:
                buf += line
            else:
                break
        return buf

    def readline(self, size=-1):
        """Reads a line, or a partial line from the file descriptor."""
        nl = b"\n"
        buf = bytearray()
        while size < 0 or len(buf) != size:
            line = self.read_queue()
            if line:
                buf += line
                if line.endswith(nl):
                    break
            else:
                break
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
        self.thread = threading.Thread(
            target=populate_fd_queue, args=(self, self.fd, self.queue)
        )
        self.thread.daemon = True
        self.thread.start()


def populate_buffer(reader, fd, buffer, chunksize):
    """Reads bytes from the file descriptor and copies them into a buffer.

    The reads happen in parallel using the pread() syscall; which is only
    available on POSIX systems. If the read fails for any reason, the reader is
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
        self.thread = threading.Thread(
            target=populate_buffer, args=(self, fd, self.buffer, chunksize)
        )
        self.thread.daemon = True

        self.thread.start()


def _expand_console_buffer(cols, max_offset, expandsize, orig_posize, fd):
    # if we are getting close to the end of the console buffer,
    # expand it so that we can read from it successfully.
    if cols == 0:
        return orig_posize[-1], max_offset, orig_posize
    rows = ((max_offset + expandsize) // cols) + 1
    xli.winutils.set_console_screen_buffer_size(cols, rows, fd=fd)
    orig_posize = orig_posize[:3] + (rows,)
    max_offset = (rows - 1) * cols
    return rows, max_offset, orig_posize


def populate_console(reader, fd, buffer, chunksize, queue, expandsize=None):
    """Reads bytes from the file descriptor and puts lines into the queue.
    The reads happened in parallel,
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
    #      care about without a noticeable performance hit.
    #   b. Even with this huge size, it is still possible to write more lines than
    #      this, so we should scroll along with the console.
    # Unfortunately, because we do not have control over the terminal emulator,
    # It is not possible to compute how far back we should set the beginning
    # read position because we don't know how many characters have been popped
    # off the top of the buffer. If we did somehow know this number we could do
    # something like the following:
    #
    #    new_offset = (y*cols) + x
    #    if new_offset == max_offset:
    #        new_offset -= scrolled_offset
    #        x = new_offset%cols
    #        y = new_offset//cols
    #        continue
    #
    # So this method is imperfect and only works as long as the screen has
    # room to expand to.  Thus the trick here is to expand the screen size
    # when we get close enough to the end of the screen. There remain some
    # async issues related to not being able to set the cursor position.
    # but they just affect the alignment / capture of the output of the
    # first command run after a screen resize.
    if expandsize is None:
        expandsize = 100 * chunksize
    x, y, cols, rows = posize = xli.winutils.get_position_size(fd)
    pre_x = pre_y = -1
    orig_posize = posize
    offset = (cols * y) + x
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
        posize = xli.winutils.get_position_size(fd)
        offset = (cols * y) + x
        if ((posize[1], posize[0]) <= (y, x) and posize[2:] == (cols, rows)) or (
            pre_x == x and pre_y == y
        ):
            # already at or ahead of the current cursor position.
            if reader.closed:
                break
            else:
                time.sleep(reader.timeout)
                continue
        elif max_offset <= offset + expandsize:
            ecb = _expand_console_buffer(cols, max_offset, expandsize, orig_posize, fd)
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
            buf = xli.winutils.read_console_output_character(
                x=x, y=y, fd=fd, buf=buffer, bufsize=chunksize, raw=True
            )
        except OSError:
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
        cur_offset = (cols * cur_y) + cur_x
        beg_offset = (cols * y) + x
        end_offset = beg_offset + nread
        if end_offset > cur_offset and cur_offset != max_offset:
            buf = buf[: cur_offset - end_offset]
        # convert to lines
        xshift = cols - x
        yshift = (nread // cols) + (1 if nread % cols > 0 else 0)
        lines = [buf[:xshift]]
        lines += [
            buf[l * cols + xshift : (l + 1) * cols + xshift]
            for l in range(yshift)  # noqa
        ]
        lines = [line for line in lines if line]
        if not lines:
            time.sleep(reader.timeout)
            continue
        # put lines in the queue
        nl = b"\n"
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
        timeout = timeout or XSH.env.get("XONSH_PROC_FREQUENCY")
        super().__init__(fd, timeout=timeout)
        self._buffer = buffer  # this cannot be public
        if buffer is None:
            self._buffer = ctypes.c_char_p(b" " * chunksize)
        self.chunksize = chunksize
        # start reading from stream
        self.thread = threading.Thread(
            target=populate_console,
            args=(self, fd, self._buffer, chunksize, self.queue),
        )
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
