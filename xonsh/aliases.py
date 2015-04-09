"""Aliases for the xonsh shell.
"""
import os
import gc
import shlex
import platform
import builtins
import itertools
import subprocess
from warnings import warn

from xonsh.dirstack import dirs, pushd, popd
from xonsh.jobs import jobs, fg, bg, kill_all_jobs


def cd(args, stdin=None):
    """Changes the directory.

    If no directory is specified (i.e. if `args` is None) then this
    changes to the current user's home directory.
    """
    env = builtins.__xonsh_env__
    cur_oldpwd = env.get('OLDPWD', os.getcwd())
    if len(args) == 0:
        d = os.path.expanduser('~')
    elif len(args) == 1:
        d = os.path.expanduser(args[0])
        if d == '-':
            d = cur_oldpwd
    else:
        return '', 'cd takes 0 or 1 arguments, not {0}\n'.format(len(args))
    if not os.path.exists(d):
        return '', 'cd: no such file or directory: {0}\n'.format(d)
    if not os.path.isdir(d):
        return '', 'cd: {0} is not a directory\n'.format(d)

    env['OLDPWD'] = os.getcwd()
    os.chdir(d)
    env['PWD'] = os.getcwd()
    return None, None


def exit(args, stdin=None):  # pylint:disable=redefined-builtin,W0622
    """Sends signal to exit shell."""
    builtins.__xonsh_exit__ = True
    kill_all_jobs()
    print()  # gimme a newline
    return None, None


# The following time_it alias and Timer was forked from the IPython project:
# * Copyright (c) 2008-2014, IPython Development Team
# * Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
# * Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
# * Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
class Timer(timeit.Timer):
    """Timer class that explicitly uses self.inner
    
    which is an undocumented implementation detail of CPython,
    not shared by PyPy.
    """
    # Timer.timeit copied from CPython 3.4.2
    def timeit(self, number=timeit.default_number):
        """Time 'number' executions of the main statement.
        To be precise, this executes the setup statement once, and
        then returns the time it takes to execute the main statement
        a number of times, as a float measured in seconds.  The
        argument is the number of times through the loop, defaulting
        to one million.  The main statement, the setup statement and
        the timer function to be used are passed to the constructor.
        """
        it = itertools.repeat(None, number)
        gcold = gc.isenabled()
        gc.disable()
        try:
            timing = self.inner(it, self.timer)
        finally:
            if gcold:
                gc.enable()
        return timing


def time_it(args, stdin=None):
    """Runs timing study on arguments."""
    import time
    import timeit
    timer = Timer(timer=timefunc)
    return


def source_bash(args, stdin=None):
    """Implements bash's source builtin."""
    import tempfile
    env = builtins.__xonsh_env__
    denv = env.detype()
    with tempfile.NamedTemporaryFile(mode='w+t') as f:
        args = ' '.join(args)
        inp = 'source {0}\nenv >> {1}\n'.format(args, f.name)
        try:
            subprocess.check_output(['bash'],
                                    input=inp,
                                    env=denv,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
        except subprocess.CalledProcessError:
            return None, 'could not source {0}\n'.format(args)
        f.seek(0)
        exported = f.read()
    items = [l.split('=', 1) for l in exported.splitlines() if '=' in l]
    newenv = dict(items)
    for k, v in newenv.items():
        if k in env and v == denv[k]:
            continue  # no change from original
        env[k] = v
    return


def bash_aliases():
    """Computes a dictionary of aliases based on Bash's aliases."""
    try:
        s = subprocess.check_output(['bash', '-i'],
                                    input='alias',
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except subprocess.CalledProcessError:
        s = ''
    items = [line.split('=', 1) for line in s.splitlines() if '=' in line]
    aliases = {}
    for key, value in items:
        try:
            key = key[6:]
            value = value.strip('\'')
            value = shlex.split(value)
        except ValueError as exc:
            warn('could not parse Bash alias "{0}": {1!r}'.format(key, exc),
                 RuntimeWarning)
            continue
        aliases[key] = value
    return aliases


DEFAULT_ALIASES = {
    'cd': cd,
    'pushd': pushd,
    'popd': popd,
    'dirs': dirs,
    'jobs': jobs,
    'fg': fg,
    'bg': bg,
    'EOF': exit,
    'exit': exit,
    'quit': exit,
    'source-bash': source_bash,
    'grep': ['grep', '--color=auto'],
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
}

if platform.system() == 'Darwin':
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']
