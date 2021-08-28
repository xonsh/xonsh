"""Interface for running Python functions as subprocess-mode commands.

Code for several helper methods in the `ProcProxy` class have been reproduced
without modification from `subprocess.py` in the Python 3.4.2 standard library.
The contents of `subprocess.py` (and, thus, the reproduced methods) are
Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se> and were
licensed to the Python Software foundation under a Contributor Agreement.
"""
import os
import io
import sys
import time
import signal
import inspect
import functools
import threading
import subprocess
import collections.abc as cabc

import xonsh.tools as xt
import xonsh.platform as xp
import xonsh.lazyimps as xli
from xonsh.built_ins import XSH

from xonsh.procs.readers import safe_fdclose


def still_writable(fd):
    """Determines whether a file descriptor is still writable by trying to
    write an empty string and seeing if it fails.
    """
    try:
        os.write(fd, b"")
        status = True
    except OSError:
        status = False
    return status


def safe_flush(handle):
    """Attempts to safely flush a file handle, returns success bool."""
    status = True
    try:
        handle.flush()
    except OSError:
        status = False
    return status


class Handle(int):
    closed = False

    def Close(self, CloseHandle=None):
        CloseHandle = CloseHandle or xli._winapi.CloseHandle
        if not self.closed:
            self.closed = True
            CloseHandle(self)

    def Detach(self):
        if not self.closed:
            self.closed = True
            return int(self)
        raise ValueError("already closed")

    def __repr__(self):
        return f"Handle({int(self)})"

    __del__ = Close
    __str__ = __repr__


class FileThreadDispatcher:
    """Dispatches to different file handles depending on the
    current thread. Useful if you want file operation to go to different
    places for different threads.
    """

    def __init__(self, default=None):
        """
        Parameters
        ----------
        default : file-like or None, optional
            The file handle to write to if a thread cannot be found in
            the registry. If None, a new in-memory instance.

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
        if handle is self:
            # prevent weird recurssion errors
            return self
        self.registry[threading.get_ident()] = handle
        return self

    def deregister(self):
        """Removes the current thread from the registry."""
        ident = threading.get_ident()
        if ident in self.registry:
            # don't remove if we have already been deregistered
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
        if self.default:
            return self.default.isatty()
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
# main thread. Also their creation time should be negligible.
STDOUT_DISPATCHER = FileThreadDispatcher(default=sys.stdout)
STDERR_DISPATCHER = FileThreadDispatcher(default=sys.stderr)


def parse_proxy_return(r, stdout, stderr):
    """Proxies may return a variety of outputs. This handles them generally.

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
            stdout.write(str(r[0]))
            stdout.flush()
        if rlen > 1 and r[1] is not None:
            stderr.write(str(r[1]))
            stderr.flush()
        if rlen > 2 and isinstance(r[2], int):
            cmd_result = r[2]
    elif r is not None:
        # for the random object...
        stdout.write(str(r))
        stdout.flush()
    return cmd_result


def proxy_zero(f, args, stdin, stdout, stderr, spec, stack):
    """Calls a proxy function which takes no parameters."""
    return f()


def proxy_one(f, args, stdin, stdout, stderr, spec, stack):
    """Calls a proxy function which takes one parameter: args"""
    return f(args)


def proxy_two(f, args, stdin, stdout, stderr, spec, stack):
    """Calls a proxy function which takes two parameter: args and stdin."""
    return f(args, stdin)


def proxy_three(f, args, stdin, stdout, stderr, spec, stack):
    """Calls a proxy function which takes three parameter: args, stdin, stdout."""
    return f(args, stdin, stdout)


def proxy_four(f, args, stdin, stdout, stderr, spec, stack):
    """Calls a proxy function which takes four parameter: args, stdin, stdout,
    and stderr.
    """
    return f(args, stdin, stdout, stderr)


def proxy_five(f, args, stdin, stdout, stderr, spec, stack):
    """Calls a proxy function which takes four parameter: args, stdin, stdout,
    stderr, and spec.
    """
    return f(args, stdin, stdout, stderr, spec)


PROXIES = (proxy_zero, proxy_one, proxy_two, proxy_three, proxy_four, proxy_five)


def partial_proxy(f):
    """Dispatches the appropriate proxy function based on the number of args."""
    numargs = 0

    for name, param in inspect.signature(f).parameters.items():
        # handle *args/**kwargs signature
        if param.kind in {param.VAR_KEYWORD, param.VAR_POSITIONAL}:
            numargs = 6
            break
        if (
            param.kind == param.POSITIONAL_ONLY
            or param.kind == param.POSITIONAL_OR_KEYWORD
        ):
            numargs += 1
        elif name in xt.ALIAS_KWARG_NAMES and param.kind == param.KEYWORD_ONLY:
            numargs += 1
    if numargs < 6:
        return functools.partial(PROXIES[numargs], f)
    elif numargs == 6:
        # don't need to partial.
        return f
    else:
        e = "Expected proxy with 6 or fewer arguments for {}, not {}"
        raise xt.XonshError(e.format(", ".join(xt.ALIAS_KWARG_NAMES), numargs))


class ProcProxyThread(threading.Thread):
    """
    Class representing a function to be run as a subprocess-mode command.
    """

    def __init__(
        self,
        f,
        args,
        stdin=None,
        stdout=None,
        stderr=None,
        universal_newlines=False,
        close_fds=False,
        env=None,
    ):
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
        close_fds : bool, optional
            Whether or not to close file descriptors. This is here for Popen
            compatability and currently does nothing.
        env : Mapping, optional
            Environment mapping.
        """
        self.orig_f = f
        self.f = partial_proxy(f)
        self.args = args
        self.pid = None
        self.returncode = None
        self._closed_handle_cache = {}

        handles = self._get_handles(stdin, stdout, stderr)
        (
            self.p2cread,
            self.p2cwrite,
            self.c2pread,
            self.c2pwrite,
            self.errread,
            self.errwrite,
        ) = handles

        # default values
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.close_fds = close_fds
        self.env = env
        self._interrupted = False

        if xp.ON_WINDOWS:
            if self.p2cwrite != -1:
                self.p2cwrite = xli.msvcrt.open_osfhandle(self.p2cwrite.Detach(), 0)
            if self.c2pread != -1:
                self.c2pread = xli.msvcrt.open_osfhandle(self.c2pread.Detach(), 0)
            if self.errread != -1:
                self.errread = xli.msvcrt.open_osfhandle(self.errread.Detach(), 0)

        if self.p2cwrite != -1:
            self.stdin = io.open(self.p2cwrite, "wb", -1)
            if universal_newlines:
                self.stdin = io.TextIOWrapper(
                    self.stdin, write_through=True, line_buffering=False
                )
        elif isinstance(stdin, int) and stdin != 0:
            self.stdin = io.open(stdin, "wb", -1)

        if self.c2pread != -1:
            self.stdout = io.open(self.c2pread, "rb", -1)
            if universal_newlines:
                self.stdout = io.TextIOWrapper(self.stdout)

        if self.errread != -1:
            self.stderr = io.open(self.errread, "rb", -1)
            if universal_newlines:
                self.stderr = io.TextIOWrapper(self.stderr)

        # Set some signal handles, if we can. Must come before process
        # is started to prevent deadlock on windows
        self.old_int_handler = None
        if xt.on_main_thread():
            self.old_int_handler = signal.signal(signal.SIGINT, self._signal_int)
        # start up the proc
        super().__init__()
        # This is so the thread will use the same swapped values as the origin one.
        self.original_swapped_values = XSH.env.get_swapped_values()
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
        # Set the thread-local swapped values.
        XSH.env.set_swapped_values(self.original_swapped_values)
        spec = self._wait_and_getattr("spec")
        last_in_pipeline = spec.last_in_pipeline
        if last_in_pipeline:
            capout = spec.captured_stdout  # NOQA
            caperr = spec.captured_stderr  # NOQA
        env = XSH.env
        enc = env.get("XONSH_ENCODING")
        err = env.get("XONSH_ENCODING_ERRORS")
        if xp.ON_WINDOWS:
            if self.p2cread != -1:
                self.p2cread = xli.msvcrt.open_osfhandle(self.p2cread.Detach(), 0)
            if self.c2pwrite != -1:
                self.c2pwrite = xli.msvcrt.open_osfhandle(self.c2pwrite.Detach(), 0)
            if self.errwrite != -1:
                self.errwrite = xli.msvcrt.open_osfhandle(self.errwrite.Detach(), 0)
        # get stdin
        if self.stdin is None:
            sp_stdin = None
        elif self.p2cread != -1:
            sp_stdin = io.TextIOWrapper(
                io.open(self.p2cread, "rb", -1), encoding=enc, errors=err
            )
        else:
            sp_stdin = sys.stdin
        # stdout
        if self.c2pwrite != -1:
            sp_stdout = io.TextIOWrapper(
                io.open(self.c2pwrite, "wb", -1), encoding=enc, errors=err
            )
        else:
            sp_stdout = sys.stdout
        # stderr
        if self.errwrite == self.c2pwrite:
            sp_stderr = sp_stdout
        elif self.errwrite != -1:
            sp_stderr = io.TextIOWrapper(
                io.open(self.errwrite, "wb", -1), encoding=enc, errors=err
            )
        else:
            sp_stderr = sys.stderr
        # run the function itself
        try:
            alias_stack = XSH.env.get("__ALIAS_STACK", "")
            if self.env and self.env.get("__ALIAS_NAME"):
                alias_stack += ":" + self.env["__ALIAS_NAME"]

            with STDOUT_DISPATCHER.register(sp_stdout), STDERR_DISPATCHER.register(
                sp_stderr
            ), xt.redirect_stdout(STDOUT_DISPATCHER), xt.redirect_stderr(
                STDERR_DISPATCHER
            ), XSH.env.swap(
                self.env, __ALIAS_STACK=alias_stack
            ):
                r = self.f(self.args, sp_stdin, sp_stdout, sp_stderr, spec, spec.stack)
        except SystemExit as e:
            r = e.code if isinstance(e.code, int) else int(bool(e.code))
        except OSError:
            status = still_writable(self.c2pwrite) and still_writable(self.errwrite)
            if status:
                # stdout and stderr are still writable, so error must
                # come from function itself.
                xt.print_exception()
                r = 1
            else:
                # stdout and stderr are no longer writable, so error must
                # come from the fact that the next process in the pipeline
                # has closed the other side of the pipe. The function then
                # attempted to write to this side of the pipe anyway. This
                # is not truly an error and we should exit gracefully.
                r = 0
        except Exception:
            xt.print_exception()
            r = 1
        safe_flush(sp_stdout)
        safe_flush(sp_stderr)
        self.returncode = parse_proxy_return(r, sp_stdout, sp_stderr)
        if not last_in_pipeline and not xp.ON_WINDOWS:
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
        # Check if we have already been interrupted. This should prevent
        # the possibility of infinite recursion.
        if self._interrupted:
            return
        self._interrupted = True
        # close file handles here to stop an processes piped to us.
        handles = (
            self.p2cread,
            self.p2cwrite,
            self.c2pread,
            self.c2pwrite,
            self.errread,
            self.errwrite,
        )
        for handle in handles:
            safe_fdclose(handle)
        if self.poll() is not None:
            self._restore_sigint(frame=frame)
        if xt.on_main_thread() and not xp.ON_WINDOWS:
            signal.pthread_kill(threading.get_ident(), signal.SIGINT)

    def _restore_sigint(self, frame=None):
        old = self.old_int_handler
        if old is not None:
            if xt.on_main_thread():
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
        if not hasattr(self, "_devnull"):
            self._devnull = os.open(os.devnull, os.O_RDWR)
        return self._devnull

    if xp.ON_WINDOWS:

        def _make_inheritable(self, handle):
            """Return a duplicate of handle, which is inheritable"""
            h = xli._winapi.DuplicateHandle(
                xli._winapi.GetCurrentProcess(),
                handle,
                xli._winapi.GetCurrentProcess(),
                0,
                1,
                xli._winapi.DUPLICATE_SAME_ACCESS,
            )
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
                p2cread = xli._winapi.GetStdHandle(xli._winapi.STD_INPUT_HANDLE)
                if p2cread is None:
                    p2cread, _ = xli._winapi.CreatePipe(None, 0)
                    p2cread = Handle(p2cread)
                    xli._winapi.CloseHandle(_)
            elif stdin == subprocess.PIPE:
                p2cread, p2cwrite = Handle(p2cread), Handle(p2cwrite)
            elif stdin == subprocess.DEVNULL:
                p2cread = xli.msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stdin, int):
                p2cread = xli.msvcrt.get_osfhandle(stdin)
            else:
                # Assuming file-like object
                p2cread = xli.msvcrt.get_osfhandle(stdin.fileno())
            p2cread = self._make_inheritable(p2cread)

            if stdout is None:
                c2pwrite = xli._winapi.GetStdHandle(xli._winapi.STD_OUTPUT_HANDLE)
                if c2pwrite is None:
                    _, c2pwrite = xli._winapi.CreatePipe(None, 0)
                    c2pwrite = Handle(c2pwrite)
                    xli._winapi.CloseHandle(_)
            elif stdout == subprocess.PIPE:
                c2pread, c2pwrite = xli._winapi.CreatePipe(None, 0)
                c2pread, c2pwrite = Handle(c2pread), Handle(c2pwrite)
            elif stdout == subprocess.DEVNULL:
                c2pwrite = xli.msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stdout, int):
                c2pwrite = xli.msvcrt.get_osfhandle(stdout)
            else:
                # Assuming file-like object
                c2pwrite = xli.msvcrt.get_osfhandle(stdout.fileno())
            c2pwrite = self._make_inheritable(c2pwrite)

            if stderr is None:
                errwrite = xli._winapi.GetStdHandle(xli._winapi.STD_ERROR_HANDLE)
                if errwrite is None:
                    _, errwrite = xli._winapi.CreatePipe(None, 0)
                    errwrite = Handle(errwrite)
                    xli._winapi.CloseHandle(_)
            elif stderr == subprocess.PIPE:
                errread, errwrite = xli._winapi.CreatePipe(None, 0)
                errread, errwrite = Handle(errread), Handle(errwrite)
            elif stderr == subprocess.STDOUT:
                errwrite = c2pwrite
            elif stderr == subprocess.DEVNULL:
                errwrite = xli.msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stderr, int):
                errwrite = xli.msvcrt.get_osfhandle(stderr)
            else:
                # Assuming file-like object
                errwrite = xli.msvcrt.get_osfhandle(stderr.fileno())
            errwrite = self._make_inheritable(errwrite)

            return (p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite)

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

            return (p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite)


#
# Foreground Thread Process Proxies
#


class ProcProxy:
    """This is process proxy class that runs its alias functions on the
    same thread that it was called from, which is typically the main thread.
    This prevents the process from running on a background thread, but enables
    debugger and profiler tools (functions) be run on the same thread that they
    are attempting to debug.
    """

    def __init__(
        self,
        f,
        args,
        stdin=None,
        stdout=None,
        stderr=None,
        universal_newlines=False,
        close_fds=False,
        env=None,
    ):
        self.orig_f = f
        self.f = partial_proxy(f)
        self.args = args
        self.pid = os.getpid()
        self.returncode = None
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.universal_newlines = universal_newlines
        self.close_fds = close_fds
        self.env = env

    def poll(self):
        """Check if the function has completed via the returncode or None."""
        return self.returncode

    def wait(self, timeout=None):
        """Runs the function and returns the result. Timeout argument only
        present for API compatibility.
        """
        if self.f is None:
            return 0
        env = XSH.env
        enc = env.get("XONSH_ENCODING")
        err = env.get("XONSH_ENCODING_ERRORS")
        spec = self._wait_and_getattr("spec")
        # set file handles
        if self.stdin is None:
            stdin = None
        else:
            if isinstance(self.stdin, int):
                inbuf = io.open(self.stdin, "rb", -1)
            else:
                inbuf = self.stdin
            stdin = io.TextIOWrapper(inbuf, encoding=enc, errors=err)
        stdout = self._pick_buf(self.stdout, sys.stdout, enc, err)
        stderr = self._pick_buf(self.stderr, sys.stderr, enc, err)
        # run the actual function
        try:
            with XSH.env.swap(self.env):
                r = self.f(self.args, stdin, stdout, stderr, spec, spec.stack)
        except Exception:
            xt.print_exception()
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
                buf = io.TextIOWrapper(
                    io.open(handle, "wb", -1), encoding=enc, errors=err
                )
        elif hasattr(handle, "encoding"):
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
