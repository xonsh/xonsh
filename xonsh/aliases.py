"""Aliases for the xonsh shell.
"""
import os
import os.path
import platform
import builtins

def cd(args=None, stdin=None):
    """Changes the directory.

    If no directory is specified (i.e. if `args` is None) then this
    changes to the current user's home directory.
    """
    args = args or [os.path.expanduser('~')]
    d = args[0]
    if not os.path.isdir(d):
        return '', 'directory does not exist: {0}\n'.format(d)
    os.chdir(d)
    builtins.__xonsh_env__['PWD'] = os.getcwd()
    return None, None

def exit(args, stdin=None):
    """Sends signal to exit shell."""
    builtins.__xonsh_exit__ = True
    print()  # gimme a newline
    return None, None

DEFAULT_ALIASES = {
    'cd': cd,
    'EOF': exit,
    'exit': exit,
    'grep': ['grep', '--color=auto'],
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
    }

if platform.system() == 'Darwin':
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']
