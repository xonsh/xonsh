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
from xonsh.jobs import wait_for_active_job, give_terminal_to
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
            if not isinstance(proc, slug.VirtualProcess):
                closers += [proc.stdin, proc.stdout, proc.stderr]

        # Phase 3: Post-processing
        self.outbuffer = io.BytesIO()
        if proc.stdout is None:  # If it hasn't otherwise been redirected
            # TODO: Make this a PTY if the system stdout is a TTY
            # FIXME: Bundle stderr with this if necessary
            output = slug.Pipe()
            proc.stdout = output.side_in
            if not isinstance(proc, slug.VirtualProcess):
                closers += [output.side_in]

            if False: # FIXME: When do we not stream to stdout?
                # We need it not printed and stored
                buf = output
            else:
                # We need it printed, but store it for other uses
                buf = slug.Pipe()
                slug.Tee(output.side_out, unwrap_to_binary(sys.stdout), buf.side_in.write, buf.side_in.close, keepopen=True)

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
            for proc in processes:
                pg.add(proc)
        
        self.processgroup = pg
        return self

    @property
    def procs(self):
        yield from self.processgroup

    def start(self):
        self.started = time.time()
        self.processgroup.start()
        for f in self._files_to_close:
            assert f.fileno() not in (0,1,2)
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

    @property
    def returncode(self):
        # Use the return code of the last process
        return list(self.processgroup)[-1].return_code

    def kill(self):
        """
        Forcibly quit the job
        """
        self.processgroup.kill()

    def terminate(self):
        """
        Ask the job to exit quickly, if "asking nicely" is something this
        platform understands
        """
        self.processgroup.terminate()

    def pause(self):
        """
        Pause the job, able to be continued later
        """
        self.processgroup.pause()

    def unpause(self):
        # continue is a reserved word
        """
        Continue the job after it's been paused
        """
        self.processgroup.unpause()


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
        fo = io.TextIOWrapper(buf, encoding=enc, errors=err, line_buffering=True, write_through=True)
    return fo


def unwrap_to_binary(fo):
    """
    Attempts to find the underlying binary file from the standard file-likes
    """
    if not hasattr(fo, 'mode'):
        # FIXME: Warn
        return fo
    while 'b' not in fo.mode:
        if hasattr(fo, 'buffer'):
            fo = fo.buffer
        elif hasattr(fo, 'raw'):
            fo = fo.raw
        else:
            raise ValueError("Can't unwrap {!r}".format(fo), fo)
    return fo

class XonshAlias(slug.ThreadedVirtualProcess):
    def __init__(self, func, args, *, stdin=None, stdout=None, stderr=None, job=None):
        super().__init__()
        self.func = func
        self.func_normed = partial_proxy(func)
        self.args = args
        self.cmd = args
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.job = job
        self._return_code = None

    def run(self):
        stdin = may_wrap_as_text(self.stdin)
        stdout = may_wrap_as_text(self.stdout)
        stderr = may_wrap_as_text(self.stderr)

        try:
            with STDOUT_DISPATCHER.register(stdout), \
                 STDERR_DISPATCHER.register(stderr), \
                 redirect_stdout(STDOUT_DISPATCHER), \
                 redirect_stderr(STDERR_DISPATCHER):
                r = self.func_normed(self.args[1:], stdin, stdout, stderr, self.job)
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
        self._return_code = parse_proxy_return(r, stdout, stderr)

    @property
    def return_code(self):
        return self._return_code

    @property
    def returncode(self):
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
        if self.stdin is not None:
            self.stdin.close()
        if self.stdout is not None:
            self.stdout.close()
        if self.stderr is not None:
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
        return getattr(self.registry, 'handle', None) is not None

    @property
    def handle(self):
        """Gets the current handle for the thread."""
        return getattr(self.registry, 'handle', None) or self.default

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
        """Writes to this thread's handle.
        """
        h = self.handle
        try:
            r = h.write(s)
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
