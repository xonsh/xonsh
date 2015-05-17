"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import re
import sys
import shlex
import signal
import inspect
import builtins
import subprocess
from io import TextIOWrapper, StringIO
from glob import glob, iglob
from subprocess import Popen, PIPE, STDOUT
from contextlib import contextmanager
from collections import Sequence, MutableMapping, Iterable, namedtuple, \
    MutableSequence, MutableSet

from xonsh.tools import string_types
from xonsh.tools import suggest_commands, XonshError, ON_POSIX, ON_WINDOWS
from xonsh.inspectors import Inspector
from xonsh.environ import Env, default_env
from xonsh.aliases import DEFAULT_ALIASES, bash_aliases
from xonsh.jobs import add_job, wait_for_active_job
from xonsh.proc import ProcProxy, SimpleProcProxy

ENV = None
BUILTINS_LOADED = False
INSPECTOR = Inspector()


class Aliases(MutableMapping):
    """Represents a location to hold and look up aliases."""

    def __init__(self, *args, **kwargs):
        self._raw = {}
        self.update(*args, **kwargs)

    def get(self, key, default=None):
        """Returns the (possibly modified) value. If the key is not present,
        then `default` is returned.
        If the value is callable, it is returned without modification. If it
        is an iterable of strings it will be evaluated recursively to expand
        other aliases, resulting in a new list or a "partially applied"
        callable.
        """
        val = self._raw.get(key)
        if val is None:
            return default
        elif isinstance(val, Iterable) or callable(val):
            return self.eval_alias(val, seen_tokens={key})
        else:
            msg = 'alias of {!r} has an inappropriate type: {!r}'
            raise TypeError(msg.format(key, val))

    def eval_alias(self, value, seen_tokens, acc_args=[]):
        """
        "Evaluates" the alias `value`, by recursively looking up the leftmost
        token and "expanding" if it's also an alias.

        A value like ["cmd", "arg"] might transform like this:
        > ["cmd", "arg"] -> ["ls", "-al", "arg"] -> callable()
        where `cmd=ls -al` and `ls` is an alias with its value being a
        callable.  The resulting callable will be "partially applied" with
        ["-al", "arg"].
        """
        # Beware of mutability: default values for keyword args are evaluated
        # only once.
        if callable(value):
            if acc_args:  # Partial application
                return lambda args, stdin=None: value(acc_args + args,
                                                      stdin=stdin)
            else:
                return value
        else:
            token, *rest = value
            if token in seen_tokens or token not in self._raw:
                # ^ Making sure things like `egrep=egrep --color=auto` works,
                # and that `l` evals to `ls --color=auto -CF` if `l=ls -CF`
                # and `ls=ls --color=auto`
                return value + acc_args
            else:
                return self.eval_alias(self._raw[token],
                                       seen_tokens | {token},
                                       rest + acc_args)

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self._raw[key]

    def __setitem__(self, key, val):
        if isinstance(val, string_types):
            self._raw[key] = shlex.split(val)
        else:
            self._raw[key] = val

    def __delitem__(self, key):
        del self._raw[key]

    def update(self, *args, **kwargs):
        for key, val in dict(*args, **kwargs).items():
            self[key] = val

    def __iter__(self):
        yield from self._raw

    def __len__(self):
        return len(self._raw)

    def __str__(self):
        return str(self._raw)

    def __repr__(self):
        return '{0}.{1}({2})'.format(self.__class__.__module__,
                                     self.__class__.__name__, self._raw)


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
    global ENV
    if ENV is not None:
        ENV.replace_env()
    return os.path.expanduser(os.path.expandvars(s))


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
            if regex.match(p) is not None:
                paths.append(p)
    else:
        for f in files:
            p = os.path.join(base, f)
            if regex.match(p) is None or not os.path.isdir(p):
                continue
            paths += reglob(p, parts=parts, i=i1)
    return paths


def regexpath(s):
    """Takes a regular expression string and returns a list of file
    paths that match the regex.
    """
    s = expand_path(s)
    return reglob(s)


def globpath(s):
    """Simple wrapper around glob that also expands home and env vars."""
    s = expand_path(s)
    o = glob(s)
    return o if len(o) != 0 else [s]


def iglobpath(s):
    """Simple wrapper around iglob that also expands home and env vars."""
    s = expand_path(s)
    return iglob(s)


RE_SHEBANG = re.compile(r'#![ \t]*(.+?)$')


def _is_runnable_name(fname):
    return os.path.isfile(fname) and fname != os.path.basename(fname)


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


def get_script_subproc_command(fname, args):
    """
    Given the name of a script outside the path, returns a list representing
    an appropriate subprocess command to execute the script.  Raises
    PermissionError if the script is not executable.
    """
    # make sure file is executable
    if not os.access(fname, os.X_OK):
        raise PermissionError

    # if the file is a binary, we should call it directly
    if _is_binary(fname):
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

    return interp + [fname] + args


def _subproc_pre():
    os.setpgrp()
    signal.signal(signal.SIGTSTP, lambda n, f: signal.pause())


_REDIR_NAME = "(o(?:ut)?|e(?:rr)?|a(?:ll)?|\d?)"
_REDIR_REGEX = re.compile("{r}(>?>|<){r}$".format(r=_REDIR_NAME))
_MODES = {'>>': 'a', '>': 'w', '<': 'r'}

def _is_redirect(x):
    return isinstance(x, str) and _REDIR_REGEX.match(x)


def _open(fname, mode):
    try:
        return open(fname, mode)
    except:
        raise XonshError('xonsh: {0}: no such file or directory'.format(fname))


def _redirect_io(streams, r, loc=None):
    # special case of redirecting stderr to stdout 
    if r in {'e>o', 'e>out', 'err>o', 'err>out',
             '2>1', '2>&1', 'e>1', 'err>1', 'e>&1', 'err>&1'}:
        if 'stderr' in streams:
            raise XonshError('Multiple redirects for stderr')
        streams['stderr'] = STDOUT
        return

    orig, mode, dest = _REDIR_REGEX.match(r).groups()

    mode = _MODES.get(mode, None)

    if mode == 'r':
        if len(orig) > 0 or len(dest) > 0:
            raise XonshError('Unrecognized redirection command: {}'.format(r))
        elif 'stdin' in streams:
            raise XonshError('Multiple inputs for stdin')
        else:
            streams['stdin'] = _open(loc, mode)
    elif mode in {'w', 'a'}:
        if orig in {'&', 'a', 'all'}:
            if 'stderr' in streams:
                raise XonshError('Multiple redirects for stderr')
            elif 'stdout' in streams:
                raise XonshError('Multiple redirects for stdout')
            targets = ['stdout', 'stderr']
        elif orig in {'2', 'e', 'err'}:
            if 'stderr' in streams:
                raise XonshError('Multiple redirects for stderr')
            targets = ['stderr']
        elif orig in {'', '1', 'o', 'out'}:
            if 'stdout' in streams:
                raise XonshError('Multiple redirects for stdout')
            targets = ['stdout']
        else:
            raise XonshError('Unrecognized redirection command: {}'.format(r))
        
        f = _open(loc, mode)
        for t in targets:
            streams[t] = f

    else:
        raise XonshError('Unrecognized redirection command: {}'.format(r))


def run_subproc(cmds, captured=True):
    """Runs a subprocess, in its many forms. This takes a list of 'commands,'
    which may be a list of command line arguments or a string, representing
    a special connecting character.  For example::

        $ ls | grep wakka

    is represented by the following cmds::

        [['ls'], '|', ['grep', 'wakka']]

    Lastly, the captured argument affects only the last real command.
    """
    global ENV
    print(cmds)
    background = False
    if cmds[-1] == '&':
        background = True
        cmds = cmds[:-1]
    write_target = None
    last_cmd = len(cmds)-1
    prev = None
    procs = []
    prev_proc = None
    for cmd in cmds:
        stdin = None
        stdout = None
        stderr = None
        if isinstance(cmd, string_types):
            prev = cmd
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
            stdin = streams['stdin']
        elif prev_proc is not None:
            stdin = prev_proc.stdout
        # set standard output
        if 'stdout' in streams:
            if cmd is not last_cmd:
                raise XonshError('Multiple redirects for stdout')
            stdout = streams['stdout']
        elif captured or cmd is not last_cmd:
            stdout = PIPE
        else:
            stdout = None
        # set standard error
        if 'stderr' in streams:
            stderr = streams['stderr']
        print(stdin, stdout, stderr)
        uninew = cmd is last_cmd
        alias = builtins.aliases.get(cmd[0], None)
        if _is_runnable_name(cmd[0]):
            try:
                aliased_cmd = get_script_subproc_command(cmd[0], cmd[1:])
            except PermissionError:
                e = 'xonsh: subprocess mode: permission denied: {0}'
                raise XonshError(e.format(cmd[0]))
        elif alias is None:
            aliased_cmd = cmd
        elif callable(alias):
            aliased_cmd = alias
        else:
            aliased_cmd = alias + cmd[1:]
        # compute stdin for subprocess
        if prev_proc is None:
            stdin = None
        else:
            stdin = prev_proc.stdout
        if callable(aliased_cmd):
            prev_is_proxy = True
            numargs = len(inspect.signature(aliased_cmd).parameters)
            if numargs == 2:
                cls = SimpleProcProxy
            elif numargs == 4:
                cls = ProcProxy
            else:
                e = 'Expected callable with 2 or 4 arguments, not {}'
                raise XonshError(e.format(numargs))
            proc = cls(aliased_cmd, cmd[1:],
                       stdin, stdout, stderr,
                       universal_newlines=uninew)
        else:
            prev_is_proxy = False
            subproc_kwargs = {}
            if ON_POSIX:
                subproc_kwargs['preexec_fn'] = _subproc_pre
            try:
                proc = Popen(aliased_cmd,
                             universal_newlines=uninew,
                             env=ENV.detype(),
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
                e += '\n' + suggest_commands(cmd, ENV, builtins.aliases)
                raise XonshError(e)
        procs.append(proc)
        prev = None
        prev_proc = proc
    for proc in procs[:-1]:
        try:
            proc.stdout.close()
        except OSError:
            pass
    if not prev_is_proxy:
        add_job({
            'cmds': cmds,
            'pids': [i.pid for i in procs],
            'obj': prev_proc,
            'bg': background
        })
    if background:
        return
    if prev_is_proxy:
        prev_proc.wait()
    wait_for_active_job()
    if write_target is None:
        # get output
        output = ''
        if prev_proc.stdout not in (None, sys.stdout):
            output = prev_proc.stdout.read()
        if captured:
            return output
    elif last_stdout not in (PIPE, None, sys.stdout):
        last_stdout.close()


def subproc_captured(*cmds):
    """Runs a subprocess, capturing the output. Returns the stdout
    that was produced as a str.
    """
    return run_subproc(cmds, captured=True)


def subproc_uncaptured(*cmds):
    """Runs a subprocess, without capturing the output. Returns the stdout
    that was produced as a str.
    """
    return run_subproc(cmds, captured=False)


def ensure_list_of_strs(x):
    """Ensures that x is a list of strings."""
    if isinstance(x, string_types):
        rtn = [x]
    elif isinstance(x, Sequence):
        rtn = [i if isinstance(i, string_types) else str(i) for i in x]
    else:
        rtn = [str(x)]
    return rtn


def load_builtins(execer=None):
    """Loads the xonsh builtins into the Python builtins. Sets the
    BUILTINS_LOADED variable to True.
    """
    global BUILTINS_LOADED, ENV
    # private built-ins
    builtins.__xonsh_env__ = ENV = Env(default_env())
    builtins.__xonsh_ctx__ = {}
    builtins.__xonsh_help__ = helper
    builtins.__xonsh_superhelp__ = superhelper
    builtins.__xonsh_regexpath__ = regexpath
    builtins.__xonsh_glob__ = globpath
    builtins.__xonsh_exit__ = False
    if hasattr(builtins, 'exit'):
        builtins.__xonsh_pyexit__ = builtins.exit
        del builtins.exit
    if hasattr(builtins, 'quit'):
        builtins.__xonsh_pyquit__ = builtins.quit
        del builtins.quit
    builtins.__xonsh_subproc_captured__ = subproc_captured
    builtins.__xonsh_subproc_uncaptured__ = subproc_uncaptured
    builtins.__xonsh_execer__ = execer
    builtins.__xonsh_all_jobs__ = {}
    builtins.__xonsh_active_job__ = None
    builtins.__xonsh_ensure_list_of_strs__ = ensure_list_of_strs
    # public built-ins
    builtins.evalx = None if execer is None else execer.eval
    builtins.execx = None if execer is None else execer.exec
    builtins.compilex = None if execer is None else execer.compile
    builtins.default_aliases = builtins.aliases = Aliases(DEFAULT_ALIASES)
    builtins.aliases.update(bash_aliases())
    BUILTINS_LOADED = True


def unload_builtins():
    """Removes the xonsh builtins from the Python builtins, if the
    BUILTINS_LOADED is True, sets BUILTINS_LOADED to False, and returns.
    """
    global BUILTINS_LOADED, ENV
    if ENV is not None:
        ENV.undo_replace_env()
        ENV = None
    if hasattr(builtins, '__xonsh_pyexit__'):
        builtins.exit = builtins.__xonsh_pyexit__
    if hasattr(builtins, '__xonsh_pyquit__'):
        builtins.quit = builtins.__xonsh_pyquit__
    if not BUILTINS_LOADED:
        return
    names = ['__xonsh_env__',
             '__xonsh_ctx__',
             '__xonsh_help__',
             '__xonsh_superhelp__',
             '__xonsh_regexpath__',
             '__xonsh_glob__',
             '__xonsh_exit__',
             '__xonsh_pyexit__',
             '__xonsh_pyquit__',
             '__xonsh_subproc_captured__',
             '__xonsh_subproc_uncaptured__',
             '__xonsh_execer__',
             'evalx',
             'execx',
             'compilex',
             'default_aliases',
             '__xonsh_all_jobs__',
             '__xonsh_active_job__',
             '__xonsh_ensure_list_of_strs__', ]
    for name in names:
        if hasattr(builtins, name):
            delattr(builtins, name)
    BUILTINS_LOADED = False


@contextmanager
def xonsh_builtins(execer=None):
    """A context manager for using the xonsh builtins only in a limited
    scope. Likely useful in testing.
    """
    load_builtins(execer=execer)
    yield
    unload_builtins()
