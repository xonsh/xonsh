"""Interface for running Python functions as subprocess-mode commands.

Code for several helper methods in the `ProcProxy` class have been reproduced
without modification from `subprocess.py` in the Python 3.4.2 standard library.
The contents of `subprocess.py` (and, thus, the reproduced methods) are
Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se> and were
licensed to the Python Software foundation under a Contributor Agreement.
"""

import collections.abc as cabc
import io
import os
import signal
import subprocess
import sys
import threading
import time

import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.cli_utils import run_with_partial_args
from xonsh.procs.pipes import PipeChannel
from xonsh.procs.readers import safe_fdclose


def still_writable(fd):
    """Determines whether a file descriptor is still writable by trying to
    write an empty string and seeing if it fails.
    """
    if fd < 0:
        # No pipe was set up (e.g. stdout=None); treat as "not broken by
        # downstream", so the caller attributes the OSError to the alias.
        return True
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
        """Truncates the file for the current thread."""
        return self.handle.truncate(size)

    def writable(self):
        """Returns if file descriptor for the current thread is writable."""
        return self.handle.writable()

    def writelines(self, lines):
        """Writes lines for the file descriptor for the current thread."""
        return self.handle.writelines(lines)


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
    stderr : file-like
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
            stderr.write(xt.endswith_newline(str(r[1])))
            stderr.flush()
        if rlen > 2 and isinstance(r[2], int):
            cmd_result = r[2]
    elif r is not None:
        # for the random object...
        stdout.write(str(r))
        stdout.flush()
    return cmd_result


def get_proc_proxy_name(cls):
    return repr(
        {
            "cls": cls.__class__.__name__,
            "name": getattr(cls, "name", None),
            "func": cls.f,
            "alias": cls.env.get("__ALIAS_NAME", None),
            "pid": cls.pid,
        }
    )


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
        self.f = f
        self.args = args
        self.pid = None
        self.returncode = None
        self._closed_handle_cache = {}
        self._stdin_pipe = None
        self._stdout_pipe = None
        self._stderr_pipe = None

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

        if self.p2cwrite != -1:
            self.stdin = open(self.p2cwrite, "wb", -1, closefd=False)
            if universal_newlines:
                self.stdin = io.TextIOWrapper(
                    self.stdin, write_through=True, line_buffering=False
                )
        elif isinstance(stdin, int) and stdin != 0:
            self.stdin = open(stdin, "wb", -1, closefd=False)

        if self.c2pread != -1:
            self.stdout = open(self.c2pread, "rb", -1, closefd=False)
            if universal_newlines:
                self.stdout = io.TextIOWrapper(self.stdout)
        elif isinstance(self.stdout, int):
            # Raw fd (e.g. 2 from o>e redirect) — already used by c2pwrite
            # for the write end, but there is no readable pipe to expose.
            self.stdout = None

        if self.errread != -1:
            self.stderr = open(self.errread, "rb", -1, closefd=False)
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

    @property
    def pipe_channels(self):
        """All PipeChannel objects managed by this proc."""
        return [
            p for p in (self._stdin_pipe, self._stdout_pipe, self._stderr_pipe) if p
        ]

    def run(self):
        """Set up input/output streams and execute the child function in a new
        thread.  This is part of the `threading.Thread` interface and should
        not be called directly.
        """
        if self.f is None:
            self._close_devnull()
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
        # get stdin
        if self.stdin is None:
            sp_stdin = None
        elif self.p2cread != -1:
            sp_stdin = io.TextIOWrapper(
                open(self.p2cread, "rb", -1, closefd=False), encoding=enc, errors=err
            )
        else:
            sp_stdin = sys.stdin
        # stdout
        if self.c2pwrite != -1:
            sp_stdout = io.TextIOWrapper(
                open(self.c2pwrite, "wb", -1, closefd=False), encoding=enc, errors=err
            )
        else:
            sp_stdout = sys.stdout
        # stderr
        if self.errwrite == self.c2pwrite:
            sp_stderr = sp_stdout
        elif self.errwrite != -1:
            sp_stderr = io.TextIOWrapper(
                open(self.errwrite, "wb", -1, closefd=False), encoding=enc, errors=err
            )
        else:
            sp_stderr = sys.stderr
        # run the function itself
        try:
            alias_stack = XSH.env.get("__ALIAS_STACK", "")
            if self.env and self.env.get("__ALIAS_NAME"):
                alias_stack += ":" + self.env["__ALIAS_NAME"]

            alias_env = {}
            with (
                STDOUT_DISPATCHER.register(sp_stdout),
                STDERR_DISPATCHER.register(sp_stderr),
                xt.redirect_stdout(STDOUT_DISPATCHER),
                xt.redirect_stderr(STDERR_DISPATCHER),
                XSH.env.swap(self.env, overlay=alias_env, __ALIAS_STACK=alias_stack),
            ):
                r = run_with_partial_args(
                    self.f,
                    {
                        "args": self.args,
                        "stdin": sp_stdin,
                        "stdout": sp_stdout,
                        "stderr": sp_stderr,
                        "spec": spec,
                        "stack": spec.stack,
                        "alias_name": getattr(self.f, "__alias_name__", None),
                        "called_alias_name": self.env.get("__ALIAS_NAME")
                        if self.env
                        else None,
                        "env": alias_env,
                    },
                )
        except SystemExit as e:
            r = e.code if isinstance(e.code, int) else int(bool(e.code))
        except OSError:
            status = still_writable(self.c2pwrite) and still_writable(self.errwrite)
            if status:
                # stdout and stderr are still writable, so error must
                # come from function itself.
                xt.print_exception(
                    source_msg="Exception in thread " + get_proc_proxy_name(self)
                )
                r = 1
            else:
                # stdout and stderr are no longer writable, so error must
                # come from the fact that the next process in the pipeline
                # has closed the other side of the pipe. The function then
                # attempted to write to this side of the pipe anyway. This
                # is not truly an error and we should exit gracefully.
                r = 0
        except Exception:
            xt.print_exception(
                source_msg="Exception in thread " + get_proc_proxy_name(self)
            )
            r = 1
        safe_flush(sp_stdout)
        safe_flush(sp_stderr)
        self.returncode = parse_proxy_return(r, sp_stdout, sp_stderr)
        try:
            if not last_in_pipeline:
                # Close wrappers before closing raw fds to avoid
                # "Bad file descriptor" on finalization in Python 3.14+.
                safe_fdclose(sp_stdout)
                safe_fdclose(sp_stderr)
                # Close write ends via PipeChannel to signal EOF to downstream
                for ch in spec.pipe_channels:
                    ch.close_writer()
                if self._stdout_pipe:
                    self._stdout_pipe.close_writer()
                if self._stderr_pipe:
                    self._stderr_pipe.close_writer()
                return
            # clean up
            for handle in (sp_stdout, sp_stderr):
                safe_fdclose(handle, cache=self._closed_handle_cache)
            # Close write ends via PipeChannel to signal EOF to readers
            for ch in spec.pipe_channels:
                ch.close_writer()
            if self._stdout_pipe:
                self._stdout_pipe.close_writer()
            if self._stderr_pipe:
                self._stderr_pipe.close_writer()
        finally:
            self._close_devnull()

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
        # Do NOT close pipe FDs here.  The child subprocesses (e.g.
        # /bin/sleep) are in the same process group and receive SIGINT
        # directly from the terminal — they will die on their own.
        # The worker thread's run() method handles flush/close of its
        # FD wrappers after the child exits.  Closing FDs from the
        # signal handler races with the thread and causes
        # "ValueError: I/O operation on closed file" or, worse,
        # FD-reuse corruption.
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

    def _close_devnull(self):
        if hasattr(self, "_devnull"):
            os.close(self._devnull)
            del self._devnull

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
            self._stdin_pipe = PipeChannel.from_pipe()
            p2cread, p2cwrite = self._stdin_pipe.read_fd, self._stdin_pipe.write_fd
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
            self._stdout_pipe = PipeChannel.from_pipe()
            c2pread, c2pwrite = (
                self._stdout_pipe.read_fd,
                self._stdout_pipe.write_fd,
            )
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
            self._stderr_pipe = PipeChannel.from_pipe()
            errread, errwrite = (
                self._stderr_pipe.read_fd,
                self._stderr_pipe.write_fd,
            )
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
        self.f = f
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
        owned_handles = []  # handles opened here that we must close
        if self.stdin is None:
            stdin = None
        else:
            if isinstance(self.stdin, int):
                inbuf = open(self.stdin, "rb", -1)
            else:
                inbuf = self.stdin
            stdin = io.TextIOWrapper(inbuf, encoding=enc, errors=err)
            if isinstance(self.stdin, int):
                owned_handles.append(stdin)
        stdout = self._pick_buf(self.stdout, sys.stdout, enc, err)
        if stdout is not self.stdout and stdout is not sys.stdout:
            owned_handles.append(stdout)
        stderr = self._pick_buf(self.stderr, sys.stderr, enc, err)
        if stderr is not self.stderr and stderr is not sys.stderr:
            owned_handles.append(stderr)
        # run the actual function
        try:
            alias_env = {}
            with XSH.env.swap(self.env, overlay=alias_env):
                r = run_with_partial_args(
                    self.f,
                    {
                        "args": self.args,
                        "stdin": stdin,
                        "stdout": stdout,
                        "stderr": stderr,
                        "spec": spec,
                        "stack": spec.stack,
                        "alias_name": getattr(self.f, "__alias_name__", None),
                        "called_alias_name": self.env.get("__ALIAS_NAME")
                        if self.env
                        else None,
                        "env": alias_env,
                    },
                )
        except SystemExit as e:
            # the alias function is running in the main thread, so we need to
            # catch SystemExit to prevent the entire shell from exiting (see #5689)
            r = e.code if isinstance(e.code, int) else int(bool(e.code))
        except Exception:
            xt.print_exception(source_msg="Exception in " + get_proc_proxy_name(self))
            r = 1
        self.returncode = parse_proxy_return(r, stdout, stderr)
        safe_flush(stdout)
        safe_flush(stderr)
        for h in owned_handles:
            safe_fdclose(h)
        return self.returncode

    @staticmethod
    def _pick_buf(handle, sysbuf, enc, err):
        if handle is None or handle is sysbuf:
            buf = sysbuf
        elif isinstance(handle, int):
            if handle < 3:
                buf = sysbuf
            else:
                buf = io.TextIOWrapper(open(handle, "wb", -1), encoding=enc, errors=err)
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
