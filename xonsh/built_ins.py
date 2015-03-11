"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import re
import sys
import builtins
import subprocess
from io import TextIOWrapper, StringIO
from glob import glob, iglob
from subprocess import Popen, PIPE
from contextlib import contextmanager
from collections import Sequence, MutableMapping, Iterable, namedtuple

from xonsh.tools import string_types, redirect_stdout, redirect_stderr
from xonsh.inspectors import Inspector
from xonsh.environ import default_env
from xonsh.aliases import DEFAULT_ALIASES

BUILTINS_LOADED = False
ENV = None
INSPECTOR = Inspector()

class Env(MutableMapping):
    """A xonsh environment, whose variables have limited typing 
    (unlike BASH). Most variables are, by default, strings (like BASH).
    However, the following rules also apply based on variable-name:

    * PATH: any variable whose name ends in PATH is a list of strings.
    * XONSH_HISTORY_SIZE: this variable is an int.

    An Env instance may be converted to an untyped version suitable for 
    use in a subprocess.
    """

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
        return self._d[key]

    def __setitem__(self, key, val):
        if isinstance(key, string_types) and 'PATH' in key:
            val = val.split(os.pathsep) if isinstance(val, string_types) \
                  else val
        elif key == 'XONSH_HISTORY_SIZE' and not isinstance(val, int):
            val = int(val)
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
        self._raw = dict(*args, **kwargs)

    def get(self, key, default=None):
        """Returns the (possibly modified) key. If the key is not 
        present, the default value is returned. If the key is a string, 
        then it is parsed and evaluated in a built-ins only context and then 
        return.  If the value is a non-string Iterable of strings, then it is 
        returned directly. If the value is callable, it is also returned 
        without modification. Otherwise, it fails.
        """
        if key not in self._raw:
            return default
        val = self._raw[key]
        if isinstance(val, string_types):
            ctx = {}
            val = builtins.evalx(val, glbs=ctx, locs=ctx)
        elif isinstance(val, Iterable) or callable(val):
            pass
        else:
            msg = 'alias of {0!r} has an inappropriate type: {1!r}'
            raise TypeError(msg.format(key, val))
        return val

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self._raw[key]

    def __setitem__(self, key, val):
        self._raw[key] = val
        
    def __delitem__(self, key):
        del self._raw[key]

    def update(*args, **kwargs):
        self._raw.update(*args, **kwargs)

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
    s = os.path.expandvars(s)
    s = os.path.expanduser(s)
    return s


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

WRITER_MODES = {'>': 'w', '>>': 'a'}

ProcProxy = namedtuple('ProcProxy', ['stdout', 'stderr'])

def _run_callable_subproc(alias, cmd, captured=True, prev_proc=None, 
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
            rtn = alias(cmd[1:], stdin=stdin)
        proxy_stdout = new_stdout.getvalue()
        proxy_stderr = new_stderr.getvalue()
        if isinstance(rtn, str):
            proxy_stdout += rtn
        elif isinstance(rtn, Sequence):
            if rtn[0]:  # not None nor ''
                proxy_stdout += rtn[0]
            if rtn[1]:
                proxy_stderr += rtn[1]
        proc = ProcProxy(proxy_stdout, proxy_stderr)
    else:
        # handles uncaptured mode
        rtn = alias(cmd[1:], stdin=stdin)
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
        proc = ProcProxy(rtnout, rtnerr)
    return proc

def run_subproc(cmds, captured=True):
    """Runs a subprocess, in its many forms. This takes a list of 'commands,'
    which may be a list of command line arguments or a string, represnting
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
        if alias is None:
            aliased_cmd = cmd
        elif callable(alias):
            prev_proc = _run_callable_subproc(alias, cmd, captured=captured, 
                            prev_proc=prev_proc, stdout=stdout)
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
        proc = Popen(aliased_cmd, universal_newlines=uninew, env=ENV.detype(),
                     stdin=stdin, stdout=stdout)
        if prev_is_proxy:
            proc.communicate(input=prev_proc.stdout)
        procs.append(proc)
        prev = None
        prev_proc = proc
    for proc in procs[:-1]:
        proc.stdout.close()
    if background:
        return
    output = prev_proc.stdout if isinstance(prev_proc, ProcProxy) else \
             prev_proc.communicate()[0]
    if write_target is not None:
        with open(write_target, write_mode) as f:
            f.write(output)
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
    builtins.__xonsh_pyexit__ = builtins.exit
    del builtins.exit
    builtins.__xonsh_subproc_captured__ = subproc_captured
    builtins.__xonsh_subproc_uncaptured__ = subproc_uncaptured
    # public built-ins
    builtins.evalx = None if execer is None else execer.eval
    builtins.execx = None if execer is None else execer.exec
    builtins.compilex = None if execer is None else execer.compile
    builtins.aliases = Aliases(DEFAULT_ALIASES)
    BUILTINS_LOADED = True

def unload_builtins():
    """Removes the xonsh builtins from the Python builins, if the 
    BUILTINS_LOADED is True, sets BUILTINS_LOADED to False, and returns.
    """
    global BUILTINS_LOADED, ENV
    ENV.undo_replace_env()
    if ENV is not None:
        ENV = None
    if hasattr(builtins, '__xonsh_pyexit__'):
        builtins.exit = builtins.__xonsh_pyexit__
    if not BUILTINS_LOADED:
        return
    names = ['__xonsh_env__', '__xonsh_help__', '__xonsh_superhelp__',
             '__xonsh_regexpath__', '__xonsh_glob__', '__xonsh_exit__',
             '__xonsh_subproc_captured__', '__xonsh_subproc_uncaptured__',
             'evalx', 'execx', 'compilex', '__xonsh_pyexit__',
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

