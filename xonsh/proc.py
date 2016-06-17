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
import sys
import time
import builtins
from functools import wraps
from threading import Thread
from collections import Sequence, namedtuple
from subprocess import (Popen, PIPE, DEVNULL, STDOUT, TimeoutExpired,
                        CalledProcessError)

from xonsh.tools import (redirect_stdout, redirect_stderr, ON_WINDOWS, ON_LINUX,
                         fallback, print_exception, XonshCalledProcessError)

if ON_LINUX:
    from xonsh.teepty import TeePTY
else:
    TeePTY = None

if ON_WINDOWS:
    import _winapi
    import msvcrt

    class Handle(int):
        closed = False

        def Close(self, CloseHandle=_winapi.CloseHandle):
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


class ProcProxy(Thread):
    """
    Class representing a function to be run as a subprocess-mode command.
    """
    def __init__(self, f, args,
                 stdin=None,
                 stdout=None,
                 stderr=None,
                 universal_newlines=False):
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
        """
        self.f = f
        """
        The function to be executed.  It should be a function of four
        arguments, described below.

        Parameters
        ----------
        args : list
            A (possibly empty) list containing the arguments that were given on
            the command line
        stdin : file-like
            A file-like object representing stdin (input can be read from
            here).
        stdout : file-like
            A file-like object representing stdout (normal output can be
            written here).
        stderr : file-like
            A file-like object representing stderr (error output can be
            written here).
        """
        self.args = args
        self.pid = None
        self.returncode = None
        self.wait = self.join

        handles = self._get_handles(stdin, stdout, stderr)
        (self.p2cread, self.p2cwrite,
         self.c2pread, self.c2pwrite,
         self.errread, self.errwrite) = handles

        # default values
        self.stdin = stdin
        self.stdout = None
        self.stderr = None

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
        if self.c2pread != -1:
            self.stdout = io.open(self.c2pread, 'rb', -1)
            if universal_newlines:
                self.stdout = io.TextIOWrapper(self.stdout)

        if self.errread != -1:
            self.stderr = io.open(self.errread, 'rb', -1)
            if universal_newlines:
                self.stderr = io.TextIOWrapper(self.stderr)

        Thread.__init__(self)
        self.start()

    def run(self):
        """Set up input/output streams and execute the child function in a new
        thread.  This is part of the `threading.Thread` interface and should
        not be called directly.
        """
        if self.f is None:
            return
        if self.stdin is not None:
            sp_stdin = io.TextIOWrapper(io.open(self.p2cread, 'rb', -1))
        else:
            sp_stdin = io.StringIO("")

        if ON_WINDOWS:
            if self.c2pwrite != -1:
                self.c2pwrite = msvcrt.open_osfhandle(self.c2pwrite.Detach(), 0)
            if self.errwrite != -1:
                self.errwrite = msvcrt.open_osfhandle(self.errwrite.Detach(), 0)

        if self.c2pwrite != -1:
            sp_stdout = io.TextIOWrapper(io.open(self.c2pwrite, 'wb', -1))
        else:
            sp_stdout = sys.stdout
        if self.errwrite == self.c2pwrite:
            sp_stderr = sp_stdout
        elif self.errwrite != -1:
            sp_stderr = io.TextIOWrapper(io.open(self.errwrite, 'wb', -1))
        else:
            sp_stderr = sys.stderr

        r = self.f(self.args, sp_stdin, sp_stdout, sp_stderr)
        self.returncode = 0 if r is None else r

    def poll(self):
        """Check if the function has completed.

        Returns
        -------
        `None` if the function is still executing, `True` if the function
        finished successfully, and `False` if there was an error.
        """
        return self.returncode

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
            elif stdin == PIPE:
                p2cread, p2cwrite = _winapi.CreatePipe(None, 0)
                p2cread, p2cwrite = Handle(p2cread), Handle(p2cwrite)
            elif stdin == DEVNULL:
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
            elif stdout == PIPE:
                c2pread, c2pwrite = _winapi.CreatePipe(None, 0)
                c2pread, c2pwrite = Handle(c2pread), Handle(c2pwrite)
            elif stdout == DEVNULL:
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
            elif stderr == PIPE:
                errread, errwrite = _winapi.CreatePipe(None, 0)
                errread, errwrite = Handle(errread), Handle(errwrite)
            elif stderr == STDOUT:
                errwrite = c2pwrite
            elif stderr == DEVNULL:
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
            elif stdin == PIPE:
                p2cread, p2cwrite = os.pipe()
            elif stdin == DEVNULL:
                p2cread = self._get_devnull()
            elif isinstance(stdin, int):
                p2cread = stdin
            else:
                # Assuming file-like object
                p2cread = stdin.fileno()

            if stdout is None:
                pass
            elif stdout == PIPE:
                c2pread, c2pwrite = os.pipe()
            elif stdout == DEVNULL:
                c2pwrite = self._get_devnull()
            elif isinstance(stdout, int):
                c2pwrite = stdout
            else:
                # Assuming file-like object
                c2pwrite = stdout.fileno()

            if stderr is None:
                pass
            elif stderr == PIPE:
                errread, errwrite = os.pipe()
            elif stderr == STDOUT:
                errwrite = c2pwrite
            elif stderr == DEVNULL:
                errwrite = self._get_devnull()
            elif isinstance(stderr, int):
                errwrite = stderr
            else:
                # Assuming file-like object
                errwrite = stderr.fileno()

            return (p2cread, p2cwrite,
                    c2pread, c2pwrite,
                    errread, errwrite)


def wrap_simple_command(f, args, stdin, stdout, stderr):
    """Decorator for creating 'simple' callable aliases."""
    bgable = getattr(f, '__xonsh_backgroundable__', True)
    @wraps(f)
    def wrapped_simple_command(args, stdin, stdout, stderr):
        try:
            i = stdin.read()
            if bgable:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    r = f(args, i)
            else:
                r = f(args, i)

            cmd_result = 0
            if isinstance(r, str):
                stdout.write(r)
            elif isinstance(r, Sequence):
                if r[0] is not None:
                    stdout.write(r[0])
                if r[1] is not None:
                    stderr.write(r[1])
                if len(r) > 2 and r[2] is not None:
                    cmd_result = r[2]
            elif r is not None:
                stdout.write(str(r))
            return cmd_result
        except Exception:
            print_exception()
            return 1  # returncode for failure
    return wrapped_simple_command


class SimpleProcProxy(ProcProxy):
    """Variant of `ProcProxy` for simpler functions.

    The function passed into the initializer for `SimpleProcProxy` should have
    the form described in the xonsh tutorial.  This function is then wrapped to
    make a new function of the form expected by `ProcProxy`.
    """

    def __init__(self, f, args, stdin=None, stdout=None, stderr=None,
                 universal_newlines=False):
        f = wrap_simple_command(f, args, stdin, stdout, stderr)
        super().__init__(f, args, stdin, stdout, stderr, universal_newlines)

#
# Foreground Process Proxies
#

class ForegroundProcProxy(object):
    """This is process proxy class that runs its alias functions on the
    same thread that it was called from, which is typically the main thread.
    This prevents backgrounding the process, but enables debugger and
    profiler tools (functions) be run on the same thread that they are
    attempting to debug.
    """

    def __init__(self, f, args, stdin=None, stdout=None, stderr=None,
                 universal_newlines=False):
        self.f = f
        self.args = args
        self.pid = os.getpid()
        self.returncode = None
        self.stdin = stdin
        self.stdout = None
        self.stderr = None
        self.universal_newlines = universal_newlines

    def poll(self):
        """Check if the function has completed via the returncode or None.
        """
        return self.returncode

    def wait(self, timeout=None):
        """Runs the function and returns the result. Timeout argument only
        present for API compatability.
        """
        if self.f is None:
            return
        if self.stdin is None:
            stdin = io.StringIO("")
        else:
            stdin = io.TextIOWrapper(self.stdin)
        r = self.f(self.args, stdin, self.stdout, self.stderr)
        self.returncode = 0 if r is None else r
        return self.returncode


class SimpleForegroundProcProxy(ForegroundProcProxy):
    """Variant of `ForegroundProcProxy` for simpler functions.

    The function passed into the initializer for `SimpleForegroundProcProxy`
    should have the form described in the xonsh tutorial. This function is
    then wrapped to make a new function of the form expected by
    `ForegroundProcProxy`.
    """

    def __init__(self, f, args, stdin=None, stdout=None, stderr=None,
                 universal_newlines=False):
        f = wrap_simple_command(f, args, stdin, stdout, stderr)
        super().__init__(f, args, stdin, stdout, stderr, universal_newlines)


def foreground(f):
    """Decorator that specifies that a callable alias should be run only
    as a foreground process. This is often needed for debuggers and profilers.
    """
    f.__xonsh_backgroundable__ = False
    return f

#
# Pseudo-terminal Proxies
#


@fallback(ON_LINUX, Popen)
class TeePTYProc(object):

    def __init__(self, args, stdin=None, stdout=None, stderr=None, preexec_fn=None,
                 env=None, universal_newlines=False):
        """Popen replacement for running commands in teed psuedo-terminal. This
        allows the capturing AND streaming of stdout and stderr.  Availability
        is Linux-only.
        """
        self.stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self.args = args
        self.universal_newlines = universal_newlines
        xenv = builtins.__xonsh_env__ if hasattr(builtins, '__xonsh_env__') \
                                      else {'XONSH_ENCODING': 'utf-8',
                                            'XONSH_ENCODING_ERRORS': 'strict'}

        if not os.access(args[0], os.F_OK):
            raise FileNotFoundError('command {0!r} not found'.format(args[0]))
        elif not os.access(args[0], os.X_OK) or os.path.isdir(args[0]):
            raise PermissionError('permission denied: {0!r}'.format(args[0]))
        self._tpty = tpty = TeePTY(encoding=xenv.get('XONSH_ENCODING'),
                                   errors=xenv.get('XONSH_ENCODING_ERRORS'))
        if preexec_fn is not None:
            preexec_fn()
        delay = xenv.get('TEEPTY_PIPE_DELAY')
        tpty.spawn(args, env=env, stdin=stdin, delay=delay)

    @property
    def pid(self):
        """The pid of the spawned process."""
        return self._tpty.pid

    @property
    def returncode(self):
        """The return value of the spawned process or None if the process
        exited due to a signal."""
        if os.WIFEXITED(self._tpty.wcode):
            return os.WEXITSTATUS(self._tpty.wcode)
        else:
            return None

    @property
    def signal(self):
        """If the process was terminated by a signal a 2-tuple is returned
        containing the signal number and a boolean indicating whether a core
        file was produced. Otherwise None is returned."""
        if os.WIFSIGNALED(self._tpty.wcode):
            return (os.WTERMSIG(self._tpty.wcode),
                    os.WCOREDUMP(self._tpty.wcode))
        else:
            return None

    def poll(self):
        """Polls the spawned process and returns the os.wait code."""
        return _wcode_to_popen(self._tpty.wcode)

    def wait(self, timeout=None):
        """Waits for the spawned process to finish, up to a timeout.
        Returns the return os.wait code."""
        tpty = self._tpty
        t0 = time.time()
        while tpty.wcode is None:
            if timeout is not None and timeout < (time.time() - t0):
                raise TimeoutExpired
        return _wcode_to_popen(tpty.wcode)

    @property
    def stdout(self):
        """The stdout (and stderr) that was tee'd into a buffer by the psuedo-terminal.
        """
        if self._stdout is not None:
            pass
        elif self.universal_newlines:
            self._stdout = io.StringIO(str(self._tpty))
            self._stdout.seek(0)
        else:
            self._stdout = self._tpty.buffer
        return self._stdout


def _wcode_to_popen(code):
    """Converts os.wait return code into Popen format."""
    if os.WIFEXITED(code):
        return os.WEXITSTATUS(code)
    elif os.WIFSIGNALED(code):
        return -1 * os.WTERMSIG(code)
    else:
        # Can this happen? Let's find out. Returning None is not an option.
        raise ValueError("Invalid os.wait code: {}".format(code))


_CCTuple = namedtuple("_CCTuple", ["stdin",
                                   "stdout",
                                   "stderr",
                                   "pid",
                                   "returncode",
                                   "args",
                                   "alias",
                                   "stdin_redirect",
                                   "stdout_redirect",
                                   "stderr_redirect",
                                   "timestamp",
                                   "executed_cmd"])


class CompletedCommand(_CCTuple):
    """Represents a completed subprocess-mode command."""

    def __bool__(self):
        return self.returncode == 0

    def __iter__(self):
        if not self.stdout:
            raise StopIteration()

        pre = self.stdout
        post = None

        while post != '':
            pre, sep, post = pre.partition('\n')
            # this line may be optional since we use universal newlines.
            pre = pre[:-1] if pre and pre[-1] == '\r' else pre
            yield pre
            pre = post


    def itercheck(self):
        yield from self
        if self.returncode:
            # I included self, as providing access to stderr and other details
            # useful when instance isn't assigned to a variable in the shell.
            raise XonshCalledProcessError(self.returncode, self.executed_cmd,
                                          self.stdout, self.stderr, self)

    @property
    def inp(self):
        """Creates normalized input string from args."""
        return ' '.join(self.args)

    @property
    def out(self):
        """Alias to stdout."""
        return self.stdout

    @property
    def err(self):
        """Alias to stderr."""
        return self.stderr

    @property
    def rtn(self):
        """Alias to return code."""
        return self.returncode

CompletedCommand.__new__.__defaults__ = (None,) * len(CompletedCommand._fields)


class HiddenCompletedCommand(CompletedCommand):
    def __repr__(self):
        return ''
