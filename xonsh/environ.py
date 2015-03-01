"""Environment for the xonsh shell.
"""
import os
import socket
import builtins
import subprocess

from xonsh.tools import TERM_COLORS

def current_branch(cwd=None):
    """Gets the branch for a current working directory. Returns None
    if the cwd is not a repository.  This currently only works for git, 
    bust should be extended in the future.
    """
    cwd = os.getcwd() if cwd is None else cwd
    try:
        # note that this is about 10x faster than bash -i "__git_ps1"
        d = subprocess.check_output(['which', 'git'], cwd=cwd, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
        d = os.path.dirname(os.path.dirname(d))
        input = ('source ' + d + '/lib/git-core/git-sh-prompt; '
                 '__git_ps1 "${1:-%s}"')
        s = subprocess.check_output(['bash',], cwd=cwd, input=input,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except subprocess.CalledProcessError:
        s = ''
    if len(s) == 0:
        s = None
    return s


default_prompt_template = ('{GREEN}{user}@{hostname}{BLUE} '
                           '{cwd}{RED}{curr_branch} {BLUE}${NO_COLOR} ')

def default_prompt():
    """Returns the default xonsh prompt string. This takes no arguments."""
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    branch = current_branch(cwd=cwd)
    branch = '' if branch is None else ' ' + branch
    p = default_prompt_template.format(user=env.get('USER', '<user>'), 
            hostname=socket.gethostname(),
            cwd=cwd.replace(env['HOME'], '~'),
            curr_branch=branch,
            RED=TERM_COLORS['BOLD_RED'],
            BLUE=TERM_COLORS['BOLD_BLUE'],
            GREEN=TERM_COLORS['BOLD_GREEN'],
            NO_COLOR=TERM_COLORS['NO_COLOR'],
            )
    return p

BASE_ENV = {
    'PROMPT': default_prompt,
    }

def bash_env():
    """Attempts to compute the bash envinronment variables."""
    try:
        s = subprocess.check_output(['bash', '-i'], input='env', env={}, 
                                    stderr=subprocess.PIPE,
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
       