"""Environment for the xonsh shell.
"""
import os
import re
import socket
import locale
import builtins
import platform
import subprocess
from warnings import warn

from xonsh import __version__ as XONSH_VERSION
from xonsh.tools import TERM_COLORS

def current_branch(cwd=None):
    """Gets the branch for a current working directory. Returns None
    if the cwd is not a repository.  This currently only works for git, 
    bust should be extended in the future.
    """
    branch = None
    cwd = os.getcwd() if cwd is None else cwd

    # step out completely if git is not installed
    try:
        binary_location = subprocess.check_output(['which', 'git'], cwd=cwd,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
        if not binary_location:
            return branch
    except subprocess.CalledProcessError:
        return branch

    prompt_scripts = [
        '/usr/lib/git-core/git-sh-prompt',
        '/usr/local/etc/bash_completion.d/git-prompt.sh'
    ]

    for script in prompt_scripts:
        # note that this is about 10x faster than bash -i "__git_ps1"
        _input = ('source {}; __git_ps1 "${{1:-%s}}"'.format(script))
        try:
            branch = subprocess.check_output(['bash',], cwd=cwd, input=_input,
                                        stderr=subprocess.PIPE,
                                        universal_newlines=True) or None
        except subprocess.CalledProcessError:
            continue

    # fall back to using the git binary if the above failed
    if branch is None:
        try:
            s = subprocess.check_output(['git', 'rev-parse','--abbrev-ref', 'HEAD'],
                    stderr=subprocess.PIPE, cwd=cwd,
                    universal_newlines=True) 
            s = s.strip()
            if len(s) > 0:
                branch = s
        except subprocess.CalledProcessError:
            pass

    return branch


default_prompt = ('{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
                  '{cwd}{BOLD_RED}{curr_branch} {BOLD_BLUE}${NO_COLOR} ')
default_title = '{user}@{hostname}: {cwd} | xonsh'

def format_prompt(template=default_prompt):
    """Formats a xonsh prompt template string.

    The following keyword arguments are recognized in the template string:

    + user -- Name of current user
    + hostname -- Name of host computer
    + cwd -- Current working directory
    + curr_branch -- Name of current git branch (preceded by a space), if any
    + (QUALIFIER\_)COLORNAME -- Inserts an ANSI color code
        - COLORNAME can be any of:
              BLACK, RED, GREEN, YELLOW, BLUE, PURPLE, CYAN, WHITE
        - QUALIFIER is optional and can be any of:
              BOLD, UNDERLINE, BACKGROUND, INTENSE,
              BOLD_INTENSE, BACKGROUND_INTENSE
    + NO_COLOR -- Resets any previously used color codes
    """
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    branch = current_branch(cwd=cwd)
    branch = '' if branch is None else ' ' + branch
    p = template.format(
            user=env.get('USER', '<user>'),
            hostname=socket.gethostname(),
            cwd=cwd.replace(env['HOME'], '~'),
            curr_branch=branch,
            **TERM_COLORS
            )
    return p


RE_HIDDEN = re.compile('\001.*?\002')

def multiline_prompt():
    """Returns the filler text for the prompt in multiline scenarios."""
    curr = builtins.__xonsh_env__.get('PROMPT', "set '$PROMPT = ...' $ ")
    curr = curr() if callable(curr) else curr
    curr = format_prompt(curr)
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
    'XONSH_VERSION': XONSH_VERSION,
    'INDENT': '    ',
    'PROMPT': default_prompt,
    'TITLE': default_title,
    'MULTILINE_PROMPT': '.',
    'XONSHRC': os.path.expanduser('~/.xonshrc'),
    'XONSH_HISTORY_SIZE': 8128,
    'XONSH_HISTORY_FILE': os.path.expanduser('~/.xonsh_history'),
    'LC_CTYPE': locale.setlocale(locale.LC_CTYPE),
    'LC_COLLATE': locale.setlocale(locale.LC_COLLATE),
    'LC_TIME': locale.setlocale(locale.LC_TIME),
    'LC_MONETARY': locale.setlocale(locale.LC_MONETARY),
    'LC_MESSAGES': locale.setlocale(locale.LC_MESSAGES),
    'LC_NUMERIC': locale.setlocale(locale.LC_NUMERIC),
    }

if platform.system() == 'Darwin':
    BASE_ENV['BASH_COMPLETIONS'] = []
else:
    BASE_ENV['BASH_COMPLETIONS'] = ['/etc/bash_completion', 
                                    '/usr/share/bash-completion/completions/git']

def bash_env():
    """Attempts to compute the bash envinronment variables."""
    currenv = None
    if hasattr(builtins, '__xonsh_env__'):
        currenv = builtins.__xonsh_env__.detype()
    try:
        s = subprocess.check_output(['bash', '-i'], input='env', env=currenv, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except subprocess.CalledProcessError:
        s = ''
    items = [line.split('=', 1) for line in s.splitlines() if '=' in line]
    env = dict(items)
    return env

def xonshrc_context(rcfile=None, execer=None):
    """Attempts to read in xonshrc file, and return the contents."""
    if rcfile is None or execer is None or not os.path.isfile(rcfile):
        return {}
    with open(rcfile, 'r') as f:
        rc = f.read()
    if not rc.endswith('\n'):
        rc += '\n'
    fname = execer.filename
    env = {}
    try:
        execer.filename = rcfile
        execer.exec(rc, glbs=env)
    except SyntaxError as err:
        msg = 'syntax error in xonsh run control file {0!r}: {1!s}'
        warn(msg.format(rcfile, err), RuntimeWarning)
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
