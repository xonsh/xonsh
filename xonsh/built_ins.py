"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import re
import builtins
import subprocess
from subprocess import Popen, PIPE
from glob import glob, iglob
from contextlib import contextmanager
from collections import MutableMapping, Iterable

from xonsh.tools import string_types
from xonsh.inspectors import Inspector

BUILTINS_LOADED = False
ENV = None
INSPECTOR = Inspector()

class Env(MutableMapping):
    """A xonsh environment, whose variables have limited typing 
    (unlike BASH). Most variables are, by default, strings (like BASH).
    However, the following rules also apply based on variable-name:

    * PATH: any variable whose name ends in PATH is a list of strings.

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
    last_cmd = cmds[-1]
    prev = None
    procs = []
    prev_proc = None
    for cmd in cmds:
        if isinstance(cmd, string_types):
            prev = cmd
            continue
        stdin = None if prev_proc is None else prev_proc.stdout
        stdout = last_stdout if cmd is last_cmd else PIPE
        uninew = cmd is last_cmd
        proc = Popen(cmd, universal_newlines=uninew, env=ENV.detype(),
                     stdin=stdin, stdout=stdout)
        procs.append(proc)
        prev = None
        prev_proc = proc
    for proc in procs[:-1]:
        proc.stdout.close()
    output = prev_proc.communicate()[0]
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


def load_builtins():
    """Loads the xonsh builtins into the Python builtins. Sets the
    BUILTINS_LOADED variable to True.
    """
    global BUILTINS_LOADED, ENV
    builtins.__xonsh_env__ = ENV = Env()
    builtins.__xonsh_help__ = helper
    builtins.__xonsh_superhelp__ = superhelper
    builtins.__xonsh_regexpath__ = regexpath
    builtins.__xonsh_glob__ = globpath
    builtins.__xonsh_subproc_captured__ = subproc_captured
    builtins.__xonsh_subproc_uncaptured__ = subproc_uncaptured
    BUILTINS_LOADED = True

def unload_builtins():
    """Removes the xonsh builtins from the Python builins, if the 
    BUILTINS_LOADED is True, sets BUILTINS_LOADED to False, and returns.
    """
    global BUILTINS_LOADED, ENV
    ENV.undo_replace_env()
    if ENV is not None:
        ENV = None
    if not BUILTINS_LOADED:
        return
    names = ['__xonsh_env__', '__xonsh_help__', '__xonsh_superhelp__',
             '__xonsh_regexpath__', '__xonsh_glob__', 
             '__xonsh_subproc_captured__', '__xonsh_subproc_uncaptured__',]
    for name in names:
        if hasattr(builtins, name):
            delattr(builtins, name)
    BUILTINS_LOADED = False

@contextmanager
def xonsh_builtins():
    """A context manager for using the xonsh builtins only in a limited
    scope. Likely useful in testing.
    """
    load_builtins()
    yield
    unload_builtins()


