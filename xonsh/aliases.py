"""Aliases for the xonsh shell.
"""
import os
import platform
import builtins
import subprocess

def cd(args, stdin=None):
    """Changes the directory.

    If no directory is specified (i.e. if `args` is None) then this
    changes to the current user's home directory.
    """
    if len(args) == 0:
        d = os.path.expanduser('~')
    elif len(args) == 1:
        d = args[0]
    else:
        return '', 'cd takes 0 or 1 arguments, not {0}\n'.format(len(args))
    if not os.path.exists(d):
        return '', 'cd: no such file or directory: {0}\n'.format(d)
    if not os.path.isdir(d):
        return '', 'cd: {0} is not a directory\n'.format(d)
    os.chdir(d)
    builtins.__xonsh_env__['PWD'] = os.getcwd()
    return None, None

def exit(args, stdin=None):
    """Sends signal to exit shell."""
    builtins.__xonsh_exit__ = True
    print()  # gimme a newline
    return None, None

def source_bash(args, stdin=None):
    """Implements bash's source builtin."""
    import tempfile
    env = builtins.__xonsh_env__
    denv = env.detype()
    with tempfile.NamedTemporaryFile(mode='w+t') as f:
        args = ' '.join(args)
        input = 'source {0}\nenv >> {1}\n'.format(args, f.name)
        try:
            subprocess.check_output(['bash'], input=input, env=denv, 
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

DEFAULT_ALIASES = {
    'cd': cd,
    'EOF': exit,
    'exit': exit,
    'source-bash': source_bash,
    'grep': ['grep', '--color=auto'],
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
    }

if platform.system() == 'Darwin':
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']
