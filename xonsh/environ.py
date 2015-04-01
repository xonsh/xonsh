"""Environment for the xonsh shell.
"""
import os
import re
import socket
import locale
import builtins
import platform
import subprocess
from datetime import datetime
from functools import partial
from warnings import warn
from collections import MutableMapping

from xonsh import __version__ as XONSH_VERSION
from xonsh.tools import TERM_COLORS

# This is only needed because of the way that we create prompt objects in
# shell.py.  If we find a way to create prompt objects before
# environ.add_prompt_var() can be called then we wouldn't need this.
_prompt_vars_queue = {}

class BasePrompt(MutableMapping):
    """
    Base class that implements utilities for formatting Prompts.

    You should read the docs for this class to learn how to write your own
    Prompt class.  However, you most likely want to inherit from
    :class:`~DefaultPrompt` if you are writing a custom Prompt as that will
    give you the default prompt variables to start off with.

    Custom Prompts will need to implement their own :meth:`__init__` that adds
    entries to several dicts depending on the needs of the variables they add.
    The Prompt may also implement methods to implement those variables
    (although very simple variables can be written with pre-existing
    functions.)

    Example::

        class MyPrompt:
            def __init__(self, *args, **kwargs):
                super(MyPrompt, self).__init__(*args, **kwargs)

                # Add a variable that's just a static string.  Useful for constants
                # that you can't remember:
                self['bell'] = '\x07'

                # To add a variable that only needs to be computed once add
                # the function to be called to self.  This can be used for any
                # variable that won't change while this shell instance is run.  It is
                # especially useful if the variable takes a long time to compute and
                # is infrequently used by users:
                self['login_time'] = self.login_time

                # To add a variable that needs to be computed every time the prompt is
                # printed simply add a function to self and then add the variable name
                # to the self._run_every set.
                self['time24'] = functools.partial(time.strftime, '%H:%M:%S')
                self._run_every.add('time24')

            def login_time(self):
                who_out = subprocess.check_output(['who', '-m'])
                return ' '.join(who_out.decode().split()[2:4])

    If you add additional methods of looking up the data (beyond simple
    values, cached functions, and functions called every time) then you may
    additionally need to modify both __getitem__() and add_prompt_var() to
    implement them.
    """

    def __init__(self, prompt_template, *args, **kwargs):

        super(BasePrompt, self).__init__(*args, **kwargs)
        self.prompt_template = prompt_template
        self._run_every = set()
        self._storage = dict()

        # Load any prompt vars added before the BasePrompt was created
        global _prompt_vars_queue
        for var_name, var_data in _prompt_vars_queue.items():
            self.add_prompt_var(var_name, *(var_data[0]), **(var_data[1]))
        _prompt_vars_queue = {}

    def __getitem__(self, key):
        """
        If the item is a function, return the output of the function.
        This is so we can have static prompt values that only need to be
        determined once and dynamic values that have to be recomputed each
        time the prompt is displayed.
        """
        value = self._storage[key]

        if callable(value):
            if key in self._run_every:
                # Variables that need to be computed every time
                return value()
            # Variables computed a single time
            value = value()
            self._storage[key] = value

        # If not callable then it was a static value
        return value

    def __setitem__(self, key, value):
        self._storage[key] = value

    def __iter__(self):
        return iter(self._storage)

    def __delitem__(self, key):
        del self._storage[key]

    def __len__(self):
        return len(self._storage)

    def __call__(self):
        return self.prompt_template.format(**self)

    def add_prompt_var(self, var_name, value, call_every=False):
        """Add a variable that can then be used in a prompt template

        Parameters
        ----------
        var_name : str
            The name of the variable.  This is what will be used in prompt
            templates
        value : str or callable
            This is what is substituted for the var_name in templates.  If
            this is a callable, then the value returned by the callable is
            what is substituted into the template.
        call_every : bool
            If True and the value is a callable, then value is called every
            time a prompt containing the var_name is displayed.  This is
            needed when a value will change over the lifetime of a shell.  If
            False, the default, value is only called once and the value is
            cached for use in later prompt strings.
        """
        self[var_name] = value
        if callable(value) and call_every:
            self._run_every.add(var_name)


class DefaultPrompt(BasePrompt):
    """
    This class implements the default prompt variables.

    The following variables are recognized:

    + base_cwd -- basename of the current working directory
    + cwd -- Full path of the current working directory
    + curr_branch -- Name of current git branch (preceded by a space), if any
    + hostname -- Name of host computer (If the system supports it, this will
        be the fqdn)
    + short_host -- Just the host portion of the hostname
    + time -- A datetime object for the current time
    + user -- Name of current user
    + (QUALIFIER\_)COLORNAME -- Inserts an ANSI color code
        - COLORNAME can be any of:
              BLACK, RED, GREEN, YELLOW, BLUE, PURPLE, CYAN, WHITE
        - QUALIFIER is optional and can be any of:
              BOLD, UNDERLINE, BACKGROUND, INTENSE,
              BOLD_INTENSE, BACKGROUND_INTENSE
    + NO_COLOR -- Resets any previously used color codes
    """
    def __init__(self, prompt_template, *args, **kwargs):
        super(DefaultPrompt, self).__init__(prompt_template, *args, **kwargs)
        self._env = builtins.__xonsh_env__

        self.update(TERM_COLORS)
        self.update(dict(
                base_cwd=partial(self.cwd, False),
                cwd=self.cwd,
                curr_branch=self.curr_branch,
                hostname=socket.getfqdn,
                short_host=lambda: socket.gethostname().split('.', 1)[0],
                time=datetime.now,
                user=self.user,
        ))
        self._run_every.update(frozenset(('base_cwd', 'cwd', 'curr_branch', 'time')))

        # Do this last so the defaults could be overridden
        self.update(dict(*args, **kwargs))

    def user(self):
        """Return the current user's username"""
        return self._env.get('USER', '<user>')

    def cwd(self, full_path=True):
        """Return the current working directory

        Parameters
        ----------
        full_path : bool
            If True (the default), return the full path of the
            directory.  If False, return only the directory's basename
        """
        cwd = self._env['PWD'].replace(self._env['HOME'], '~')
        if full_path:
            return cwd
        return os.path.basename(cwd)

    def curr_branch(self, cwd=None):
        """Gets the branch for a current working directory.

        Returns empty string if the cwd is not a repository.  This currently
        only works for git but should be extended in the future.
        """
        branch = None
        cwd = os.getcwd() if cwd is None else cwd

        # step out completely if git is not installed
        try:
            binary_location = subprocess.check_output(['which', 'git'], cwd=cwd,
                                        stderr=subprocess.PIPE,
                                        universal_newlines=True)
        except subprocess.CalledProcessError:
            return ''

        if not binary_location:
            return ''

        prompt_scripts = (
            '/usr/lib/git-core/git-sh-prompt',
            '/usr/share/git-core/contrib/completion/git-prompt.sh',
            '/usr/local/etc/bash_completion.d/git-prompt.sh',
        )

        for script in prompt_scripts:
            if not os.path.exists(script):
                continue
            # note that this is about 10x faster than bash -i "__git_ps1"
            _input = ('source {}; __git_ps1 "${{1:-%s}}"'.format(script))
            try:
                branch = subprocess.check_output(['bash',], cwd=cwd, input=_input,
                                            stderr=subprocess.PIPE,
                                            universal_newlines=True)
            except subprocess.CalledProcessError:
                continue
            else:
                # Trust the git-prompt script determined if we're in a git
                # repo and if so, which branch we're in
                branch = branch.strip()
                break

        else:  # http://bit.ly/for_else
            # fall back to using the git binary if the above failed
            if branch is None:
                try:
                    branch = subprocess.check_output(['git', 'rev-parse','--abbrev-ref', 'HEAD'],
                            stderr=subprocess.PIPE, cwd=cwd,
                            universal_newlines=True)
                    branch = branch.strip()
                except subprocess.CalledProcessError:
                    pass

        if branch:
            return ' {}'.format(branch)
        return ''


DEFAULT_PROMPT = ('{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
                  '{cwd}{BOLD_RED}{curr_branch} {BOLD_BLUE}${NO_COLOR} ')
DEFAULT_TITLE = '{user}@{hostname}: {cwd} | xonsh'

def add_prompt_var(var_name, *args, **kwargs):
    """
    Add an additional prompt var to the Prompt object

    The function signature is kept very generic so that this method can be
    used with different user defined Prompt implementations.  See
    :meth:`BasePrompt.add_prompt_var` for how to use this with the standard
    included Prompt objects.
    """
    env = builtins.__xonsh_env__
    prompt_obj = env.get('PROMPT')

    # $PROMPT can contain a string at first.  When we first display a prompt
    # a default Prompt object is created from that string.  We can directly
    # add prompt vars to a Prompt object otherwise we have to queue up the
    # prompt vars until later
    if hasattr(prompt_obj, 'add_prompt_var'):
        prompt_obj.add_prompt_var(var_name, *args, **kwargs)
    else:
        global _prompt_vars_queue
        _prompt_vars_queue[var_name] = (args, kwargs)


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
    'PROMPT': DEFAULT_PROMPT,
    'TITLE': DEFAULT_TITLE,
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
