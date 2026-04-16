"""Subprocess specification and related utilities."""

import contextlib
import inspect
import io
import os
import pathlib
import re
import shlex
import signal
import stat
import subprocess
import sys

import xonsh.lib.lazyasd as xl
import xonsh.lib.lazyimps as xli
import xonsh.platform as xp
import xonsh.procs.jobs as xj
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.procs.executables import (
    get_possible_names,
    is_file,
    locate_executable,
)
from xonsh.procs.pipelines import (
    STDOUT_CAPTURE_KINDS,
    CommandPipeline,
    HiddenCommandPipeline,
    resume_process,
)
from xonsh.procs.pipes import PipeChannel
from xonsh.procs.posix import PopenThread
from xonsh.procs.proxies import ProcProxy, ProcProxyThread
from xonsh.procs.readers import ConsoleParallelReader


def _has_path_component(name):
    """Check if a command name contains any path component (directory separator).

    Commands with path separators (like ``./script``, ``subdir/script``,
    or absolute paths) are explicit path references and may be resolved
    relative to CWD.  Bare names (like ``ls`` or ``script.xsh``) must be
    found in ``$PATH`` only — matching Linux/POSIX behaviour where CWD is
    never searched implicitly.
    """
    return os.sep in name or (os.sep != "/" and "/" in name)


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
                    return False
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
        return [sys.executable, "-m", "xonsh"]
    return [x]


def parse_shebang_from_file(filepath):
    """Returns shebang for a file or None.
    Doc: https://www.gnu.org/software/guile/manual/html_node/The-Meta-Switch.html
    """
    shebang_parts = []
    with open(filepath, "rb") as f:
        for i, line in enumerate(f):
            line = line.decode("utf-8", errors="replace").strip()
            if i == 0:
                if not line.startswith("#!"):
                    return ""
            shebang_parts.append(line.rstrip("\\").strip())
            if not line.endswith("\\"):
                break
    return " ".join(shebang_parts)


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
        w_path = os.getenv("PATH", "").split(os.pathsep)
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
        _, ext = os.path.splitext(fname)
        ext_upper = ext.upper()
        # 1) .xsh / .py / .pyw — run with the current xonsh interpreter
        #    (xonsh compiles .py as pure Python and .xsh as xonsh code
        #    via codecache, matching the Linux behaviour)
        if ext_upper in {".XSH", ".PY", ".PYW"}:
            return [sys.executable, "-m", "xonsh", fname] + args
        # 3) Other PATHEXT extensions — delegate to OS file associations
        if ext_upper in {e.upper() for e in XSH.env.get("PATHEXT", [])}:
            return ["cmd", "/c", fname] + args
        # 4) Try shebang for any other text file
        shebang = parse_shebang_from_file(fname)
        m = RE_SHEBANG.match(shebang)
        if m is not None:
            interp = shlex.split(m.group(1).strip())
            o = []
            for i in interp:
                o.extend(_un_shebang(i))
            return o + [fname] + args
        # 5) Unknown file type — no recognised extension, no shebang
        return None
    # --- POSIX path (unchanged) ---
    shebang = parse_shebang_from_file(fname)
    m = RE_SHEBANG.match(shebang)
    # xonsh is the default interpreter
    if m is None:
        interp = ["xonsh"]
    else:
        interp = m.group(1).strip()
        if len(interp) > 0:
            interp = shlex.split(interp)
        else:
            interp = ["xonsh"]
    return interp + [fname] + args


@xl.lazyobject
def _REDIR_REGEX():
    name = r"(o(?:ut)?|e(?:rr)?|a(?:ll)?|&?\d?)"
    return re.compile(f"{name}(>?>|<){name}$")


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
    return frozenset({f"{e}>{o}" for e in _REDIR_ERR for o in _REDIR_OUT if o != ""})


@xl.lazyobject
def _O2E_MAP():
    return frozenset({f"{o}>{e}" for e in _REDIR_ERR for o in _REDIR_OUT if o != ""})


@xl.lazyobject
def _A2P_MAP():
    # `a>p` and variants: merge stdout+stderr into the following pipe.
    # `&` is excluded here: `&>p` would conflict with the background-process
    # parsing of `&` in subproc redirects.
    return frozenset({f"{a}>p" for a in _REDIR_ALL if a != "&"})


@xl.lazyobject
def _E2P_MAP():
    # `e>p` and variants: route stderr into the following pipe
    return frozenset({f"{e}>p" for e in _REDIR_ERR})


class _PipeRedirectSentinel:
    """Marker put in a spec's stdout/stderr slot by ``_redirect_streams``
    when the command uses ``a>p`` or ``e>p``. It is replaced by the pipe's
    write fd later in ``cmds_to_specs``; if it survives to execution, the
    redirect was used without a subsequent ``|`` pipe.
    """

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<pipe-redirect {self.name}>"


_PIPE_ALL = _PipeRedirectSentinel("a>p")
_PIPE_ERR = _PipeRedirectSentinel("e>p")


def safe_open(fname, mode, buffering=-1):
    """Safely attempts to open a file in for xonsh subprocs."""
    # file descriptors
    try:
        kwargs = {"encoding": "utf-8"} if "b" not in mode else {}
        return open(fname, mode, buffering=buffering, **kwargs)
    except PermissionError as ex:
        raise xt.XonshError(f"xonsh: {fname}: permission denied") from ex
    except FileNotFoundError as ex:
        raise xt.XonshError(f"xonsh: {fname}: no such file or directory") from ex
    except Exception as ex:
        raise xt.XonshError(f"xonsh: {fname}: unable to open file") from ex


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
    if isinstance(loc, list):
        raise Exception(f"Unsupported redirect: {r!r} {loc!r}")

    stdin = stdout = stderr = None
    # pipe redirects: a>p merges both streams into the following pipe,
    # e>p routes stderr into the following pipe (stdout left alone).
    if r in _A2P_MAP:
        return stdin, _PIPE_ALL, subprocess.STDOUT
    elif r in _E2P_MAP:
        return stdin, stdout, _PIPE_ERR
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


def _flatten_cmd_redirects(cmd):
    """Transforms a command like ['ls', ('>', '/dev/null')] into ['ls', '>', '/dev/null']."""
    new_cmd = []
    for c in cmd:
        if isinstance(c, tuple):
            new_cmd.extend(c)
        else:
            new_cmd.append(c)
    return new_cmd


def default_signal_pauser(n, f):
    """Pauses a signal, as needed."""
    signal.pause()


def no_pg_xonsh_preexec_fn():
    """Default subprocess preexec function for when there is no existing
    pipeline group.
    """
    os.setpgrp()
    signal.signal(signal.SIGTSTP, default_signal_pauser)


class DecoratorAlias:
    """Decorator alias base class."""

    descr = "DecoratorAlias base."

    def __call__(
        self,
        args,
        stdin=None,
        stdout=None,
        stderr=None,
        spec=None,
        stack=None,
        **kwargs,
    ):
        print(self.descr, file=stdout)

    def decorate_spec(self, spec):
        """Modify spec immediately after modifier added."""
        pass

    def decorate_spec_pre_run(self, pipeline, spec, spec_num):
        """Modify spec before run."""
        pass


class SpecAttrDecoratorAlias(DecoratorAlias):
    """Decorator Alias for spec attributes."""

    def __init__(self, set_attributes: dict, descr=""):
        self.set_attributes = set_attributes
        self.descr = descr
        self.__doc__ = descr
        super().__init__()

    def decorate_spec(self, spec):
        for a, v in self.set_attributes.items():
            setattr(spec, a, v)


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
            Whether or not to close the file descriptors when the
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
        self.args = _flatten_cmd_redirects(cmd)
        self.alias = None
        self.alias_name = None
        self.alias_stack = XSH.env.get("__ALIAS_STACK", "").split(":")
        self.binary_loc = None
        self.is_proxy = False
        self.background = False
        self.threadable = True
        self.force_threadable = None  # Set this value to ignore threadable prediction.
        self.pipeline_index = None
        self.last_in_pipeline = False
        self.captured_stdout = None
        self.captured_stderr = None
        self.stack = None
        self.decorators = []  # List of DecoratorAlias objects that applied to spec.
        self.pipe_channels = []  # PipeChannel objects owned by this spec
        self.output_format = XSH.env.get("XONSH_SUBPROC_OUTPUT_FORMAT", "stream_lines")
        self.raise_subproc_error = None  # Spec-based $XONSH_SUBPROC_CMD_RAISE_ERROR.
        # True when this pipeline is a direct operand of an `&&`/`||` chain
        # (set by `cmds_to_specs` from the parser-injected `in_boolop` kwarg).
        self.in_boolop = False

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
            msg = msg.format(self.get_command_str())
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
            msg = msg.format(self.get_command_str())
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
            msg = msg.format(self.get_command_str())
            raise xt.XonshError(msg)

    def get_command_str(self):
        return " ".join(arg for arg in self.args)

    def close(self):
        """Release any pipe wrappers and channels held by this spec.

        Required when a spec is created via ``cmds_to_specs`` but never
        executed (no ``CommandPipeline._close_proc`` is invoked). The
        wrappers from ``PipeChannel.open_writer/open_reader`` use
        ``closefd=False``, so leaving them for GC produces a
        ``ResourceWarning: unclosed file`` on Python 3.12+. Idempotent.
        """
        safe_close(self._stdin)
        safe_close(self._stdout)
        safe_close(self._stderr)
        safe_close(self.captured_stdout)
        safe_close(self.captured_stderr)
        for ch in self.pipe_channels:
            ch.close()
        self.pipe_channels.clear()

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
            # On Windows, CreateProcess searches the current directory for
            # executables before PATH.  Block that for bare command names
            # (no directory separator) so the behaviour matches POSIX shells
            # where CWD is never searched implicitly.
            if xp.ON_WINDOWS and self.binary_loc is None:
                cmd0 = cmd[0]
                if cmd0 and not _has_path_component(cmd0):
                    if any(is_file(n) for n in get_possible_names(cmd0)):
                        raise FileNotFoundError(cmd0)
            p = self.cls(cmd, bufsize=bufsize, **kwargs)
        except PermissionError as ex:
            e = "xonsh: subprocess mode: permission denied: {0}"
            raise xt.XonshError(e.format(self.cmd[0])) from ex
        except FileNotFoundError as ex:
            cmd0 = self.cmd[0]
            if len(self.cmd) == 1 and cmd0.endswith("?"):
                superhelp = cmd0.endswith("??")
                cmdq = cmd0[:-2] if superhelp else cmd0[:-1]
                if cmdq in XSH.aliases:
                    from xonsh.aliases import print_alias_help

                    print_alias_help(cmdq, superhelp=superhelp)
                    return self.cls(["true"], bufsize=bufsize, **kwargs)
                else:
                    resolved = locate_executable(cmdq)
                    label = "{YELLOW}Resolved " + cmdq + ":{RESET} " + repr(resolved)
                    if not superhelp or resolved is None:
                        xt.print_color(label)
                        return self.cls(["true"], bufsize=bufsize, **kwargs)
                    xt.print_color(label)
                    xt.print_color("{YELLOW}Running man " + cmdq + "{RESET}")
                    with contextlib.suppress(OSError):
                        return self.cls(["man", cmdq], bufsize=bufsize, **kwargs)
            e = f"xonsh: subprocess mode: command not found: {repr(cmd0)}"
            env = XSH.env
            sug = xt.suggest_commands(cmd0, env)
            if len(sug.strip()) > 0:
                e += "\n" + sug
            if XSH.env.get("XONSH_INTERACTIVE"):
                events = XSH.builtins.events
                replacements = events.on_command_not_found.fire(cmd=self.cmd)
                for replacement in replacements:
                    if replacement is None:
                        continue
                    # Accept dict with "cmd" and optional "env" keys
                    # (same convention as @Aliases.return_command).
                    replacement_env = None
                    if isinstance(replacement, dict):
                        replacement_env = replacement.get("env")
                        replacement = replacement.get("cmd")
                    # Validate replacement format (accept list or tuple)
                    if not isinstance(replacement, (list, tuple)) or not replacement:
                        continue
                    try:
                        kw = {**kwargs}
                        if replacement_env is not None:
                            base = kw.get("env") or {}
                            kw["env"] = {
                                **base,
                                **{str(k): str(v) for k, v in replacement_env.items()},
                            }
                        return self.cls(list(replacement), bufsize=bufsize, **kw)
                    except (FileNotFoundError, PermissionError):
                        # If replacement also fails, continue to next replacement
                        # or fall through to original error with suggestions
                        continue
            raise xt.XonshError(e) from ex
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
        if events.exists("on_pre_spec_run"):
            event = events.on_pre_spec_run
            event.fire(spec=self)

    def _post_run_event_fire(self, name, proc):
        events = XSH.builtins.events
        event_name = "on_post_spec_run_" + name
        if events.exists(event_name):
            event = getattr(events, event_name)
            event.fire(spec=self, proc=proc)
        if events.exists("on_post_spec_run"):
            event = events.on_post_spec_run
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
        spec.resolve_decorators()  # keep this first
        spec.resolve_args_list()
        spec.resolve_redirects()
        spec.resolve_alias()
        spec.resolve_binary_loc()
        spec.resolve_auto_cd()
        spec.resolve_executable_commands()
        spec.resolve_alias_cls()
        spec.resolve_stack()
        return spec

    def add_decorator(self, mod: DecoratorAlias):
        """Add spec modifier to the specification."""
        mod.decorate_spec(self)
        self.decorators.append(mod)

    def resolve_decorators(self):
        """Apply decorators."""
        if (ln := len(self.cmd)) == 1:
            return
        for i in range(ln):
            c = self.cmd[i]
            if c in XSH.aliases and isinstance(mod := XSH.aliases[c], DecoratorAlias):
                self.add_decorator(mod)
            else:
                break
        self.cmd = self.cmd[i:]

    def resolve_args_list(self):
        """Weave a list of arguments into a command."""
        resolved_cmd = []
        for c in self.cmd:
            if (
                isinstance(c, tuple)
                and len(c) == 2
                and isinstance(c[1], list)
                and len(c[1]) == 1
            ):
                # Redirect case e.g. `> file`
                resolved_cmd.append(
                    (
                        c[0],
                        c[1][0],
                    )
                )
            else:
                resolved_cmd += c if isinstance(c, list) else [c]
        self.cmd = resolved_cmd

    def resolve_redirects(self):
        """Manages redirects."""
        new_cmd = []
        redirects = []
        for c in self.cmd:
            if isinstance(c, tuple):
                redirects.append(c)
            else:
                new_cmd.append(c)
        if not new_cmd:
            raise xt.XonshError("xonsh: subprocess mode: command is empty")
        self.cmd = new_cmd
        for r in redirects:
            streams = _redirect_streams(*r)
            self.stdin, self.stdout, self.stderr = streams

    def resolve_alias(self):
        """Resolving alias and setting up command."""
        cmd0 = self.cmd[0]
        if cmd0 in self.alias_stack:
            # Disabling the alias resolving to prevent infinite loop in call stack
            # and further using binary_loc to resolve the alias name.
            self.alias = None
            return

        if callable(cmd0):
            self.alias = cmd0
        else:
            decorators = []
            alias = XSH.aliases.get(
                self.cmd,
                None,
                decorators=decorators,
            )
            if alias is not None:
                self.alias_name = cmd0
                # Apply local_env from return_command aliases
                if hasattr(alias, "local_env") and alias.local_env:
                    self.env = (self.env or {}) | alias.local_env
                if callable(alias[0]):
                    # E.g. `alias == [FuncAlias({'name': 'cd'}), '/tmp']`
                    self.alias = alias[0]
                    self.cmd = [cmd0] + alias[1:]
                else:
                    # E.g. `alias == ['ls', '-la']`
                    self.alias = alias

            for mod in decorators:
                self.add_decorator(mod)

    def resolve_binary_loc(self):
        """Sets the binary location"""
        alias = self.alias
        if alias is None:
            cmd0 = self.cmd[0]
            binary_loc = locate_executable(cmd0)
            if binary_loc is None and cmd0 and cmd0 in self.alias_stack:
                raise Exception(f'Recursive calls to "{cmd0}" alias.')
        elif callable(alias):
            binary_loc = None
        else:
            binary_loc = locate_executable(alias[0])
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
        cd_alias = XSH.aliases.get("cd")
        self.alias = cd_alias[0] if cd_alias else None

    def resolve_executable_commands(self):
        """Resolve command executables, if applicable."""
        alias = self.alias
        if alias is None:
            pass
        elif callable(alias):
            self.cmd.pop(0)
            return
        else:
            self.cmd = alias
            self.resolve_redirects()
        # Determine the file to inspect for script detection.
        # binary_loc may be None on Windows for files whose extension is not
        # in PATHEXT (e.g. .xsh), even though the file exists and is a script.
        # Only allow CWD-relative lookup when the command has an explicit path
        # component (e.g. ./script.xsh, subdir/script, or an absolute path).
        # Bare names like "script.xsh" must come from $PATH, not CWD — this
        # matches POSIX shell behaviour and avoids accidental execution of
        # files that happen to sit in the current directory.
        fname = self.binary_loc
        if fname is None:
            cmd0 = self.cmd[0] if self.cmd else None
            if cmd0 and _has_path_component(cmd0) and os.path.isfile(cmd0):
                fname = os.path.abspath(cmd0)
        if fname is None:
            return
        try:
            scriptcmd = get_script_subproc_command(fname, self.cmd[1:])
            if scriptcmd is not None:
                self.cmd = scriptcmd
                # Update binary_loc to the interpreter, not the script.
                # Otherwise _run_binary() (PR #4077) would launch the script
                # directly via CreateProcess, causing WinError 193 on Windows.
                self.binary_loc = locate_executable(scriptcmd[0])
            elif xp.ON_WINDOWS and not _is_binary(fname):
                # get_script_subproc_command returned None for a non-binary
                # file — it has no recognised extension and no shebang.
                # (None for a binary is normal — it runs via CreateProcess.)
                _, ext = os.path.splitext(fname)
                raise xt.XonshError(
                    f"xonsh: {self.cmd[0]}: unknown file type {ext!r} — "
                    f"not in $PATHEXT."
                )
        except PermissionError as ex:
            e = "xonsh: subprocess mode: permission denied: {0}"
            raise xt.XonshError(e.format(self.cmd[0])) from ex

    def resolve_alias_cls(self):
        """Determine which proxy class to run an alias with."""
        if callable(self.alias):
            self.is_proxy = True
            _update_proc_alias_threadable(self)
            _update_proc_alias_captured(self)

    def resolve_stack(self):
        """Computes the stack for a callable alias's call-site, if needed."""
        if not callable(self.alias):
            return
        # check that we actual need the stack
        sig = inspect.signature(getattr(self.alias, "func", self.alias))
        if len(sig.parameters) <= 5 and "stack" not in sig.parameters:
            return
        # compute the stack, and filter out these build methods
        # run_subproc() is the 4th command in the stack
        # we want to filter out one up, e.g. subproc_captured_hiddenobject()
        # after that the stack from the call site starts.
        stack = inspect.stack(context=0)
        if not stack[3][3].startswith("test_"):
            assert stack[3][3] == "run_subproc", "xonsh stack has changed!"
        del stack[:5]
        self.stack = stack


def _safe_pipe_properties(fd, use_tty=False):
    """Makes sure that a pipe file descriptor properties are reasonable."""
    if not use_tty:
        return
    # due to some weird, long standing issue in Python, PTYs come out
    # replacing newline \n with \r\n. This causes issues for raw unix
    # protocols, like git and ssh, which expect unix line endings.
    # see https://mail.python.org/pipermail/python-list/2013-June/650460.html
    # for more details and the following solution.
    try:
        props = xli.termios.tcgetattr(fd)
    except xli.termios.error:
        # fd is not a TTY (e.g. PTY exhaustion caused fallback to os.pipe)
        return
    props[1] = props[1] & (~xli.termios.ONLCR) | xli.termios.ONLRET
    xli.termios.tcsetattr(fd, xli.termios.TCSANOW, props)
    # newly created PTYs have a stardard size (24x80), set size to the same size
    # than the current terminal
    winsize = None
    if sys.stdin.isatty():
        winsize = xli.fcntl.ioctl(
            sys.stdin.fileno(), xli.termios.TIOCGWINSZ, b"00000000"
        )
    elif sys.stdout.isatty():
        winsize = xli.fcntl.ioctl(
            sys.stdout.fileno(), xli.termios.TIOCGWINSZ, b"00000000"
        )
    elif sys.stderr.isatty():
        winsize = xli.fcntl.ioctl(
            sys.stderr.fileno(), xli.termios.TIOCGWINSZ, b"00000000"
        )
    if winsize is not None:
        xli.fcntl.ioctl(fd, xli.termios.TIOCSWINSZ, winsize)


def _update_last_spec(last):
    last.last_in_pipeline = True

    if not last.captured:
        return

    _last_spec_update_threading(last)
    _last_spec_update_captured(last)


def _last_spec_update_threading(last: SubprocSpec):
    if callable(last.alias):
        return

    captured, env, cmds_cache = last.captured, XSH.env, XSH.commands_cache
    threadable = (
        captured
        and env.get("THREAD_SUBPROCS")
        and (captured != "hiddenobject" or env.get("XONSH_CAPTURE_ALWAYS"))
        and cmds_cache.predict_threadable(last.args)
        and cmds_cache.predict_threadable(last.cmd)
    )
    if last.force_threadable is not None:
        threadable = last.force_threadable

    if threadable:
        if last.captured:
            last.cls = PopenThread
    else:
        last.threadable = False


def _last_spec_update_captured(last: SubprocSpec):
    captured = (
        (captured := last.captured)
        # Explicit captures ("object") must always work
        # even when THREAD_SUBPROCS is disabled (e.g. during rc-file loading).
        and not (captured == "hiddenobject" and not last.threadable)
        # a ProcProxy run using ![] should not be captured
        and not (
            callable(last.alias)
            and last.cls is ProcProxy
            and captured == "hiddenobject"
        )
    )
    if captured:
        _make_last_spec_captured(last)


def _make_last_spec_captured(last: SubprocSpec):
    captured = last.captured
    callable_alias = callable(last.alias)

    if captured == "object":
        """
        In full capture mode the subprocess is running in background in fact
        and we don't need to wait for it in downstream code e.g. `jobs.wait_for_active_job`.
        """
        last.background = True

    # cannot used PTY pipes for aliases, for some dark reason,
    # and must use normal pipes instead.
    use_tty = xp.ON_POSIX and not callable_alias
    # Do not set standard in! Popen is not a fan of redirections here
    # set standard out
    if last.stdout is not None:
        last.universal_newlines = True
    elif captured in STDOUT_CAPTURE_KINDS:
        last.universal_newlines = False
        pipe = PipeChannel.from_pipe()
        last.stdout = pipe.open_writer("wb")
        last.captured_stdout = pipe.open_reader("rb")
        last.pipe_channels.append(pipe)
    elif XSH.stdout_uncaptured is not None:
        last.universal_newlines = True
        last.stdout = XSH.stdout_uncaptured
        last.captured_stdout = last.stdout
    elif (
        xp.ON_WINDOWS and not callable_alias and not XSH.env.get("XONSH_CAPTURE_ALWAYS")
    ):
        last.universal_newlines = True
        last.stdout = None  # must truly stream on windows
        last.captured_stdout = ConsoleParallelReader(1)
    else:
        last.universal_newlines = True
        pipe = PipeChannel.from_pty() if use_tty else PipeChannel.from_pipe()
        _safe_pipe_properties(pipe.write_fd, use_tty=use_tty)
        last.stdout = pipe.open_writer("w")
        _safe_pipe_properties(pipe.read_fd, use_tty=use_tty)
        last.captured_stdout = pipe.open_reader("r")
        last.pipe_channels.append(pipe)
    # set standard error
    if last.stderr is not None:
        pass
    elif captured == "stdout":
        pass
    elif captured == "object":
        pipe = PipeChannel.from_pipe()
        last.stderr = pipe.open_writer("w")
        last.captured_stderr = pipe.open_reader("r")
        last.pipe_channels.append(pipe)
    elif XSH.stderr_uncaptured is not None:
        last.stderr = XSH.stderr_uncaptured
        last.captured_stderr = last.stderr
    elif (
        xp.ON_WINDOWS and not callable_alias and not XSH.env.get("XONSH_CAPTURE_ALWAYS")
    ):
        last.universal_newlines = True
        last.stderr = None  # must truly stream on windows
    else:
        pipe = PipeChannel.from_pty() if use_tty else PipeChannel.from_pipe()
        _safe_pipe_properties(pipe.write_fd, use_tty=use_tty)
        last.stderr = pipe.open_writer("w")
        _safe_pipe_properties(pipe.read_fd, use_tty=use_tty)
        last.captured_stderr = pipe.open_reader("r")
        last.pipe_channels.append(pipe)
    # redirect stdout to stderr, if we should
    if isinstance(last.stdout, int) and last.stdout == 2:
        # need to use private interface to avoid duplication.
        last._stdout = last.stderr
    # redirect stderr to stdout, if we should
    if callable_alias and last.stderr == subprocess.STDOUT:
        last._stderr = last.stdout
        last.captured_stderr = None


def _update_proc_alias_threadable(proc):
    threadable = XSH.env.get("THREAD_SUBPROCS") and getattr(
        proc.alias, "__xonsh_threadable__", True
    )
    if proc.force_threadable is not None:
        threadable = proc.force_threadable
    proc.threadable = threadable
    proc.cls = ProcProxyThread if proc.threadable else ProcProxy


def _update_proc_alias_captured(proc):
    proc.captured = getattr(proc.alias, "__xonsh_capturable__", proc.captured)


def _trace_specs(trace, specs, cmds, captured):
    """Show information about specs.

    ``trace`` is the value of ``$XONSH_SUBPROC_TRACE``. If it's a
    callable, it's used as the formatter — called as
    ``trace(cmds, captured=<str|bool>, specs=<list[SubprocSpec]>)``.
    ``specs`` exposes per-command ``args``, ``alias``, ``binary_loc``,
    ``threadable`` and friends. ``CommandPipeline`` is *not* available
    at this point — it's built later, during ``_run_specs``.

    Otherwise ``trace`` is a verbosity int (1/2/3) for the default
    printer.
    """
    if callable(trace):
        trace(cmds, captured=captured, specs=specs)
        return
    r = {"cmds": cmds, "captured": captured}
    print(f"Trace run_subproc({repr(r)})", file=sys.stderr)
    if trace >= 2:
        for i, s in enumerate(specs):
            pcls = s.cls.__module__ + "." + s.cls.__name__
            pcmd = [s.args[0].__name__] + s.args[1:] if callable(s.args[0]) else s.args
            p = {
                "cmd": pcmd,
                "cls": pcls,
            }
            p |= {
                a: getattr(s, a, None)
                for a in [
                    "alias_name",
                    "alias",
                    "binary_loc",
                    "threadable",
                    "background",
                ]
            }
            if trace == 3:
                p |= {
                    a: getattr(s, a, None)
                    for a in [
                        "stdin",
                        "stdout",
                        "stderr",
                        "captured",
                        "captured_stdout",
                        "captured_stderr",
                    ]
                }
            p = {k: v for k, v in p.items() if v is not None}
            print(f"{i}: {repr(p)}", file=sys.stderr)


def cmds_to_specs(cmds, captured=False, envs=None, in_boolop=False):
    """Converts a list of cmds to a list of SubprocSpec objects that are
    ready to be executed.

    ``in_boolop`` is propagated from the parser; it is True when the whole
    pipeline is a direct operand of a ``&&``/``||`` chain.  Each spec gets
    the flag stored on it so downstream code (e.g. ``CommandPipeline``,
    ``_raise_subproc_error``) can decide whether to short-circuit on
    returncode or raise.
    """
    # first build the subprocs independently and separate from the redirects
    specs = []
    redirects = []
    try:
        for i, cmd in enumerate(cmds):
            if isinstance(cmd, str):
                redirects.append(cmd)
            else:
                env = envs[i] if envs is not None else None
                spec = SubprocSpec.build(cmd, captured=captured, env=env)
                spec.pipeline_index = len(specs)
                spec.in_boolop = in_boolop
                specs.append(spec)
        # now modify the subprocs based on the redirects.
        for i, redirect in enumerate(redirects):
            if redirect == "|":
                # these should remain integer file descriptors, and not Python
                # file objects since they connect processes.
                pipe = PipeChannel.from_pipe()
                upstream = specs[i]
                # `e>p` adds stderr to the pipe; stdout still goes through the
                # pipe by default, unless the user diverted it with `o>`/`>`.
                if upstream._stderr is _PIPE_ERR:
                    upstream._stderr = None
                    upstream.stderr = pipe.write_fd
                    # Skip wiring stdout if it is already redirected elsewhere
                    # (e.g. `cmd o> file e>p | grep` — stdout to file, pipe gets
                    # only stderr).
                    skip_stdout = upstream._stdout is not None
                else:
                    skip_stdout = False
                # `a>p`: stdout goes to the pipe and stderr is merged into it
                # (stderr was already set to subprocess.STDOUT by _redirect_streams).
                if upstream._stdout is _PIPE_ALL:
                    upstream._stdout = None
                if not skip_stdout:
                    upstream.stdout = pipe.write_fd
                specs[i + 1].stdin = pipe.read_fd
                upstream.pipe_channels.append(pipe)
            elif redirect == "&" and i == len(redirects) - 1:
                specs[i].background = True
            else:
                raise xt.XonshError(f"unrecognized redirect {redirect!r}")
        # Any pipe-redirect sentinel still present means `a>p`/`e>p` was used
        # without a following `|` pipe.
        for spec in specs:
            if spec._stdout is _PIPE_ALL or spec._stderr is _PIPE_ERR:
                raise xt.XonshError(
                    "xonsh: redirect 'a>p'/'e>p' requires a following pipe '|'"
                )

        # Apply boundary conditions
        if not XSH.env.get("XONSH_CAPTURE_ALWAYS"):
            # Make sure sub-specs are always captured in case:
            # `![some_alias | grep x]`, `$(some_alias)`, `some_alias > file`.
            last = spec
            is_redirected_stdout = bool(last.stdout)
            specs_to_capture = (
                specs
                if captured in STDOUT_CAPTURE_KINDS or is_redirected_stdout
                else specs[:-1]
            )
            _set_specs_capture_always(specs_to_capture)

        # Validate: unthreadable callable aliases cannot be used in pipelines
        if len(specs) > 1:
            for spec in specs:
                if callable(spec.alias) and not spec.threadable:
                    raise xt.XonshError(
                        f"Callable alias {spec.alias_name!r} is explicitly marked as unthreadable and is not supported in pipelines.\n"
                        f"If it's really threadable try to add command decorator `@thread {spec.alias_name}`."
                    )

        _update_last_spec(specs[-1])
    except BaseException:
        # Any pipes/files opened during spec construction would otherwise
        # leak as `ResourceWarning: unclosed file` once GC reaps them.
        for s in specs:
            s.close()
        raise
    return specs


def _set_specs_capture_always(specs_to_capture):
    """Set XONSH_CAPTURE_ALWAYS for all specs."""
    for spec in specs_to_capture:
        if spec.env is None:
            spec.env = {"XONSH_CAPTURE_ALWAYS": True}
        else:
            spec.env.setdefault("XONSH_CAPTURE_ALWAYS", True)


def _shell_set_title(cmds):
    if XSH.env.get("XONSH_INTERACTIVE") and XSH.shell is not None:
        # context manager updates the command information that gets
        # accessed by CurrentJobField when setting the terminal's title
        with XSH.env["PROMPT_FIELDS"]["current_job"].update_current_cmds(cmds):
            # clear the prompt cache so that fields depending on
            # current_job are also re-evaluated (see #4926)
            XSH.env["PROMPT_FIELDS"].reset()
            # The terminal's title needs to be set before starting the
            # subprocess to avoid accidentally answering interactive questions
            # from commands such as `rm -i` (see #1436)
            XSH.shell.settitle()


def run_subproc(cmds, captured=False, envs=None, in_boolop=False):
    """Runs a subprocess, in its many forms. This takes a list of 'commands,'
    which may be a list of command line arguments or a string, representing
    a special connecting character.  For example::

        $ ls | grep wakka

    is represented by the following cmds::

        [['ls'], '|', ['grep', 'wakka']]

    Lastly, the captured argument affects only the last real command.

    ``in_boolop`` is forwarded from the parser; True when this whole
    pipeline is a direct operand of a ``&&``/``||`` chain.  Each spec
    receives ``spec.in_boolop`` so downstream consumers can act on it
    (e.g. let a non-zero return short-circuit instead of raising).
    """

    specs = cmds_to_specs(cmds, captured=captured, envs=envs, in_boolop=in_boolop)

    if trace := XSH.env.get("XONSH_SUBPROC_TRACE", False):
        _trace_specs(trace, specs, cmds, captured)

    cmds = [
        _flatten_cmd_redirects(cmd) if isinstance(cmd, list) else cmd for cmd in cmds
    ]
    _shell_set_title(cmds)
    return _run_specs(specs, cmds)


def _run_command_pipeline(specs, cmds):
    captured = specs[-1].captured
    if captured == "hiddenobject":
        cp = HiddenCommandPipeline(specs)
    else:
        cp = CommandPipeline(specs)
    proc = cp.proc
    background = cp.spec.background
    if proc is not None and not all(x.is_proxy for x in specs):
        xj.add_job(
            {
                "cmds": cmds,
                "pids": [i.pid for i in cp.procs],
                "status": "suspended" if cp.suspended else "running",
                "obj": proc,
                "bg": background,
                "pipeline": cp,
                "pgrp": cp.term_pgid,
            }
        )
    return cp


def _run_specs(specs, cmds):
    cp = _run_command_pipeline(specs, cmds)
    XSH.last = XSH.lastcmd = XSH.interface.lastcmd = cp
    proc, captured, background = (
        cp.proc,
        specs[-1].captured,
        cp.spec.background,
    )

    """
    For some reason, some programs are in a stopped state when the flow
    reaches this point, hence a SIGCONT should be sent to `proc` to make
    sure that the shell doesn't hang. See issue #2999 and the fix in PR #3000
    """
    resume_process(proc)

    if captured == "object":
        return cp
    elif captured == "hiddenobject":
        if not background:
            cp.end()
        return cp
    elif background:
        return
    elif captured == "stdout":
        cp.end()
        return cp.output
    else:
        cp.end()
        return
