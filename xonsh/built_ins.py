# -*- coding: utf-8 -*-
"""The xonsh built-ins.

Note that this module is named 'built_ins' so as not to be confused with the
special Python builtins module.
"""
import os
import re
import sys
import time
import shlex
import signal
import atexit
import inspect
import tempfile
import builtins
import subprocess
import contextlib
import collections.abc as abc

from xonsh.lazyasd import LazyObject, lazyobject
from xonsh.history import History
from xonsh.inspectors import Inspector
from xonsh.aliases import Aliases, make_default_aliases
from xonsh.environ import Env, default_env, locate_binary
from xonsh.foreign_shells import load_foreign_aliases
from xonsh.jobs import add_job, wait_for_active_job
from xonsh.platform import ON_POSIX, ON_WINDOWS
from xonsh.proc import (
    ProcProxy, SimpleProcProxy, ForegroundProcProxy,
    SimpleForegroundProcProxy, TeePTYProc, pause_call_resume, CompletedCommand,
    HiddenCompletedCommand)
from xonsh.tools import (
    suggest_commands, expandvars, globpath, XonshError,
    XonshCalledProcessError, XonshBlockError
)
from xonsh.commands_cache import CommandsCache

import xonsh.completers.init

BUILTINS_LOADED = False
INSPECTOR = LazyObject(Inspector, globals(), 'INSPECTOR')


@lazyobject
def AT_EXIT_SIGNALS():
    sigs = (signal.SIGABRT, signal.SIGFPE, signal.SIGILL, signal.SIGSEGV,
            signal.SIGTERM)
    if ON_POSIX:
        sigs += (signal.SIGTSTP, signal.SIGQUIT, signal.SIGHUP)
    return sigs


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


def resetting_signal_handle(sig, f):
    """Sets a new signal handle that will automatically restore the old value
    once the new handle is finished.
    """
    oldh = signal.getsignal(sig)

    def newh(s=None, frame=None):
        f(s, frame)
        signal.signal(sig, oldh)
        if sig != 0:
            sys.exit(sig)
    signal.signal(sig, newh)


def helper(x, name=''):
    """Prints help about, and then returns that variable."""
    INSPECTOR.pinfo(x, oname=name, detail_level=0)
    return x


def superhelper(x, name=''):
    """Prints help about, and then returns that variable."""
    INSPECTOR.pinfo(x, oname=name, detail_level=1)
    return x


def expand_path(s):
    """Takes a string path and expands ~ to home and environment vars."""
    if builtins.__xonsh_env__.get('EXPAND_ENV_VARS'):
        s = expandvars(s)
    return os.path.expanduser(s)


def reglob(path, parts=None, i=None):
    """Regular expression-based globbing."""
    if parts is None:
        path = os.path.normpath(path)
        drive, tail = os.path.splitdrive(path)
        parts = tail.split(os.sep)
        d = os.sep if os.path.isabs(path) else '.'
        d = os.path.join(drive, d)
        return reglob(d, parts, i=0)
    base = subdir = path
    if i == 0:
        if not os.path.isabs(base):
            base = ''
        elif len(parts) > 1:
            i += 1
    regex = os.path.join(base, parts[i])
    if ON_WINDOWS:
        # currently unable to access regex backslash sequences
        # on Windows due to paths using \.
        regex = regex.replace('\\', '\\\\')
    regex = re.compile(regex)
    files = os.listdir(subdir)
    files.sort()
    paths = []
    i1 = i + 1
    if i1 == len(parts):
        for f in files:
            p = os.path.join(base, f)
            if regex.fullmatch(p) is not None:
                paths.append(p)
    else:
        for f in files:
            p = os.path.join(base, f)
            if regex.fullmatch(p) is None or not os.path.isdir(p):
                continue
            paths += reglob(p, parts=parts, i=i1)
    return paths


def regexsearch(s):
    s = expand_path(s)
    return reglob(s)


def globsearch(s):
    csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
    glob_sorted = builtins.__xonsh_env__.get('GLOB_SORTED')
    return globpath(s, ignore_case=(not csc), return_empty=True,
                    sort_result=glob_sorted)


def pathsearch(func, s, pymode=False):
    """
    Takes a string and returns a list of file paths that match (regex, glob,
    or arbitrary search function).
    """
    if (not callable(func) or
            len(inspect.signature(func).parameters) != 1):
        error = "%r is not a known path search function"
        raise XonshError(error % func)
    o = func(s)
    no_match = [] if pymode else [s]
    return o if len(o) != 0 else no_match


RE_SHEBANG = LazyObject(lambda: re.compile(r'#![ \t]*(.+?)$'),
                        globals(), 'RE_SHEBANG')


def _is_binary(fname, limit=80):
    with open(fname, 'rb') as f:
        for i in range(limit):
            char = f.read(1)
            if char == b'\0':
                return True
            if char == b'\n':
                return False
            if char == b'':
                return False
    return False


def _un_shebang(x):
    if x == '/usr/bin/env':
        return []
    elif any(x.startswith(i) for i in ['/usr/bin', '/usr/local/bin', '/bin']):
        x = os.path.basename(x)
    elif x.endswith('python') or x.endswith('python.exe'):
        x = 'python'
    if x == 'xonsh':
        return ['python', '-m', 'xonsh.main']
    return [x]


def get_script_subproc_command(fname, args):
    """
    Given the name of a script outside the path, returns a list representing
    an appropriate subprocess command to execute the script.  Raises
    PermissionError if the script is not executable.
    """
    # make sure file is executable
    if not os.access(fname, os.X_OK):
        raise PermissionError
    if ON_POSIX and not os.access(fname, os.R_OK):
        # on some systems, some importnat programs (e.g. sudo) will have
        # execute permissions but not read/write permisions. This enables
        # things with the SUID set to be run. Needs to come before _is_binary()
        # is called, because that function tries to read the file.
        return [fname] + args
    elif _is_binary(fname):
        # if the file is a binary, we should call it directly
        return [fname] + args
    if ON_WINDOWS:
        # Windows can execute various filetypes directly
        # as given in PATHEXT
        _, ext = os.path.splitext(fname)
        if ext.upper() in builtins.__xonsh_env__.get('PATHEXT'):
            return [fname] + args
    # find interpreter
    with open(fname, 'rb') as f:
        first_line = f.readline().decode().strip()
    m = RE_SHEBANG.match(first_line)
    # xonsh is the default interpreter
    if m is None:
        interp = ['xonsh']
    else:
        interp = m.group(1).strip()
        if len(interp) > 0:
            interp = shlex.split(interp)
        else:
            interp = ['xonsh']
    if ON_WINDOWS:
        o = []
        for i in interp:
            o.extend(_un_shebang(i))
        interp = o
    return interp + [fname] + args


@lazyobject
def _REDIR_REGEX():
    name = "(o(?:ut)?|e(?:rr)?|a(?:ll)?|&?\d?)"
    return re.compile("{r}(>?>|<){r}$".format(r=name))


_MODES = LazyObject(lambda: {'>>': 'a', '>': 'w', '<': 'r'}, globals(),
                    '_MODES')
_WRITE_MODES = LazyObject(lambda: frozenset({'w', 'a'}), globals(),
                          '_WRITE_MODES')
_REDIR_ALL = LazyObject(lambda: frozenset({'&', 'a', 'all'}),
                        globals(), '_REDIR_ALL')
_REDIR_ERR = LazyObject(lambda: frozenset({'2', 'e', 'err'}), globals(),
                        '_REDIR_ERR')
_REDIR_OUT = LazyObject(lambda: frozenset({'', '1', 'o', 'out'}), globals(),
                        '_REDIR_OUT')
_E2O_MAP = LazyObject(lambda: frozenset({'{}>{}'.format(e, o)
                                         for e in _REDIR_ERR
                                         for o in _REDIR_OUT
                                         if o != ''}), globals(), '_E2O_MAP')


def _is_redirect(x):
    return isinstance(x, str) and _REDIR_REGEX.match(x)


def _open(fname, mode):
    # file descriptors
    if isinstance(fname, int):
        return fname
    try:
        return open(fname, mode)
    except PermissionError:
        raise XonshError('xonsh: {0}: permission denied'.format(fname))
    except FileNotFoundError:
        raise XonshError('xonsh: {0}: no such file or directory'.format(fname))
    except Exception:
        raise XonshError('xonsh: {0}: unable to open file'.format(fname))


def _redirect_io(streams, r, loc=None):
    # special case of redirecting stderr to stdout
    if r.replace('&', '') in _E2O_MAP:
        if 'stderr' in streams:
            raise XonshError('Multiple redirects for stderr')
        streams['stderr'] = ('<stdout>', 'a', subprocess.STDOUT)
        return
    orig, mode, dest = _REDIR_REGEX.match(r).groups()
    # redirect to fd
    if dest.startswith('&'):
        try:
            dest = int(dest[1:])
            if loc is None:
                loc, dest = dest, ''
            else:
                e = 'Unrecognized redirection command: {}'.format(r)
                raise XonshError(e)
        except (ValueError, XonshError):
            raise
        except Exception:
            pass
    mode = _MODES.get(mode, None)
    if mode == 'r':
        if len(orig) > 0 or len(dest) > 0:
            raise XonshError('Unrecognized redirection command: {}'.format(r))
        elif 'stdin' in streams:
            raise XonshError('Multiple inputs for stdin')
        else:
            streams['stdin'] = (loc, 'r', _open(loc, mode))
    elif mode in _WRITE_MODES:
        if orig in _REDIR_ALL:
            if 'stderr' in streams:
                raise XonshError('Multiple redirects for stderr')
            elif 'stdout' in streams:
                raise XonshError('Multiple redirects for stdout')
            elif len(dest) > 0:
                e = 'Unrecognized redirection command: {}'.format(r)
                raise XonshError(e)
            targets = ['stdout', 'stderr']
        elif orig in _REDIR_ERR:
            if 'stderr' in streams:
                raise XonshError('Multiple redirects for stderr')
            elif len(dest) > 0:
                e = 'Unrecognized redirection command: {}'.format(r)
                raise XonshError(e)
            targets = ['stderr']
        elif orig in _REDIR_OUT:
            if 'stdout' in streams:
                raise XonshError('Multiple redirects for stdout')
            elif len(dest) > 0:
                e = 'Unrecognized redirection command: {}'.format(r)
                raise XonshError(e)
            targets = ['stdout']
        else:
            raise XonshError('Unrecognized redirection command: {}'.format(r))
        f = _open(loc, mode)
        for t in targets:
            streams[t] = (loc, mode, f)
    else:
        raise XonshError('Unrecognized redirection command: {}'.format(r))


def run_subproc(cmds, captured=False):
    """Runs a subprocess, in its many forms. This takes a list of 'commands,'
    which may be a list of command line arguments or a string, representing
    a special connecting character.  For example::

        $ ls | grep wakka

    is represented by the following cmds::

        [['ls'], '|', ['grep', 'wakka']]

    Lastly, the captured argument affects only the last real command.
    """
    env = builtins.__xonsh_env__
    background = False
    procinfo = {}
    if cmds[-1] == '&':
        background = True
        cmds = cmds[:-1]
    _pipeline_group = None
    write_target = None
    last_cmd = len(cmds) - 1
    procs = []
    prev_proc = None
    _capture_streams = captured in {'stdout', 'object'}
    for ix, cmd in enumerate(cmds):
        starttime = time.time()
        procinfo['args'] = list(cmd)
        stdin = None
        stderr = None
        if isinstance(cmd, str):
            continue
        streams = {}
        while True:
            if len(cmd) >= 3 and _is_redirect(cmd[-2]):
                _redirect_io(streams, cmd[-2], cmd[-1])
                cmd = cmd[:-2]
            elif len(cmd) >= 2 and _is_redirect(cmd[-1]):
                _redirect_io(streams, cmd[-1])
                cmd = cmd[:-1]
            elif len(cmd) >= 3 and cmd[0] == '<':
                _redirect_io(streams, cmd[0], cmd[1])
                cmd = cmd[2:]
            else:
                break
        # set standard input
        if 'stdin' in streams:
            if prev_proc is not None:
                raise XonshError('Multiple inputs for stdin')
            stdin = streams['stdin'][-1]
            procinfo['stdin_redirect'] = streams['stdin'][:-1]
        elif prev_proc is not None:
            stdin = prev_proc.stdout
        # set standard output
        _stdout_name = None
        _stderr_name = None
        if 'stdout' in streams:
            if ix != last_cmd:
                raise XonshError('Multiple redirects for stdout')
            stdout = streams['stdout'][-1]
            procinfo['stdout_redirect'] = streams['stdout'][:-1]
        elif ix != last_cmd:
            stdout = subprocess.PIPE
        elif _capture_streams:
            _nstdout = stdout = tempfile.NamedTemporaryFile(delete=False)
            _stdout_name = stdout.name
        elif builtins.__xonsh_stdout_uncaptured__ is not None:
            stdout = builtins.__xonsh_stdout_uncaptured__
        else:
            stdout = None
        # set standard error
        if 'stderr' in streams:
            stderr = streams['stderr'][-1]
            procinfo['stderr_redirect'] = streams['stderr'][:-1]
        elif captured == 'object' and ix == last_cmd:
            _nstderr = stderr = tempfile.NamedTemporaryFile(delete=False)
            _stderr_name = stderr.name
        elif builtins.__xonsh_stderr_uncaptured__ is not None:
            stderr = builtins.__xonsh_stderr_uncaptured__
        uninew = (ix == last_cmd) and (not _capture_streams)
        # find alias
        if callable(cmd[0]):
            alias = cmd[0]
        else:
            alias = builtins.aliases.get(cmd[0], None)
        procinfo['alias'] = alias
        # find binary location, if not callable
        if alias is None:
            binary_loc = locate_binary(cmd[0])
        elif not callable(alias):
            binary_loc = locate_binary(alias[0])
        # implement AUTO_CD
        if (alias is None and
                builtins.__xonsh_env__.get('AUTO_CD') and
                len(cmd) == 1 and
                os.path.isdir(cmd[0]) and
                binary_loc is None):
            cmd.insert(0, 'cd')
            alias = builtins.aliases.get('cd', None)

        if callable(alias):
            aliased_cmd = alias
        else:
            if alias is not None:
                aliased_cmd = alias + cmd[1:]
            else:
                aliased_cmd = cmd
            if binary_loc is not None:
                try:
                    aliased_cmd = get_script_subproc_command(binary_loc,
                                                             aliased_cmd[1:])
                except PermissionError:
                    e = 'xonsh: subprocess mode: permission denied: {0}'
                    raise XonshError(e.format(cmd[0]))
        _stdin_file = None
        if (stdin is not None and
                env.get('XONSH_STORE_STDIN') and
                captured == 'object' and
                __xonsh_commands_cache__.lazy_locate_binary('cat') and
                __xonsh_commands_cache__.lazy_locate_binary('tee')):
            _stdin_file = tempfile.NamedTemporaryFile()
            cproc = subprocess.Popen(['cat'], stdin=stdin,
                                     stdout=subprocess.PIPE)
            tproc = subprocess.Popen(['tee', _stdin_file.name],
                                     stdin=cproc.stdout, stdout=subprocess.PIPE)
            stdin = tproc.stdout
        if callable(aliased_cmd):
            prev_is_proxy = True
            bgable = getattr(aliased_cmd, '__xonsh_backgroundable__', True)
            numargs = len(inspect.signature(aliased_cmd).parameters)
            if numargs == 2:
                cls = SimpleProcProxy if bgable else SimpleForegroundProcProxy
            elif numargs == 4:
                cls = ProcProxy if bgable else ForegroundProcProxy
            else:
                e = 'Expected callable with 2 or 4 arguments, not {}'
                raise XonshError(e.format(numargs))
            proc = cls(aliased_cmd, cmd[1:],
                       stdin, stdout, stderr,
                       universal_newlines=uninew)
        else:
            prev_is_proxy = False
            usetee = ((stdout is None) and
                      (not background) and
                      env.get('XONSH_STORE_STDOUT', False))
            cls = TeePTYProc if usetee else subprocess.Popen
            subproc_kwargs = {}
            if ON_POSIX and cls is subprocess.Popen:
                def _subproc_pre():
                    if _pipeline_group is None:
                        os.setpgrp()
                    else:
                        os.setpgid(0, _pipeline_group)
                    signal.signal(signal.SIGTSTP, lambda n, f: signal.pause())
                subproc_kwargs['preexec_fn'] = _subproc_pre
            denv = env.detype()
            if ON_WINDOWS:
                # Over write prompt variable as xonsh's $PROMPT does
                # not make much sense for other subprocs
                denv['PROMPT'] = '$P$G'
            try:
                proc = cls(aliased_cmd,
                           universal_newlines=uninew,
                           env=denv,
                           stdin=stdin,
                           stdout=stdout,
                           stderr=stderr,
                           **subproc_kwargs)
            except PermissionError:
                e = 'xonsh: subprocess mode: permission denied: {0}'
                raise XonshError(e.format(aliased_cmd[0]))
            except FileNotFoundError:
                cmd = aliased_cmd[0]
                e = 'xonsh: subprocess mode: command not found: {0}'.format(cmd)
                sug = suggest_commands(cmd, env, builtins.aliases)
                if len(sug.strip()) > 0:
                    e += '\n' + suggest_commands(cmd, env, builtins.aliases)
                raise XonshError(e)
        procs.append(proc)
        prev_proc = proc
        if ON_POSIX and cls is subprocess.Popen and _pipeline_group is None:
            _pipeline_group = prev_proc.pid
    if not prev_is_proxy:
        add_job({
            'cmds': cmds,
            'pids': [i.pid for i in procs],
            'obj': prev_proc,
            'bg': background
        })
    if (env.get('XONSH_INTERACTIVE') and
            not env.get('XONSH_STORE_STDOUT') and
            not _capture_streams and
            hasattr(builtins, '__xonsh_shell__')):
        # set title here to get current command running
        pause_call_resume(prev_proc, builtins.__xonsh_shell__.settitle)
    if background:
        return
    if prev_is_proxy:
        prev_proc.wait()
    wait_for_active_job()
    for proc in procs[:-1]:
        try:
            proc.stdout.close()
        except OSError:
            pass
    hist = builtins.__xonsh_history__
    hist.last_cmd_rtn = prev_proc.returncode
    # get output
    output = b''
    if write_target is None:
        if _stdout_name is not None:
            with open(_stdout_name, 'rb') as stdoutfile:
                output = stdoutfile.read()
            try:
                _nstdout.close()
            except Exception:
                pass
            os.unlink(_stdout_name)
        elif prev_proc.stdout not in (None, sys.stdout):
            output = prev_proc.stdout.read()
        if _capture_streams:
            # to get proper encoding from Popen, we have to
            # use a byte stream and then implement universal_newlines here
            output = output.decode(encoding=env.get('XONSH_ENCODING'),
                                   errors=env.get('XONSH_ENCODING_ERRORS'))
            output = output.replace('\r\n', '\n')
        else:
            hist.last_cmd_out = output
        if captured == 'object':  # get stderr as well
            named = _stderr_name is not None
            unnamed = prev_proc.stderr not in {None, sys.stderr}
            if named:
                with open(_stderr_name, 'rb') as stderrfile:
                    errout = stderrfile.read()
                try:
                    _nstderr.close()
                except Exception:
                    pass
                os.unlink(_stderr_name)
            elif unnamed:
                errout = prev_proc.stderr.read()
            if named or unnamed:
                errout = errout.decode(encoding=env.get('XONSH_ENCODING'),
                                       errors=env.get('XONSH_ENCODING_ERRORS'))
                errout = errout.replace('\r\n', '\n')
                procinfo['stderr'] = errout

    if getattr(prev_proc, 'signal', None):
        sig, core = prev_proc.signal
        sig_str = SIGNAL_MESSAGES.get(sig)
        if sig_str:
            if core:
                sig_str += ' (core dumped)'
            print(sig_str, file=sys.stderr)
    if (not prev_is_proxy and
            hist.last_cmd_rtn is not None and
            hist.last_cmd_rtn > 0 and
            env.get('RAISE_SUBPROC_ERROR')):
        raise subprocess.CalledProcessError(hist.last_cmd_rtn, aliased_cmd,
                                            output=output)
    if captured == 'stdout':
        return output
    elif captured is not False:
        procinfo['executed_cmd'] = aliased_cmd
        procinfo['pid'] = prev_proc.pid
        procinfo['returncode'] = prev_proc.returncode
        procinfo['timestamp'] = (starttime, time.time())
        if captured == 'object':
            procinfo['stdout'] = output
            if _stdin_file is not None:
                _stdin_file.seek(0)
                procinfo['stdin'] = _stdin_file.read().decode()
                _stdin_file.close()
            return CompletedCommand(**procinfo)
        else:
            return HiddenCompletedCommand(**procinfo)


def subproc_captured_stdout(*cmds):
    """Runs a subprocess, capturing the output. Returns the stdout
    that was produced as a str.
    """
    return run_subproc(cmds, captured='stdout')


def subproc_captured_inject(*cmds):
    """Runs a subprocess, capturing the output. Returns a list of
    whitespace-separated strings in the stdout that was produced."""
    return [i.strip() for i in run_subproc(cmds, captured='stdout').split()]


def subproc_captured_object(*cmds):
    """
    Runs a subprocess, capturing the output. Returns an instance of
    ``CompletedCommand`` representing the completed command.
    """
    return run_subproc(cmds, captured='object')


def subproc_captured_hiddenobject(*cmds):
    """
    Runs a subprocess, capturing the output. Returns an instance of
    ``HiddenCompletedCommand`` representing the completed command.
    """
    return run_subproc(cmds, captured='hiddenobject')


def subproc_uncaptured(*cmds):
    """Runs a subprocess, without capturing the output. Returns the stdout
    that was produced as a str.
    """
    return run_subproc(cmds, captured=False)


def ensure_list_of_strs(x):
    """Ensures that x is a list of strings."""
    if isinstance(x, str):
        rtn = [x]
    elif isinstance(x, abc.Sequence):
        rtn = [i if isinstance(i, str) else str(i) for i in x]
    else:
        rtn = [str(x)]
    return rtn


def list_of_strs_or_callables(x):
    """Ensures that x is a list of strings or functions"""
    if isinstance(x, str) or callable(x):
        rtn = [x]
    elif isinstance(x, abc.Sequence):
        rtn = [i if isinstance(i, str) or callable(i) else str(i) for i in x]
    else:
        rtn = [str(x)]
    return rtn


def load_builtins(execer=None, config=None, login=False, ctx=None):
    """Loads the xonsh builtins into the Python builtins. Sets the
    BUILTINS_LOADED variable to True.
    """
    global BUILTINS_LOADED
    # private built-ins
    builtins.__xonsh_config__ = {}
    builtins.__xonsh_env__ = env = Env(default_env(config=config, login=login))
    builtins.__xonsh_help__ = helper
    builtins.__xonsh_superhelp__ = superhelper
    builtins.__xonsh_pathsearch__ = pathsearch
    builtins.__xonsh_globsearch__ = globsearch
    builtins.__xonsh_regexsearch__ = regexsearch
    builtins.__xonsh_glob__ = globpath
    builtins.__xonsh_expand_path__ = expand_path
    builtins.__xonsh_exit__ = False
    builtins.__xonsh_stdout_uncaptured__ = None
    builtins.__xonsh_stderr_uncaptured__ = None
    if hasattr(builtins, 'exit'):
        builtins.__xonsh_pyexit__ = builtins.exit
        del builtins.exit
    if hasattr(builtins, 'quit'):
        builtins.__xonsh_pyquit__ = builtins.quit
        del builtins.quit
    builtins.__xonsh_subproc_captured_stdout__ = subproc_captured_stdout
    builtins.__xonsh_subproc_captured_inject__ = subproc_captured_inject
    builtins.__xonsh_subproc_captured_object__ = subproc_captured_object
    builtins.__xonsh_subproc_captured_hiddenobject__ = subproc_captured_hiddenobject
    builtins.__xonsh_subproc_uncaptured__ = subproc_uncaptured
    builtins.__xonsh_execer__ = execer
    builtins.__xonsh_commands_cache__ = CommandsCache()
    builtins.__xonsh_all_jobs__ = {}
    builtins.__xonsh_ensure_list_of_strs__ = ensure_list_of_strs
    builtins.__xonsh_list_of_strs_or_callables__ = list_of_strs_or_callables
    builtins.__xonsh_completers__ = xonsh.completers.init.default_completers()
    # public built-ins
    builtins.XonshError = XonshError
    builtins.XonshBlockError = XonshBlockError
    builtins.XonshCalledProcessError = XonshCalledProcessError
    builtins.evalx = None if execer is None else execer.eval
    builtins.execx = None if execer is None else execer.exec
    builtins.compilex = None if execer is None else execer.compile

    # sneak the path search functions into the aliases
    # Need this inline/lazy import here since we use locate_binary that relies on __xonsh_env__ in default aliases
    builtins.default_aliases = builtins.aliases = Aliases(make_default_aliases())
    if login:
        builtins.aliases.update(load_foreign_aliases(issue_warning=False))
    # history needs to be started after env and aliases
    # would be nice to actually include non-detyped versions.
    builtins.__xonsh_history__ = History(env=env.detype(),
                                         ts=[time.time(), None], locked=True)
    atexit.register(_lastflush)
    for sig in AT_EXIT_SIGNALS:
        resetting_signal_handle(sig, _lastflush)
    BUILTINS_LOADED = True


def _lastflush(s=None, f=None):
    if hasattr(builtins, '__xonsh_history__'):
        builtins.__xonsh_history__.flush(at_exit=True)


def unload_builtins():
    """Removes the xonsh builtins from the Python builtins, if the
    BUILTINS_LOADED is True, sets BUILTINS_LOADED to False, and returns.
    """
    global BUILTINS_LOADED
    env = getattr(builtins, '__xonsh_env__', None)
    if isinstance(env, Env):
        env.undo_replace_env()
    if hasattr(builtins, '__xonsh_pyexit__'):
        builtins.exit = builtins.__xonsh_pyexit__
    if hasattr(builtins, '__xonsh_pyquit__'):
        builtins.quit = builtins.__xonsh_pyquit__
    if not BUILTINS_LOADED:
        return
    names = ['__xonsh_config__',
             '__xonsh_env__',
             '__xonsh_ctx__',
             '__xonsh_help__',
             '__xonsh_superhelp__',
             '__xonsh_pathsearch__',
             '__xonsh_globsearch__',
             '__xonsh_regexsearch__',
             '__xonsh_glob__',
             '__xonsh_expand_path__',
             '__xonsh_exit__',
             '__xonsh_stdout_uncaptured__',
             '__xonsh_stderr_uncaptured__',
             '__xonsh_pyexit__',
             '__xonsh_pyquit__',
             '__xonsh_subproc_captured_stdout__',
             '__xonsh_subproc_captured_inject__',
             '__xonsh_subproc_captured_object__',
             '__xonsh_subproc_captured_hiddenobject__',
             '__xonsh_subproc_uncaptured__',
             '__xonsh_execer__',
             '__xonsh_commands_cache__',
             '__xonsh_completers__',
             'XonshError',
             'XonshBlockError',
             'XonshCalledProcessError',
             'evalx',
             'execx',
             'compilex',
             'default_aliases',
             '__xonsh_all_jobs__',
             '__xonsh_ensure_list_of_strs__',
             '__xonsh_list_of_strs_or_callables__',
             '__xonsh_history__',
             ]
    for name in names:
        if hasattr(builtins, name):
            delattr(builtins, name)
    BUILTINS_LOADED = False


@contextlib.contextmanager
def xonsh_builtins(execer=None):
    """A context manager for using the xonsh builtins only in a limited
    scope. Likely useful in testing.
    """
    load_builtins(execer=execer)
    yield
    unload_builtins()
