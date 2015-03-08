"""Environment for the xonsh shell.
"""
import os
import re
import socket
import builtins
import subprocess
from warnings import warn

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


RE_HIDDEN = re.compile('\001.*?\002')

def multiline_prompt():
    """Returns the filler text for the prompt in multiline scenarios."""
    curr = builtins.__xonsh_env__.get('PROMPT', "set '$PROMPT = ...' $ ")
    curr = curr() if callable(curr) else curr
    line = curr.rsplit('\n', 1)[1] if '\n' in curr else curr
    line = RE_HIDDEN.sub('', line)  # gets rid of colors
    # most prompts end in whitespace, head is the part before that.
    head = line.rstrip()
    headlen = len(head)
    # tail is the trailing whitespace
    tail = line if headlen == 0 else line.rsplit(head[-1], 1)[1]
    # now to constuct the actual string
    dots = builtins.__xonsh_env__.get('MULTILINE_PROMPT', '.')
    dots = dots() if callable(dots) else dots
    if dots is None or len(dots) == 0:
        return ''
    return (dots*(headlen//len(dots))) + dots[:headlen%len(dots)] + tail


BASE_ENV = {
    'PROMPT': default_prompt,
    'MULTILINE_PROMPT': '.',
    'XONSHRC': os.path.expanduser('~/.xonshrc'),
    'XONSH_HISTORY_SIZE': 8128,
    'XONSH_HISTORY_FILE': os.path.expanduser('~/.xonsh_history'),
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

def xonshrc_context(rcfile=None, execer=None):
    """Attempts to read in xonshrc file, and return the contents."""
    if rcfile is None or execer is None or not os.path.isfile(rcfile):
        return {}
    with open(rcfile, 'r') as f:
        rc = f.read()
    fname = execer.filename
    env = {}
    try:
        execer.filename = rcfile
        execer.exec(rc, glbs={}, locs=env)
    except SyntaxError:
        warn('syntax error in xonsh run control file {0!r}'.format(rcfile), 
             RuntimeWarning)
    finally:
        execer.filename = fname
    return env

def default_env(env=None):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = dict(BASE_ENV)
    ctx.update(os.environ)
    ctx.update(bash_env())
    if env is not None:
        ctx.update(env)
    return ctx
