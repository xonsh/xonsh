"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import re
import sys
import time
import shlex
import signal
import locale
import builtins
import subprocess
from io import TextIOWrapper, StringIO
from glob import glob, iglob
from subprocess import Popen, PIPE
from contextlib import contextmanager
from collections import Sequence, MutableMapping, Iterable, namedtuple

from xonsh.tools import string_types, redirect_stdout, redirect_stderr
from xonsh.tools import suggest_commands
from xonsh.inspectors import Inspector
from xonsh.environ import default_env
from xonsh.aliases import DEFAULT_ALIASES, bash_aliases
from xonsh.jobs import print_one_job, get_next_job_number, wait_for_active_job
from xonsh.jobs import ProcProxy

ENV = None
BUILTINS_LOADED = False
INSPECTOR = Inspector()
LOCALE_CAT = {'LC_CTYPE': locale.LC_CTYPE, 'LC_MESSAGES': locale.LC_MESSAGES,
              'LC_COLLATE': locale.LC_COLLATE, 'LC_NUMERIC': locale.LC_NUMERIC,
              'LC_MONETARY': locale.LC_MONETARY, 'LC_TIME': locale.LC_TIME}


class Env(MutableMapping):
    """A xonsh environment, whose variables have limited typing
    (unlike BASH). Most variables are, by default, strings (like BASH).
    However, the following rules also apply based on variable-name:

    * PATH: any variable whose name ends in PATH is a list of strings.
    * XONSH_HISTORY_SIZE: this variable is an int.
    * LC_* (locale categories): locale catergory names get/set the Python
      locale via locale.getlocale() and locale.setlocale() functions.

    An Env instance may be converted to an untyped version suitable for
    use in a subprocess.
    """

    _arg_regex = re.compile(r'ARG(\d+)')

    def __init__(self, *args, **kwargs):
        """If no initial environment is given, os.environ is used."""
        self._d = {}
        if len(args) == 0 and len(kwargs) == 0:
            args = (os.environ,)
        for key, val in dict(*args, **kwargs).items():
            self[key] = val
        self._detyped = None
        self._orig_env = None

    def detype(self):
        if self._detyped is not None:
            return self._detyped
        ctx = {}
        for key, val in self._d.items():
            if callable(val):
                continue
            if not isinstance(key, string_types):
                key = str(key)
            if 'PATH' in key:
                val = os.pathsep.join(val)
            elif not isinstance(val, string_types):
                val = str(val)
            ctx[key] = val
        self._detyped = ctx
        return ctx

    def replace_env(self):
        """Replaces the contents of os.environ with a detyped version
        of the xonsh environement.
        """
        if self._orig_env is None:
            self._orig_env = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.detype())

    def undo_replace_env(self):
        """Replaces the contents of os.environ with a detyped version
        of the xonsh environement.
        """
        if self._orig_env is not None:
            os.environ.clear()
            os.environ.update(self._orig_env)
            self._orig_env = None

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        m = self._arg_regex.match(key)
        if (m is not None) and (key not in self._d) and ('ARGS' in self._d):
            args = self._d['ARGS']
            ix = int(m.group(1))
            if ix >= len(args):
                e = "Not enough arguments given to access ARG{0}."
                raise IndexError(e.format(ix))
            return self._d['ARGS'][ix]
        return self._d[key]

    def __setitem__(self, key, val):
        if isinstance(key, string_types) and 'PATH' in key:
            val = val.split(os.pathsep) if isinstance(val, string_types) \
                  else val
        elif key == 'XONSH_HISTORY_SIZE' and not isinstance(val, int):
            val = int(val)
        elif key in LOCALE_CAT:
            locale.setlocale(LOCALE_CAT[key], val)
            val = locale.setlocale(LOCALE_CAT[key])
        self._d[key] = val
        self._detyped = None

    def __delitem__(self, key):
        del self._d[key]
        self._detyped = None

    def __iter__(self):
        yield from self._d

    def __len__(self):
        return len(self._d)

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return '{0}.{1}({2})'.format(self.__class__.__module__,
                                     self.__class__.__name__, self._d)


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
                return lambda args, stdin=None: value(acc_args+args,
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
                                       rest+acc_args)

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
        parts = path.split(os.sep)
        d = os.sep if path.startswith(os.sep) else '.'
        return reglob(d, parts=parts, i=0)
    base = subdir = path
    if i == 0:
        if base == '.':
            base = ''
        elif base == '/' and len(parts) > 1:
            i += 1
    regex = re.compile(os.path.join(base, parts[i]))
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
    return glob(s)


def iglobpath(s):
    """Simple wrapper around iglob that also expands home and env vars."""
    s = expand_path(s)
    return iglob(s)

WRITER_MODES = {'>': 'w', '>>': 'a'}


def _run_callable_subproc(alias, args, captured=True, prev_proc=None,
                          stdout=None):
    """Helper for running callables as a subprocess."""
    # compute stdin for callable
    if prev_proc is None:
        stdin = None
    elif isinstance(prev_proc, ProcProxy):
        stdin = prev_proc.stdout
    else:
        stdin = StringIO(prev_proc.communicate()[0].decode(), None)
        stdin.seek(0)
        stdin, _ = stdin.read(), stdin.close()
    # Redirect the output streams temporarily. merge with possible
    # return values from alias function.
    if stdout is PIPE:
        # handles captured mode
        new_stdout, new_stderr = StringIO(), StringIO()
        with redirect_stdout(new_stdout), redirect_stderr(new_stderr):
            rtn = alias(args, stdin=stdin)
        proxy_stdout = new_stdout.getvalue()
        proxy_stderr = new_stderr.getvalue()
        if isinstance(rtn, str):
            proxy_stdout += rtn
        elif isinstance(rtn, Sequence):
            if rtn[0]:  # not None nor ''
                proxy_stdout += rtn[0]
            if rtn[1]:
                proxy_stderr += rtn[1]
        return ProcProxy(proxy_stdout, proxy_stderr)
    else:
        # handles uncaptured mode
        rtn = alias(args, stdin=stdin)
        rtnout, rtnerr = None, None
        if isinstance(rtn, str):
            rtnout = rtn
            sys.stdout.write(rtn)
        elif isinstance(rtn, Sequence):
            if rtn[0]:
                rtnout = rtn[0]
                sys.stdout.write(rtn[0])
            if rtn[1]:
                rtnerr = rtn[1]
                sys.stderr.write(rtn[1])
        return ProcProxy(rtnout, rtnerr)


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
    last_stdout = PIPE if captured else None
    background = False
    if cmds[-1] == '&':
        background = True
        cmds = cmds[:-1]
    write_target = None
    if len(cmds) >= 3 and cmds[-2] in WRITER_MODES:
        write_target = cmds[-1][0]
        write_mode = WRITER_MODES[cmds[-2]]
        cmds = cmds[:-2]
        last_stdout = PIPE
    last_cmd = cmds[-1]
    prev = None
    procs = []
    prev_proc = None
    for cmd in cmds:
        if isinstance(cmd, string_types):
            prev = cmd
            continue
        stdout = last_stdout if cmd is last_cmd else PIPE
        uninew = cmd is last_cmd
        alias = builtins.aliases.get(cmd[0], None)
        if _is_runnable_name(cmd[0]):
            try:
                aliased_cmd = get_script_subproc_command(cmd[0], cmd[1:])
            except PermissionError:
                e = 'xonsh: subprocess mode: permission denied: {0}'
                print(e.format(cmd[0]))
                return
        elif alias is None:
            aliased_cmd = cmd
        elif callable(alias):
            prev_proc = _run_callable_subproc(alias, cmd[1:],
                                              captured=captured,
                                              prev_proc=prev_proc,
                                              stdout=stdout)
            continue
        else:
            aliased_cmd = alias + cmd[1:]
        # compute stdin for subprocess
        prev_is_proxy = isinstance(prev_proc, ProcProxy)
        if prev_proc is None:
            stdin = None
        elif prev_is_proxy:
            stdin = PIPE
        else:
            stdin = prev_proc.stdout
        subproc_kwargs = {}
        if os.name == 'posix':
            subproc_kwargs['preexec_fn'] = _subproc_pre
        try:
            proc = Popen(aliased_cmd, universal_newlines=uninew,
                         env=ENV.detype(), stdin=stdin,
                         stdout=stdout, **subproc_kwargs)
        except PermissionError:
            cmd = aliased_cmd[0]
            print('xonsh: subprocess mode: permission denied: {0}'.format(cmd))
            return
        except FileNotFoundError:
            cmd = aliased_cmd[0]
            print('xonsh: subprocess mode: command not found: {0}'.format(cmd))
            print(suggest_commands(cmd, ENV, builtins.aliases), end='')
            return
        procs.append(proc)
        prev = None
        if prev_is_proxy:
            proc.stdin.write(prev_proc.stdout)
            proc.stdin.close()
        prev_proc = proc
    for proc in procs[:-1]:
        proc.stdout.close()
    num = get_next_job_number()
    pids = [i.pid for i in procs]
    if not isinstance(prev_proc, ProcProxy):
        builtins.__xonsh_active_job__ = num
        builtins.__xonsh_all_jobs__[num] = {'cmds': cmds,
                                            'pids': pids,
                                            'obj': prev_proc,
                                            'started': time.time(),
                                            'pgrp': os.getpgid(prev_proc.pid),
                                            'status': 'running',
                                            'bg': background}
    if background:
        print_one_job(num)
        return
    wait_for_active_job()
    # get output
    if isinstance(prev_proc, ProcProxy):
        output = prev_proc.stdout
    elif prev_proc.stdout is not None:
        output = prev_proc.stdout.read()
    # write the output if we should
    if write_target is not None:
        try:
            with open(write_target, write_mode) as f:
                f.write(output)
        except FileNotFoundError:
            print('xonsh: {0}: no such file or directory'.format(write_target))
    if captured:
        return output


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
    names = ['__xonsh_env__', '__xonsh_help__', '__xonsh_superhelp__',
             '__xonsh_regexpath__', '__xonsh_glob__', '__xonsh_exit__',
             '__xonsh_pyexit__', '__xonsh_pyquit__',
             '__xonsh_subproc_captured__', '__xonsh_subproc_uncaptured__',
             '__xonsh_execer__', 'evalx', 'execx', 'compilex',
             'default_aliases', '__xonsh_all_jobs__', '__xonsh_active_job__',
             '__xonsh_ensure_list_of_strs__',
             ]
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
