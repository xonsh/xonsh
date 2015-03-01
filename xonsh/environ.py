"""Environment for the xonsh shell.
"""
import os
import builtins
import subprocess

default_prompt_template = r'\[\033[01;32m\]\u@\h\[\033[01;34m\] \w\[\033[01;31m\]$(get_curr_branch ) \[\033[01;34m\]\$\[\033[00m\]'

def default_prompt():
    """Returns the default xonsh prompt string. This takes no arguments."""
    env = builtins.__xonsh_env__
    return 'yo '

BASE_ENV = {
    'PROMPT': default_prompt,
    }

def bash_env():
    """Attempts to compute the bash envinronment variables."""
    try:
        s = subprocess.check_output(['bash', '-i'], input='env', env={}, 
                                    universal_newlines=True)
    except subprocess.CalledProcessError:
        s = ''
    items = [line.split('=', 1) for line in s.splitlines()]
    env = dict(items)
    return env

def default_env(env=None):
    """Constructs a default xonsh environment context."""
    ctx = dict(BASE_ENV)
    ctx.update(os.environ)
    ctx.update(bash_env())
    if env is not None:
        ctx.update(env)
    return ctx
       