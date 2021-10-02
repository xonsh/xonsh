"""Subprocess specification and related utilities."""
import os
import io
import re
import sys
import stat
import shlex
import signal
import inspect
import pathlib
import subprocess
import contextlib

from xonsh.built_ins import XSH
import xonsh.tools as xt
import xonsh.lazyasd as xl
import xonsh.platform as xp
import xonsh.environ as xenv
import xonsh.lazyimps as xli
import xonsh.jobs as xj

from xonsh.procs.readers import ConsoleParallelReader
from xonsh.procs.posix import PopenThread
from xonsh.procs.proxies import ProcProxy, ProcProxyThread
from xonsh.procs.pipelines import (
    pause_call_resume,
    CommandPipeline,
    HiddenCommandPipeline,
    STDOUT_CAPTURE_KINDS,
)


@xl.lazyobject
def RE_SHEBANG():
    return re.compile(r"#![ \t]*(.+?)$")


def is_app_execution_alias(fname):
    """App execution aliases behave strangly on Windows and Python.
    Here we try to detect if a file is an app execution alias.
    """
    fname = pathlib.Path(fname)
    try:
        return fname.stat().st_reparse_tag == stat.IO_REPARSE_TAG_APPEXECLINK

    # os.stat().st_reparse_tag is python 3.8+, and os.stat(app_exec_alias) throws OSError for <= 3.7
    # so use old method as fallback
    except (AttributeError, OSError):
        return not os.path.exists(fname) and fname.name in os.listdir(fname.parent)


def _is_binary(fname, limit=80):
    try:
        with open(fname, "rb") as f:
            for _ in range(limit):
                char = f.read(1)
                if char == b"\0":
                    return True
                if char == b"\n":
                    return False
                if char == b"":
                    return
    except OSError as e:
        if xp.ON_WINDOWS and is_app_execution_alias(fname):
            return True
        raise e

    return False


def _un_shebang(x):
    if x == "/usr/bin/env":
        return []
    elif any(x.startswith(i) for i in ["/usr/bin", "/usr/local/bin", "/bin"]):
        x = os.path.basename(x)
    elif x.endswith("python") or x.endswith("python.exe"):
        x = "python"
    if x == "xonsh":
        return ["python", "-m", "xonsh.main"]
    return [x]


def get_script_subproc_command(fname, args):
    """Given the name of a script outside the path, returns a list representing
    an appropriate subprocess command to execute the script or None if
    the argument is not readable or not a script. Raises PermissionError
    if the script is not executable.
    """
    # make sure file is executable
    if not os.access(fname, os.X_OK):
        if not xp.ON_CYGWIN:
            raise PermissionError
        # explicitly look at all PATH entries for cmd
        w_path = os.getenv("PATH").split(":")
        w_fpath = list(map(lambda p: p + os.sep + fname, w_path))
        if not any(list(map(lambda c: os.access(c, os.X_OK), w_fpath))):
            raise PermissionError
    if xp.ON_POSIX and not os.access(fname, os.R_OK):
        # on some systems, some important programs (e.g. sudo) will have
        # execute permissions but not read/write permissions. This enables
        # things with the SUID set to be run. Needs to come before _is_binary()
        # is called, because that function tries to read the file.
        return None
    elif _is_binary(fname):
        # if the file is a binary, we should call it directly
        return None
    if xp.ON_WINDOWS:
        # Windows can execute various filetypes directly
        # as given in PATHEXT
        _, ext = os.path.splitext(fname)
        if ext.upper() in XSH.env.get("PATHEXT"):
            return [fname] + args
    # find interpreter
    with open(fname, "rb") as f:
        first_line = f.readline().decode().strip()
    m = RE_SHEBANG.match(first_line)
    # xonsh is the default interpreter
    if m is None:
        interp = ["xonsh"]
    else:
        interp = m.group(1).strip()
        if len(interp) > 0:
            interp = shlex.split(interp)
        else:
            interp = ["xonsh"]
    if xp.ON_WINDOWS:
        o = []
        for i in interp:
            o.extend(_un_shebang(i))
        interp = o
    return interp + [fname] + args


@xl.lazyobject
def _REDIR_REGEX():
    name = r"(o(?:ut)?|e(?:rr)?|a(?:ll)?|&?\d?)"
    return re.compile("{r}(>?>|<){r}$".format(r=name))


@xl.lazyobject
def _MODES():
    return {">>": "a", ">": "w", "<": "r"}


@xl.lazyobject
def _WRITE_MODES():
    return frozenset({"w", "a"})


@xl.lazyobject
def _REDIR_ALL():
    return frozenset({"&", "a", "all"})


@xl.lazyobject
def _REDIR_ERR():
    return frozenset({"2", "e", "err"})


@xl.lazyobject
def _REDIR_OUT():
    return frozenset({"", "1", "o", "out"})


@xl.lazyobject
def _E2O_MAP():
    return frozenset(
        {"{}>{}".format(e, o) for e in _REDIR_ERR for o in _REDIR_OUT if o != ""}
    )


@xl.lazyobject
def _O2E_MAP():
    return frozenset(
        {"{}>{}".format(o, e) for e in _REDIR_ERR for o in _REDIR_OUT if o != ""}
    )


def _is_redirect(x):
    return isinstance(x, str) and _REDIR_REGEX.match(x)


def safe_open(fname, mode, buffering=-1):
    """Safely attempts to open a file in for xonsh subprocs."""
    # file descriptors
    try:
        return io.open(fname, mode, buffering=buffering)
    except PermissionError:
        raise xt.XonshError(f"xonsh: {fname}: permission denied")
    except FileNotFoundError:
        raise xt.XonshError(f"xonsh: {fname}: no such file or directory")
    except Exception:
        raise xt.XonshError(f"xonsh: {fname}: unable to open file")


def safe_close(x):
    """Safely attempts to close an object."""
    if not isinstance(x, io.IOBase):
        return
    if x.closed:
        return
    try:
        x.close()
    except Exception:
        pass


def _parse_redirects(r, loc=None):
    """returns origin, mode, destination tuple"""
    orig, mode, dest = _REDIR_REGEX.match(r).groups()
    # redirect to fd
    if dest.startswith("&"):
        try:
            dest = int(dest[1:])
            if loc is None:
                loc, dest = dest, ""  # NOQA
            else:
                e = f"Unrecognized redirection command: {r}"
                raise xt.XonshError(e)
        except (ValueError, xt.XonshError):
            raise
        except Exception:
            pass
    mode = _MODES.get(mode, None)
    if mode == "r" and (len(orig) > 0 or len(dest) > 0):
        raise xt.XonshError(f"Unrecognized redirection command: {r}")
    elif mode in _WRITE_MODES and len(dest) > 0:
        raise xt.XonshError(f"Unrecognized redirection command: {r}")
    return orig, mode, dest


def _redirect_streams(r, loc=None):
    """Returns stdin, stdout, stderr tuple of redirections."""
    stdin = stdout = stderr = None
    no_ampersand = r.replace("&", "")
    # special case of redirecting stderr to stdout
    if no_ampersand in _E2O_MAP:
        stderr = subprocess.STDOUT
        return stdin, stdout, stderr
    elif no_ampersand in _O2E_MAP:
        stdout = 2  # using 2 as a flag, rather than using a file object
        return stdin, stdout, stderr
    # get streams
    orig, mode, dest = _parse_redirects(r)
    if mode == "r":
        stdin = safe_open(loc, mode)
    elif mode in _WRITE_MODES:
        if orig in _REDIR_ALL:
            stdout = stderr = safe_open(loc, mode)
        elif orig in _REDIR_OUT:
            stdout = safe_open(loc, mode)
        elif orig in _REDIR_ERR:
            stderr = safe_open(loc, mode)
        else:
            raise xt.XonshError(f"Unrecognized redirection command: {r}")
    else:
        raise xt.XonshError(f"Unrecognized redirection command: {r}")
    return stdin, stdout, stderr


def default_signal_pauser(n, f):
    """Pauses a signal, as needed."""
    signal.pause()


def no_pg_xonsh_preexec_fn():
    """Default subprocess preexec function for when there is no existing
    pipeline group.
    """
    os.setpgrp()
    signal.signal(signal.SIGTSTP, default_signal_pauser)


class SubprocSpec:
    """A container for specifying how a subprocess command should be
    executed.
    """

    kwnames = ("stdin", "stdout", "stderr", "universal_newlines", "close_fds")

    def __init__(
        self,
        cmd,
        cls=subprocess.Popen,
        stdin=None,
        stdout=None,
        stderr=None,
        universal_newlines=False,
        close_fds=False,
        captured=False,
        env=None,
    ):
        """
        Parameters
        ----------
        cmd : list of str
            Command to be run.
        cls : Popen-like
            Class to run the subprocess with.
        stdin : file-like
            Popen file descriptor or flag for stdin.
        stdout : file-like
            Popen file descriptor or flag for stdout.
        stderr : file-like
            Popen file descriptor or flag for stderr.
        universal_newlines : bool
            Whether or not to use universal newlines.
        close_fds : bool
            Whether or not to close the file descriptiors when the
            process exits.
        captured : bool or str, optional
            The flag for if the subprocess is captured, may be one of:
            False for $[], 'stdout' for $(), 'hiddenobject' for ![], or
            'object' for !().
        env : dict
            Replacement environment to run the subporcess in.

        Attributes
        ----------
        args : list of str
            Arguments as originally supplied.
        alias : list of str, callable, or None
            The alias that was resolved for this command, if any.
        binary_loc : str or None
            Path to binary to execute.
        is_proxy : bool
            Whether or not the subprocess is or should be run as a proxy.
        background : bool
            Whether or not the subprocess should be started in the background.
        threadable : bool
            Whether or not the subprocess is able to be run in a background
            thread, rather than the main thread.
        pipeline_index : int or None
            The index number of this sepc into the pipeline that is being setup.
        last_in_pipeline : bool
            Whether the subprocess is the last in the execution pipeline.
        captured_stdout : file-like
            Handle to captured stdin
        captured_stderr : file-like
            Handle to captured stderr
        stack : list of FrameInfo namedtuples or None
            The stack of the call-site of alias, if the alias requires it.
            None otherwise.
        """
        self._stdin = self._stdout = self._stderr = None
        # args
        self.cmd = list(cmd)
        self.cls = cls
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.universal_newlines = universal_newlines
        self.close_fds = close_fds
        self.captured = captured
        if env is not None:
            self.env = {
                k: v if not (isinstance(v, list)) or len(v) > 1 else v[0]
                for (k, v) in env.items()
            }
        else:
            self.env = None
        # pure attrs
        self.args = list(cmd)
        self.alias = None
        self.alias_name = None
        self.alias_stack = XSH.env.get("__ALIAS_STACK", "").split(":")
        self.binary_loc = None
        self.is_proxy = False
        self.background = False
        self.threadable = True
        self.pipeline_index = None
        self.last_in_pipeline = False
        self.captured_stdout = None
        self.captured_stderr = None
        self.stack = None

    def __str__(self):
        s = self.__class__.__name__ + "(" + str(self.cmd) + ", "
        s += self.cls.__name__ + ", "
        kws = [n + "=" + str(getattr(self, n)) for n in self.kwnames]
        s += ", ".join(kws) + ")"
        return s

    def __repr__(self):
        s = self.__class__.__name__ + "(" + repr(self.cmd) + ", "
        s += self.cls.__name__ + ", "
        kws = [n + "=" + repr(getattr(self, n)) for n in self.kwnames]
        s += ", ".join(kws) + ")"
        return s

    #
    # Properties
    #

    @property
    def stdin(self):
        return self._stdin

    @stdin.setter
    def stdin(self, value):
        if self._stdin is None:
            self._stdin = value
        elif value is None:
            pass
        else:
            safe_close(value)
            msg = "Multiple inputs for stdin for {0!r}"
            msg = msg.format(" ".join(self.args))
            raise xt.XonshError(msg)

    @property
    def stdout(self):
        return self._stdout

    @stdout.setter
    def stdout(self, value):
        if self._stdout is None:
            self._stdout = value
        elif value is None:
            pass
        else:
            safe_close(value)
            msg = "Multiple redirections for stdout for {0!r}"
            msg = msg.format(" ".join(self.args))
            raise xt.XonshError(msg)

    @property
    def stderr(self):
        return self._stderr

    @stderr.setter
    def stderr(self, value):
        if self._stderr is None:
            self._stderr = value
        elif value is None:
            pass
        else:
            safe_close(value)
            msg = "Multiple redirections for stderr for {0!r}"
            msg = msg.format(" ".join(self.args))
            raise xt.XonshError(msg)

    #
    # Execution methods
    #

    def run(self, *, pipeline_group=None):
        """Launches the subprocess and returns the object."""
        event_name = self._cmd_event_name()
        self._pre_run_event_fire(event_name)
        kwargs = {n: getattr(self, n) for n in self.kwnames}
        if callable(self.alias):
            kwargs["env"] = self.env or {}
            kwargs["env"]["__ALIAS_NAME"] = self.alias_name or ""
            p = self.cls(self.alias, self.cmd, **kwargs)
        else:
            self.prep_env_subproc(kwargs)
            self.prep_preexec_fn(kwargs, pipeline_group=pipeline_group)
            self._fix_null_cmd_bytes()
            p = self._run_binary(kwargs)
        p.spec = self
        p.last_in_pipeline = self.last_in_pipeline
        p.captured_stdout = self.captured_stdout
        p.captured_stderr = self.captured_stderr
        self._post_run_event_fire(event_name, p)
        return p

    def _run_binary(self, kwargs):
        if not self.cmd[0]:
            raise xt.XonshError("xonsh: subprocess mode: command is empty")
        bufsize = 1
        try:
            if xp.ON_WINDOWS and self.binary_loc is not None:
                # launch process using full paths (https://bugs.python.org/issue8557)
                cmd = [self.binary_loc] + self.cmd[1:]
            else:
                cmd = self.cmd
            p = self.cls(cmd, bufsize=bufsize, **kwargs)
        except PermissionError:
            e = "xonsh: subprocess mode: permission denied: {0}"
            raise xt.XonshError(e.format(self.cmd[0]))
        except FileNotFoundError:
            cmd0 = self.cmd[0]
            if len(self.cmd) == 1 and cmd0.endswith("?"):
                with contextlib.suppress(OSError):
                    return self.cls(
                        ["man", cmd0.rstrip("?")], bufsize=bufsize, **kwargs
                    )
            e = "xonsh: subprocess mode: command not found: {0}".format(cmd0)
            env = XSH.env
            sug = xt.suggest_commands(cmd0, env)
            if len(sug.strip()) > 0:
                e += "\n" + xt.suggest_commands(cmd0, env)
            raise xt.XonshError(e)
        return p

    def prep_env_subproc(self, kwargs):
        """Prepares the environment to use in the subprocess."""
        with XSH.env.swap(self.env) as env:
            denv = env.detype()
        if xp.ON_WINDOWS:
            # Over write prompt variable as xonsh's $PROMPT does
            # not make much sense for other subprocs
            denv["PROMPT"] = "$P$G"
        kwargs["env"] = denv

    def prep_preexec_fn(self, kwargs, pipeline_group=None):
        """Prepares the 'preexec_fn' keyword argument"""
        if not xp.ON_POSIX:
            return
        if not XSH.env.get("XONSH_INTERACTIVE"):
            return
        if pipeline_group is None or xp.ON_WSL1:
            # If there is no pipeline group
            # or the platform is windows subsystem for linux (WSL)
            xonsh_preexec_fn = no_pg_xonsh_preexec_fn
        else:

            def xonsh_preexec_fn():
                """Preexec function bound to a pipeline group."""
                os.setpgid(0, pipeline_group)
                signal.signal(
                    signal.SIGTERM if xp.ON_WINDOWS else signal.SIGTSTP,
                    default_signal_pauser,
                )

        kwargs["preexec_fn"] = xonsh_preexec_fn

    def _fix_null_cmd_bytes(self):
        # Popen does not accept null bytes in its input commands.
        # That doesn't stop some subprocesses from using them. Here we
        # escape them just in case.
        cmd = self.cmd
        for i in range(len(cmd)):
            if callable(cmd[i]):
                raise Exception(f"The command contains callable argument: {cmd[i]}")
            cmd[i] = cmd[i].replace("\0", "\\0")

    def _cmd_event_name(self):
        if callable(self.alias):
            return getattr(self.alias, "__name__", repr(self.alias))
        elif self.binary_loc is None:
            return "<not-found>"
        else:
            return os.path.basename(self.binary_loc)

    def _pre_run_event_fire(self, name):
        events = XSH.builtins.events
        event_name = "on_pre_spec_run_" + name
        if events.exists(event_name):
            event = getattr(events, event_name)
            event.fire(spec=self)

    def _post_run_event_fire(self, name, proc):
        events = XSH.builtins.events
        event_name = "on_post_spec_run_" + name
        if events.exists(event_name):
            event = getattr(events, event_name)
            event.fire(spec=self, proc=proc)

    #
    # Building methods
    #

    @classmethod
    def build(kls, cmd, *, cls=subprocess.Popen, **kwargs):
        """Creates an instance of the subprocess command, with any
        modifications and adjustments based on the actual cmd that
        was received.
        """
        if not cmd:
            raise xt.XonshError("xonsh: subprocess mode: command is empty")
        # modifications that do not alter cmds may come before creating instance
        spec = kls(cmd, cls=cls, **kwargs)
        # modifications that alter cmds must come after creating instance
        # perform initial redirects
        spec.redirect_leading()
        spec.redirect_trailing()
        # apply aliases
        spec.resolve_alias()
        spec.resolve_binary_loc()
        spec.resolve_auto_cd()
        spec.resolve_executable_commands()
        spec.resolve_alias_cls()
        spec.resolve_stack()
        return spec

    def redirect_leading(self):
        """Manage leading redirects such as with '< input.txt COMMAND'."""
        while len(self.cmd) >= 3 and self.cmd[0] == "<":
            self.stdin = safe_open(self.cmd[1], "r")
            self.cmd = self.cmd[2:]

    def redirect_trailing(self):
        """Manages trailing redirects."""
        while True:
            cmd = self.cmd
            if len(cmd) >= 3 and _is_redirect(cmd[-2]):
                streams = _redirect_streams(cmd[-2], cmd[-1])
                self.stdin, self.stdout, self.stderr = streams
                self.cmd = cmd[:-2]
            elif len(cmd) >= 2 and _is_redirect(cmd[-1]):
                streams = _redirect_streams(cmd[-1])
                self.stdin, self.stdout, self.stderr = streams
                self.cmd = cmd[:-1]
            else:
                break

    def resolve_alias(self):
        """Sets alias in command, if applicable."""
        cmd0 = self.cmd[0]

        if cmd0 in self.alias_stack:
            # Disabling the alias resolving to prevent infinite loop in call stack
            # and futher using binary_loc to resolve the alias name.
            self.alias = None
            return

        if callable(cmd0):
            alias = cmd0
        else:
            alias = XSH.aliases.get(cmd0, None)
            if alias is not None:
                self.alias_name = cmd0
        self.alias = alias

    def resolve_binary_loc(self):
        """Sets the binary location"""
        alias = self.alias
        if alias is None:
            cmd0 = self.cmd[0]
            binary_loc = xenv.locate_binary(cmd0)
            if binary_loc == cmd0 and cmd0 in self.alias_stack:
                raise Exception(f'Recursive calls to "{cmd0}" alias.')
        elif callable(alias):
            binary_loc = None
        else:
            binary_loc = xenv.locate_binary(alias[0])
        self.binary_loc = binary_loc

    def resolve_auto_cd(self):
        """Implements AUTO_CD functionality."""
        if not (
            self.alias is None
            and self.binary_loc is None
            and len(self.cmd) == 1
            and XSH.env.get("AUTO_CD")
            and os.path.isdir(self.cmd[0])
        ):
            return
        self.cmd.insert(0, "cd")
        self.alias = XSH.aliases.get("cd", None)

    def resolve_executable_commands(self):
        """Resolve command executables, if applicable."""
        alias = self.alias
        if alias is None:
            pass
        elif callable(alias):
            self.cmd.pop(0)
            return
        else:
            self.cmd = alias + self.cmd[1:]
            # resolve any redirects the aliases may have applied
            self.redirect_leading()
            self.redirect_trailing()
        if self.binary_loc is None:
            return
        try:
            scriptcmd = get_script_subproc_command(self.binary_loc, self.cmd[1:])
            if scriptcmd is not None:
                self.cmd = scriptcmd
        except PermissionError:
            e = "xonsh: subprocess mode: permission denied: {0}"
            raise xt.XonshError(e.format(self.cmd[0]))

    def resolve_alias_cls(self):
        """Determine which proxy class to run an alias with."""
        alias = self.alias
        if not callable(alias):
            return
        self.is_proxy = True
        env = XSH.env
        thable = env.get("THREAD_SUBPROCS") and getattr(
            alias, "__xonsh_threadable__", True
        )
        cls = ProcProxyThread if thable else ProcProxy
        self.cls = cls
        self.threadable = thable
        # also check capturability, while we are here
        cpable = getattr(alias, "__xonsh_capturable__", self.captured)
        self.captured = cpable

    def resolve_stack(self):
        """Computes the stack for a callable alias's call-site, if needed."""
        if not callable(self.alias):
            return
        # check that we actual need the stack
        sig = inspect.signature(self.alias)
        if len(sig.parameters) <= 5 and "stack" not in sig.parameters:
            return
        # compute the stack, and filter out these build methods
        # run_subproc() is the 4th command in the stack
        # we want to filter out one up, e.g. subproc_captured_hiddenobject()
        # after that the stack from the call site starts.
        stack = inspect.stack(context=0)
        assert stack[3][3] == "run_subproc", "xonsh stack has changed!"
        del stack[:5]
        self.stack = stack


def _safe_pipe_properties(fd, use_tty=False):
    """Makes sure that a pipe file descriptor properties are sane."""
    if not use_tty:
        return
    # due to some weird, long standing issue in Python, PTYs come out
    # replacing newline \n with \r\n. This causes issues for raw unix
    # protocols, like git and ssh, which expect unix line endings.
    # see https://mail.python.org/pipermail/python-list/2013-June/650460.html
    # for more details and the following solution.
    props = xli.termios.tcgetattr(fd)
    props[1] = props[1] & (~xli.termios.ONLCR) | xli.termios.ONLRET
    xli.termios.tcsetattr(fd, xli.termios.TCSANOW, props)
    # newly created PTYs have a stardard size (24x80), set size to the same size
    # than the current terminal
    winsize = None
    if sys.stdin.isatty():
        winsize = xli.fcntl.ioctl(sys.stdin.fileno(), xli.termios.TIOCGWINSZ, b"0000")
    elif sys.stdout.isatty():
        winsize = xli.fcntl.ioctl(sys.stdout.fileno(), xli.termios.TIOCGWINSZ, b"0000")
    elif sys.stderr.isatty():
        winsize = xli.fcntl.ioctl(sys.stderr.fileno(), xli.termios.TIOCGWINSZ, b"0000")
    if winsize is not None:
        xli.fcntl.ioctl(fd, xli.termios.TIOCSWINSZ, winsize)


def _update_last_spec(last):
    env = XSH.env
    captured = last.captured
    last.last_in_pipeline = True
    if not captured:
        return
    callable_alias = callable(last.alias)
    if callable_alias:
        pass
    else:
        cmds_cache = XSH.commands_cache
        thable = (
            env.get("THREAD_SUBPROCS")
            and (captured != "hiddenobject" or env.get("XONSH_CAPTURE_ALWAYS"))
            and cmds_cache.predict_threadable(last.args)
            and cmds_cache.predict_threadable(last.cmd)
        )
        if captured and thable:
            last.cls = PopenThread
        elif not thable:
            # foreground processes should use Popen
            last.threadable = False
            if captured == "object" or captured == "hiddenobject":
                # CommandPipeline objects should not pipe stdout, stderr
                return
    # cannot used PTY pipes for aliases, for some dark reason,
    # and must use normal pipes instead.
    use_tty = xp.ON_POSIX and not callable_alias
    # Do not set standard in! Popen is not a fan of redirections here
    # set standard out
    if last.stdout is not None:
        last.universal_newlines = True
    elif captured in STDOUT_CAPTURE_KINDS:
        last.universal_newlines = False
        r, w = os.pipe()
        last.stdout = safe_open(w, "wb")
        last.captured_stdout = safe_open(r, "rb")
    elif XSH.stdout_uncaptured is not None:
        last.universal_newlines = True
        last.stdout = XSH.stdout_uncaptured
        last.captured_stdout = last.stdout
    elif xp.ON_WINDOWS and not callable_alias:
        last.universal_newlines = True
        last.stdout = None  # must truly stream on windows
        last.captured_stdout = ConsoleParallelReader(1)
    else:
        last.universal_newlines = True
        r, w = xli.pty.openpty() if use_tty else os.pipe()
        _safe_pipe_properties(w, use_tty=use_tty)
        last.stdout = safe_open(w, "w")
        _safe_pipe_properties(r, use_tty=use_tty)
        last.captured_stdout = safe_open(r, "r")
    # set standard error
    if last.stderr is not None:
        pass
    elif captured == "stdout":
        pass
    elif captured == "object":
        r, w = os.pipe()
        last.stderr = safe_open(w, "w")
        last.captured_stderr = safe_open(r, "r")
    elif XSH.stderr_uncaptured is not None:
        last.stderr = XSH.stderr_uncaptured
        last.captured_stderr = last.stderr
    elif xp.ON_WINDOWS and not callable_alias:
        last.universal_newlines = True
        last.stderr = None  # must truly stream on windows
    else:
        r, w = xli.pty.openpty() if use_tty else os.pipe()
        _safe_pipe_properties(w, use_tty=use_tty)
        last.stderr = safe_open(w, "w")
        _safe_pipe_properties(r, use_tty=use_tty)
        last.captured_stderr = safe_open(r, "r")
    # redirect stdout to stderr, if we should
    if isinstance(last.stdout, int) and last.stdout == 2:
        # need to use private interface to avoid duplication.
        last._stdout = last.stderr
    # redirect stderr to stdout, if we should
    if callable_alias and last.stderr == subprocess.STDOUT:
        last._stderr = last.stdout
        last.captured_stderr = last.captured_stdout


def cmds_to_specs(cmds, captured=False, envs=None):
    """Converts a list of cmds to a list of SubprocSpec objects that are
    ready to be executed.
    """
    # first build the subprocs independently and separate from the redirects
    i = 0
    specs = []
    redirects = []
    for i, cmd in enumerate(cmds):
        if isinstance(cmd, str):
            redirects.append(cmd)
        else:
            env = envs[i] if envs is not None else None
            spec = SubprocSpec.build(cmd, captured=captured, env=env)
            spec.pipeline_index = i
            specs.append(spec)
            i += 1
    # now modify the subprocs based on the redirects.
    for i, redirect in enumerate(redirects):
        if redirect == "|":
            # these should remain integer file descriptors, and not Python
            # file objects since they connect processes.
            r, w = os.pipe()
            specs[i].stdout = w
            specs[i + 1].stdin = r
        elif redirect == "&" and i == len(redirects) - 1:
            specs[i].background = True
        else:
            raise xt.XonshError(f"unrecognized redirect {redirect!r}")

    # Apply boundary conditions
    if not XSH.env.get("XONSH_CAPTURE_ALWAYS"):
        # Make sure sub-specs are always captured.
        # I.e. ![some_alias | grep x] $(some_alias)
        specs_to_capture = specs if captured in STDOUT_CAPTURE_KINDS else specs[:-1]
        for spec in specs_to_capture:
            if spec.env is None:
                spec.env = {"XONSH_CAPTURE_ALWAYS": True}
            else:
                spec.env.setdefault("XONSH_CAPTURE_ALWAYS", True)

    _update_last_spec(specs[-1])
    return specs


def _should_set_title(captured=False):
    env = XSH.env
    return (
        env.get("XONSH_INTERACTIVE")
        and not env.get("XONSH_STORE_STDOUT")
        and captured not in STDOUT_CAPTURE_KINDS
        and XSH.shell is not None
    )


def run_subproc(cmds, captured=False, envs=None):
    """Runs a subprocess, in its many forms. This takes a list of 'commands,'
    which may be a list of command line arguments or a string, representing
    a special connecting character.  For example::

        $ ls | grep wakka

    is represented by the following cmds::

        [['ls'], '|', ['grep', 'wakka']]

    Lastly, the captured argument affects only the last real command.
    """
    if XSH.env.get("XONSH_TRACE_SUBPROC", False):
        tracer = XSH.env.get("XONSH_TRACE_SUBPROC_FUNC")
        if callable(tracer):
            tracer(cmds, captured=captured)
        else:
            print(f"TRACE SUBPROC: {cmds}, captured={captured}", file=sys.stderr)

    specs = cmds_to_specs(cmds, captured=captured, envs=envs)
    captured = specs[-1].captured
    if captured == "hiddenobject":
        command = HiddenCommandPipeline(specs)
    else:
        command = CommandPipeline(specs)
    proc = command.proc
    background = command.spec.background
    if not all(x.is_proxy for x in specs):
        xj.add_job(
            {
                "cmds": cmds,
                "pids": [i.pid for i in command.procs],
                "obj": proc,
                "bg": background,
                "pipeline": command,
                "pgrp": command.term_pgid,
            }
        )
    if _should_set_title(captured=captured):
        # set title here to get currently executing command
        pause_call_resume(proc, XSH.shell.settitle)
    else:
        # for some reason, some programs are in a stopped state when the flow
        # reaches this point, hence a SIGCONT should be sent to `proc` to make
        # sure that the shell doesn't hang. This `pause_call_resume` invocation
        # does this
        pause_call_resume(proc, int)
    # now figure out what we should return
    if captured == "object":
        return command  # object can be returned even if backgrounding
    elif background:
        return
    elif captured == "stdout":
        command.end()
        return command.output
    elif captured == "hiddenobject":
        command.end()
        return command
    else:
        command.end()
        return
