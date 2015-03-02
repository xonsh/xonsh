"""Aliases for the xonsh shell.
"""
import os
import builtins

def cd(args, stdin=None):
    """Changes the directory."""
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
    'ls': ['ls', '--color=auto', '-v'],
    'grep': ['grep', '--color=auto'],
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
    }