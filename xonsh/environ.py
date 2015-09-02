"""Environment for the xonsh shell."""
import functools
import os
import re
import socket
import string
import locale
import builtins
import subprocess
from warnings import warn
from functools import wraps
from collections import MutableMapping, MutableSequence, MutableSet, namedtuple

from xonsh import __version__ as XONSH_VERSION
from xonsh.tools import TERM_COLORS, ON_WINDOWS, ON_MAC, ON_LINUX, string_types, \
    is_int, always_true, always_false, ensure_string, is_env_path, str_to_env_path, \
    env_path_to_str, is_bool, to_bool, bool_to_str
from xonsh.dirstack import _get_cwd

LOCALE_CATS = {
    'LC_CTYPE': locale.LC_CTYPE,
    'LC_COLLATE': locale.LC_COLLATE,
    'LC_NUMERIC': locale.LC_NUMERIC,
    'LC_MONETARY': locale.LC_MONETARY,
    'LC_TIME': locale.LC_TIME,
}
try:
    LOCALE_CATS['LC_MESSAGES'] = locale.LC_MESSAGES
except AttributeError:
    pass


def locale_convert(key):
    """Creates a converter for a locale key."""

    def lc_converter(val):
        locale.setlocale(LOCALE_CATS[key], val)
        val = locale.setlocale(LOCALE_CATS[key])
        return val
    return lc_converter

Ensurer = namedtuple('Ensurer', ['validate', 'convert', 'detype'])
Ensurer.__doc__ = """Named tuples whose elements are functions that
represent environment variable validation, conversion, detyping.
"""

DEFAULT_ENSURERS = {
    re.compile('\w*PATH'): (is_env_path, str_to_env_path, env_path_to_str),
    re.compile('\w*DIRS'): (is_env_path, str_to_env_path, env_path_to_str),
    'LC_CTYPE': (always_false, locale_convert('LC_CTYPE'), ensure_string),
    'LC_MESSAGES': (always_false, locale_convert('LC_MESSAGES'), ensure_string),
    'LC_COLLATE': (always_false, locale_convert('LC_COLLATE'), ensure_string),
    'LC_NUMERIC': (always_false, locale_convert('LC_NUMERIC'), ensure_string),
    'LC_MONETARY': (always_false, locale_convert('LC_MONETARY'), ensure_string),
    'LC_TIME': (always_false, locale_convert('LC_TIME'), ensure_string),
    'XONSH_HISTORY_SIZE': (is_int, int, str),
    'CASE_SENSITIVE_COMPLETIONS': (is_bool, to_bool, bool_to_str),
}


class Env(MutableMapping):
    """A xonsh environment, whose variables have limited typing
    (unlike BASH). Most variables are, by default, strings (like BASH).
    However, the following rules also apply based on variable-name:

    * PATH: any variable whose name ends in PATH is a list of strings.
    * XONSH_HISTORY_SIZE: this variable is an int.
    * LC_* (locale categories): locale catergory names get/set the Python
      locale via locale.getlocale() and locale.setlocale() functions.

    An Env instance may be converted to an untyped version suitable for
    use in a subprocess.
    """

    _arg_regex = re.compile(r'ARG(\d+)')

    def __init__(self, *args, **kwargs):
        """If no initial environment is given, os.environ is used."""
        self._d = {}
        self.ensurers = {k: Ensurer(*v) for k, v in DEFAULT_ENSURERS.items()}
        if len(args) == 0 and len(kwargs) == 0:
            args = (os.environ, )
        for key, val in dict(*args, **kwargs).items():
            self[key] = val
        self._detyped = None
        self._orig_env = None

    def detype(self):
        if self._detyped is not None:
            return self._detyped
        ctx = {}
        for key, val in self._d.items():
            if callable(val) or isinstance(val, MutableMapping):
                continue
            if not isinstance(key, string_types):
                key = str(key)
            ensurer = self.get_ensurer(key)
            val = ensurer.detype(val)
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

    def get_ensurer(self, key,
                    default=Ensurer(always_true, None, ensure_string)):
        """Gets an ensurer for the given key."""
        if key in self.ensurers:
            return self.ensurers[key]
        for k, ensurer in self.ensurers.items():
            if isinstance(k, string_types):
                continue
            m = k.match(key)
            if m is not None:
                ens = ensurer
                break
        else:
            ens = default
        self.ensurers[key] = ens
        return ens

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        m = self._arg_regex.match(key)
        if (m is not None) and (key not in self._d) and ('ARGS' in self._d):
            args = self._d['ARGS']
            ix = int(m.group(1))
            if ix >= len(args):
                e = "Not enough arguments given to access ARG{0}."
                raise IndexError(e.format(ix))
            return self._d['ARGS'][ix]
        val = self._d[key]
        if isinstance(val, (MutableSet, MutableSequence, MutableMapping)):
            self._detyped = None
        return self._d[key]

    def __setitem__(self, key, val):
        ensurer = self.get_ensurer(key)
        if not ensurer.validate(val):
            val = ensurer.convert(val)
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

    def _repr_pretty_(self, p, cycle):
        name = '{0}.{1}'.format(self.__class__.__module__,
                                self.__class__.__name__)
        with p.group(0, name + '(', ')'):
            if cycle:
                p.text('...')
            elif len(self):
                p.break_()
                p.pretty(dict(self))

@functools.lru_cache(maxsize=10)
def locate_binary(name, cwd):
    # StackOverflow for `where` tip: http://stackoverflow.com/a/304447/90297
    locator = 'where' if ON_WINDOWS else 'which'
    try:
        binary_location = subprocess.check_output([locator, name],
                                                  cwd=cwd,
                                                  stderr=subprocess.PIPE,
                                                  universal_newlines=True)
        if not binary_location:
            return
    except (subprocess.CalledProcessError, FileNotFoundError):
        return

    return binary_location


def ensure_git(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get cwd or bail
        kwargs['cwd'] = kwargs.get('cwd', _get_cwd())
        if kwargs['cwd'] is None:
            return

        # step out completely if git is not installed
        if locate_binary('git', kwargs['cwd']) is None:
            return

        return func(*args, **kwargs)
    return wrapper


def ensure_hg(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs['cwd'] = kwargs.get('cwd', _get_cwd())
        if kwargs['cwd'] is None:
            return

        # walk up the directory tree to see if we are inside an hg repo
        path = kwargs['cwd'].split(os.path.sep)
        while len(path) > 0:
            if os.path.exists(os.path.sep.join(path + ['.hg'])):
                break
            del path[-1]

        # bail if we aren't inside a repository
        if path == []:
            return

        kwargs['root'] = os.path.sep.join(path)

        # step out completely if hg is not installed
        if locate_binary('hg', kwargs['cwd']) is None:
            return

        return func(*args, **kwargs)
    return wrapper


@ensure_git
def get_git_branch(cwd=None):
    branch = None
    if not ON_WINDOWS:
        prompt_scripts = ['/usr/lib/git-core/git-sh-prompt',
                          '/usr/local/etc/bash_completion.d/git-prompt.sh']

        for script in prompt_scripts:
            # note that this is about 10x faster than bash -i "__git_ps1"
            _input = ('source {}; __git_ps1 "${{1:-%s}}"'.format(script))
            try:
                branch = subprocess.check_output(['bash', ],
                                                 cwd=cwd,
                                                 input=_input,
                                                 stderr=subprocess.PIPE,
                                                 universal_newlines=True)
                if len(branch) == 0:
                    branch = None
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue

    # fall back to using the git binary if the above failed
    if branch is None:
        try:
            cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
            s = subprocess.check_output(cmd,
                                        stderr=subprocess.PIPE,
                                        cwd=cwd,
                                        universal_newlines=True)
            s = s.strip()
            if len(s) > 0:
                branch = s
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    return branch


def call_hg_command(command, cwd):
    # Override user configurations settings and aliases
    hg_env = os.environ.copy()
    hg_env['HGRCPATH'] = ""

    s = None
    try:
        s = subprocess.check_output(['hg'] + command,
                                    stderr=subprocess.PIPE,
                                    cwd=cwd,
                                    universal_newlines=True,
                                    env=hg_env)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return s


@ensure_hg
def get_hg_branch(cwd=None, root=None):
    branch = None
    active_bookmark = None

    if root is not None:
        branch_path = os.path.sep.join([root, '.hg', 'branch'])
        bookmark_path = os.path.sep.join([root, '.hg', 'bookmarks.current'])

        if os.path.exists(branch_path):
            with open(branch_path, 'r') as branch_file:
                branch = branch_file.read()
        else:
            branch = call_hg_command(['branch'], cwd)

        if os.path.exists(bookmark_path):
            with open(bookmark_path, 'r') as bookmark_file:
                active_bookmark = bookmark_file.read()

    if active_bookmark is not None:
        return "{0}, {1}".format(
            *(b.strip(os.linesep) for b in (branch, active_bookmark)))

    return branch.strip(os.linesep) if branch else None


def current_branch(pad=True):
    """Gets the branch for a current working directory. Returns None
    if the cwd is not a repository.  This currently only works for git and hg
    and should be extended in the future.
    """
    branch = get_git_branch() or get_hg_branch()

    if pad and branch is not None:
        branch = ' ' + branch

    return branch or ''


@ensure_git
def git_dirty_working_directory(cwd=None):
    try:
        cmd = ['git', 'status', '--porcelain']
        s = subprocess.check_output(cmd,
                                    stderr=subprocess.PIPE,
                                    cwd=cwd,
                                    universal_newlines=True)
        return bool(s)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@ensure_hg
def hg_dirty_working_directory(cwd=None, root=None):
    id = call_hg_command(['identify', '--id'], cwd)
    if id is None:
        return False
    return id.strip(os.linesep).endswith('+')


def dirty_working_directory(cwd=None):
    """Returns a boolean as to whether there are uncommitted files in version
    control repository we are inside. Currently supports git and hg.
    """
    return git_dirty_working_directory() or hg_dirty_working_directory()


def branch_color():
    """Return red if the current branch is dirty, otherwise green"""
    return (TERM_COLORS['BOLD_RED'] if dirty_working_directory() else
            TERM_COLORS['BOLD_GREEN'])


DEFAULT_PROMPT = ('{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
                  '{cwd}{branch_color}{curr_branch} '
                  '{BOLD_BLUE}${NO_COLOR} ')
DEFAULT_TITLE = '{user}@{hostname}: {cwd} | xonsh'


def _replace_home(x):
    if ON_WINDOWS:
        home = (builtins.__xonsh_env__['HOMEDRIVE'] +
                builtins.__xonsh_env__['HOMEPATH'][0])
        cwd = x.replace(home, '~')

        if builtins.__xonsh_env__.get('FORCE_POSIX_PATHS'):
            cwd = cwd.replace(os.sep, os.altsep)

        return cwd
    else:
        return x.replace(builtins.__xonsh_env__['HOME'], '~')

_replace_home_cwd = lambda: _replace_home(builtins.__xonsh_env__['PWD'])


if ON_WINDOWS:
    USER = 'USERNAME'
else:
    USER = 'USER'


FORMATTER_DICT = dict(
    user=os.environ.get(USER, '<user>'),
    hostname=socket.gethostname().split('.', 1)[0],
    cwd=_replace_home_cwd,
    cwd_dir=lambda: os.path.dirname(_replace_home_cwd()),
    cwd_base=lambda: os.path.basename(_replace_home_cwd()),
    curr_branch=current_branch,
    branch_color=branch_color,
    **TERM_COLORS)

_FORMATTER = string.Formatter()


def format_prompt(template=DEFAULT_PROMPT, formatter_dict=None):
    """Formats a xonsh prompt template string."""
    template = template() if callable(template) else template
    if formatter_dict is None:
        fmtter = builtins.__xonsh_env__.get('FORMATTER_DICT', FORMATTER_DICT)
    else:
        fmtter = formatter_dict
    included_names = set(i[1] for i in _FORMATTER.parse(template))
    fmt = {}
    for k, v in fmtter.items():
        if k not in included_names:
            continue
        val = v() if callable(v) else v
        val = '' if val is None else val
        fmt[k] = val
    return template.format(**fmt)


RE_HIDDEN = re.compile('\001.*?\002')


def multiline_prompt():
    """Returns the filler text for the prompt in multiline scenarios."""
    curr = builtins.__xonsh_env__.get('PROMPT', "set '$PROMPT = ...' $ ")
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
    return (dots * (headlen // len(dots))) + dots[:headlen % len(dots)] + tail


BASE_ENV = {
    'XONSH_VERSION': XONSH_VERSION,
    'INDENT': '    ',
    'FORMATTER_DICT': dict(FORMATTER_DICT),
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
    'LC_NUMERIC': locale.setlocale(locale.LC_NUMERIC),
    'SHELL_TYPE': 'readline',
    'HIGHLIGHTING_LEXER': None,
    'CASE_SENSITIVE_COMPLETIONS': ON_LINUX,
}

try:
    BASE_ENV['LC_MESSAGES'] = locale.setlocale(locale.LC_MESSAGES)
except AttributeError:
    pass


if ON_MAC:
    BASE_ENV['BASH_COMPLETIONS'] = [
        '/usr/local/etc/bash_completion',
        '/opt/local/etc/profile.d/bash_completion.sh'
    ]
else:
    BASE_ENV['BASH_COMPLETIONS'] = [
        '/etc/bash_completion', '/usr/share/bash-completion/completions/git'
    ]


def bash_env():
    """Attempts to compute the bash envinronment variables."""
    currenv = None
    if hasattr(builtins, '__xonsh_env__'):
        currenv = builtins.__xonsh_env__.detype()
    try:
        s = subprocess.check_output(['bash', '-i', '-l'],
                                    input='env',
                                    env=currenv,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
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
    if ON_WINDOWS:
        # Windows default prompt doesn't work.
        ctx['PROMPT'] = DEFAULT_PROMPT

        # remove these bash variables which only cause problems.
        for ev in ['HOME', 'OLDPWD']:
            if ev in ctx:
                del ctx[ev]

        # Override path-related bash variables; on Windows bash uses
        # /c/Windows/System32 syntax instead of C:\\Windows\\System32
        # which messes up these environment variables for xonsh.
        for ev in ['PATH', 'TEMP', 'TMP']:
            if ev in os.environ:
                ctx[ev] = os.environ[ev]
            elif ev in ctx:
                del ctx[ev]

        ctx['PWD'] = _get_cwd()

    if env is not None:
        ctx.update(env)
    return ctx
