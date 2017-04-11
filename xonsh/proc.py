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
import ctypes
import signal
import inspect
import builtins
import functools
import threading
import subprocess
import collections.abc as cabc

import slug

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


STDOUT_CAPTURE_KINDS = {'stdout', 'object'}


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


def parse_redirect(word, arg):
    """parse_redirect(str) -> stdin, stdout, stderr
    Attempts to parse all the variations of < and > redirects.
    """
    if word.startswith('<'):
        post = word[1:]
        if post and arg:
            return None, None, None
        if not post and not arg:
            return None, None, None
        return (arg or post), None, None
    elif '>' in word:
        # FIXME: Handle for files that end with '>'
        if word.endswith('>'):
            pre, post = word[:-1], ''
        elif word.startswith('>'):
            pre, post = '', word[1:]
        else:
            pre, post = word.split('>', 1)
        if pre not in ('', 'e', 'err', 'o', 'out'):
            return None, None, None

        if not post and not arg:
            return None, None, None

        if post and arg:
            return None, None, None

        # These only work if part of the same word
        if post in ('', 'o', 'out') and pre in ('e', 'err'):
            return None, None, {'out'}
        elif post in ('e', 'err') and pre in ('', 'o', 'out'):
            return None, {'err'}, None

        post = post or arg

        if pre in ('', 'o', 'out'):
            return None, post, None
        elif pre in ('e', 'err'):
            return None, None, post
        else:
            return None, None, None

    else:
        return None, None, None

def build_proc(proc, before, after):
    proc = proc.copy()  # TODO: Resolve aliases
    stdin = stdout = stderr = None
    if after is not None:
        stdout = after.side_in
    if before is not None:
        stdin = before.side_out

    # FIXME: https://github.com/xonsh/xonsh/issues/2335
    # Find redirections
    while len(proc) > 1:
        # FIXME: Handle prefix redirect (`< foo.bar mycmd`)
        (i, o, e), idx = parse_redirect(proc[-1], None), -1
        if i == o == e == None and len(proc) > 2:  # noqa: E711
            (i, o, e), idx = parse_redirect(proc[-2], proc[-1]), slice(-2, None)
        if i == o == e == None:  # noqa: E711
            break

        del proc[idx]

        if i is not None and stdin is not None:
            raise ValueError
        else:
            stdin = i
        if o is not None and stdout is not None:
            raise ValueError
        else:
            stdout = o
        if e is not None and stderr is not None:
            raise ValueError
        else:
            stderr = e

    if isinstance(stdin, str):
        stdin = open(stdin, 'wb')
    if isinstance(stdout, str):
        stdout = open(stdout, 'wb')
    if isinstance(stderr, str):
        stderr = open(stderr, 'wb')

    if stdout == {'err'} and stderr == {'out'}:
        raise ValueError
    elif stdout == {'err'}:
        stdout = stderr
    elif stderr == {'out'}:
        stderr = stdout

    alias = builtins.aliases.get(proc[0])
    if callable(alias):
        return XonshAlias(alias, proc, stdin=stdin, stdout=stdout, stderr=stderr)
    elif isinstance(alias, cabc.Sequence):
        proc[0:1] = alias
    elif alias is None:
        # No alias, do nothing
        pass
    else:
        raise RuntimeError("Unknown alias: {!r}".format(alias))
    return slug.Process(proc, stdin=stdin, stdout=stdout, stderr=stderr)


class Job:
    """
    Top-level object for a pipeline.
    """
    # FIXME: Implement rtns, inp, and other properties
    def __init__(self):
        self.processgroup = None
        self.background = False
        self.started = None
        self.outbuffer = None
        self.finished = threading.Event()

    @classmethod
    def from_cmds(cls, cmds, captured=False):
        """
        Build a Job from a sequence describing the processes, redirections,
        piping, etc.

        captured is one of False, 'stdout', 'object', 'hiddenobject'
        """
        cmds = list(cmds)
        self = cls()
        # Phase 0: Check for background
        self.background = False
        if cmds[-1] == '&':
            self.background = True
            del cmds[-1]

        # Phase 1: Build inter-process pipes
        for i, item in enumerate(cmds):
            if item == '|':
                cmds[i] = slug.Pipe()

        # Phase 2: Build processes
        processes = []  # List of processes
        closers = []  # List of file-likes that need to be closed on start
        for procidx, proc in enumerate(cmds):
            if not isinstance(proc, list):
                continue

            before = cmds[procidx-1] if procidx > 0 else None
            after = cmds[procidx+1] if procidx < len(cmds) - 1 else None

            proc = build_proc(proc, before, after)
            processes.append(proc)
            closers += [proc.stdin, proc.stdout, proc.stderr]

        # Phase 3: Post-processing
        self.outbuffer = io.BytesIO()
        if proc.stdout is None:  # If it hasn't otherwise been redirected
            # TODO: Make this a PTY if the system stdout is a TTY
            # FIXME: Bundle stderr with this if necessary
            output = slug.Pipe()
            proc.stdout = output.side_in
            closers += [output.side_in]

            if captured:
                buf = output
            else:
                buf = slug.Pipe()
                slug.Tee(output.side_out, sys.stdout, buf.side_in.write, buf.side_in.close)

            slug.Tee(
                buf.side_out,
                self.outbuffer,
                lambda data: None,
                self.finished.set,
                keepopen=True,
            )
        else:
            # Don't wait on finished
            self.finished.set()

        self._files_to_close = {f for f in closers if f is not None}

        with slug.ProcessGroup() as pg:
            # TODO: Handle if proc is an alias
            for proc in processes:
                pg.add(proc)

        # TODO: aliases
        self.processgroup = pg
        return self

    @property
    def procs(self):
        yield from self.processgroup

    def start(self):
        self.started = time.time()
        # TODO: Handle aliases
        self.processgroup.start()
        for f in self._files_to_close:
            f.close()
        self._files_to_close = ()

    def wait(self):
        self.processgroup.join()
        self.finished.wait()

    @property
    def output(self):
        # FIXME: Cache this in some way
        env = builtins.__xonsh_env__
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')
        if self.outbuffer is not None:
            return self.outbuffer.getvalue().decode(enc, err)

    @property
    def status(self):
        if self.processgroup:
            return self.processgroup.status


class HiddenJob(Job):
    def __repr__(self):
        return ''


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


def proxy_four(f, args, stdin, stdout, stderr, job):
    """Calls a proxy function which takes four parameter: args, stdin, stdout,
    and stderr.
    """
    return f(args, stdin, stdout, stderr)


PROXIES = (proxy_zero, proxy_one, proxy_two, proxy_three, proxy_four)
PROXY_KWARG_NAMES = frozenset(['args', 'stdin', 'stdout', 'stderr', 'job'])


def partial_proxy(f):
    """Dispatches the approriate proxy function based on the number of args."""
    numargs = 0
    for name, param in inspect.signature(f).parameters.items():
        if param.kind == param.POSITIONAL_ONLY or \
           param.kind == param.POSITIONAL_OR_KEYWORD:
            numargs += 1
        elif name in PROXY_KWARG_NAMES and param.kind == param.KEYWORD_ONLY:
            numargs += 1
    if numargs < 5:
        return functools.partial(PROXIES[numargs], f)
    elif numargs == 5:
        # don't need to partial.
        return f
    else:
        e = 'Expected proxy with 5 or fewer arguments for {}, not {}'
        raise XonshError(e.format(', '.join(PROXY_KWARG_NAMES), numargs))


def may_wrap_as_text(fo):
    """
    Might wrap a file-like as its text equivelent, or could return the same
    object.
    """
    if fo is None:
        return

    if 'b' in fo.mode:
        env = builtins.__xonsh_env__
        enc = env.get('XONSH_ENCODING')
        err = env.get('XONSH_ENCODING_ERRORS')

        if '+' in fo.mode:
            buf = io.BufferedRandom(fo)
        elif 'w' in fo.mode or 'a' in fo.mode:
            buf = io.BufferedWriter(fo)
        else:
            buf = io.BufferedReader(fo)
        # XXX: Not sure Python's standard IO uses write_through
        fo = io.TextIOWrapper(buf, encoding=enc, errors=err, line_buffering=True, write_through=True)
    return fo


class XonshAlias(slug.ThreadedVirtualProcess):
    def __init__(self, func, args, *, stdin=None, stdout=None, stderr=None, job=None):
        super().__init__()
        self.func = func
        self.func_normed = partial_proxy(func)
        self.args = args
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.job = job
        self._return_code = None

    def run(self):
        self.stdin = may_wrap_as_text(self.stdin)
        self.stdout = may_wrap_as_text(self.stdout)
        self.stderr = may_wrap_as_text(self.stderr)

        try:
            with STDOUT_DISPATCHER.register(self.stdout), \
                 STDERR_DISPATCHER.register(self.stderr), \
                 redirect_stdout(STDOUT_DISPATCHER), \
                 redirect_stderr(STDERR_DISPATCHER):
                rv = self.func_normed(self.args, self.stdin, self.stdout, self.stderr, self.job)
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
        # FIXME: Returns

    @property
    def return_code(self):
        return self._return_code

    def status(self):
        if self.ident is None:
            return slug.INIT
        elif self.is_alive():
            return slug.RUNNING
        else:
            return slug.FINISHED

    def terminate(self):
        # Can't kill threads, so just try to make it die
        self.stdin.close()
        self.stdout.close()
        self.stderr.close()

    def kill(self):
        # Can't kill threads, even rudely
        self.terminate()

    def pause(self):
        # Pausing threads is potentially dangerous
        pass

    def unpause(self):
        # And therefore we can't continue them either
        pass

    def on_signal(self, sig):
        # Don't have a way to pass signals
        pass


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


def update_fg_process_group(pipeline_group, background):
    if background:
        return False
    if not ON_POSIX:
        return False
    env = builtins.__xonsh_env__
    if not env.get('XONSH_INTERACTIVE'):
        return False
    return give_terminal_to(pipeline_group)


def pause_call_resume(p, f, *args, **kwargs):
    """For a process p, this will call a function f with the remaining args and
    and kwargs. If the process cannot accept signals, the function will be called.

    Parameters
    ----------
    p : Process object or similar
    f : callable
    args : remaining arguments
    kwargs : keyword arguments
    """
    p.pause()
    try:
        f(*args, **kwargs)
    except Exception:
        pass
    p.unpause()


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
        self.registry = threading.local()

    def register(self, handle):
        """Registers a file handle for the current thread. Returns self so
        that this method can be used in a with-statement.
        """
        self.registry.handle = handle
        return self

    def deregister(self):
        """Removes the current thread from the registry."""
        del self.registry.handle

    @property
    def available(self):
        """True if the thread is available in the registry."""
        return hasattr(self.registry, 'handle')

    @property
    def handle(self):
        """Gets the current handle for the thread."""
        return getattr(self.registry, 'handle', self.default)

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
