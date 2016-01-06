# -*- coding: utf-8 -*-
"""Environment for the xonsh shell."""
import os
import re
import json
import socket
import string
import locale
import builtins
import subprocess
from warnings import warn
from functools import wraps
from contextlib import contextmanager
from collections import MutableMapping, MutableSequence, MutableSet, namedtuple

from xonsh import __version__ as XONSH_VERSION
from xonsh.tools import (
    TERM_COLORS, ON_WINDOWS, ON_MAC, ON_LINUX, ON_ARCH, IS_ROOT,
    always_true, always_false, ensure_string, is_env_path, str_to_env_path,
    env_path_to_str, is_bool, to_bool, bool_to_str, is_history_tuple, to_history_tuple,
    history_tuple_to_str, is_float, string_types, is_string, DEFAULT_ENCODING,
    is_completions_display_value, to_completions_display_value, is_string_set,
    csv_to_set, set_to_csv, get_sep, is_int
)
from xonsh.dirstack import _get_cwd
from xonsh.foreign_shells import DEFAULT_SHELLS, load_foreign_envs

LOCALE_CATS = {
    'LC_CTYPE': locale.LC_CTYPE,
    'LC_COLLATE': locale.LC_COLLATE,
    'LC_NUMERIC': locale.LC_NUMERIC,
    'LC_MONETARY': locale.LC_MONETARY,
    'LC_TIME': locale.LC_TIME,
}
if hasattr(locale, 'LC_MESSAGES'):
    LOCALE_CATS['LC_MESSAGES'] = locale.LC_MESSAGES


def locale_convert(key):
    """Creates a converter for a locale key."""
    def lc_converter(val):
        try:
            locale.setlocale(LOCALE_CATS[key], val)
            val = locale.setlocale(LOCALE_CATS[key])
        except (locale.Error, KeyError):
            warn('Failed to set locale {0!r} to {1!r}'.format(key, val), RuntimeWarning)
        return val
    return lc_converter

Ensurer = namedtuple('Ensurer', ['validate', 'convert', 'detype'])
Ensurer.__doc__ = """Named tuples whose elements are functions that
represent environment variable validation, conversion, detyping.
"""

DEFAULT_ENSURERS = {
    'AUTO_CD': (is_bool, to_bool, bool_to_str),
    'AUTO_SUGGEST': (is_bool, to_bool, bool_to_str),
    'BASH_COMPLETIONS': (is_env_path, str_to_env_path, env_path_to_str),
    'CASE_SENSITIVE_COMPLETIONS': (is_bool, to_bool, bool_to_str),
    re.compile('\w*DIRS$'): (is_env_path, str_to_env_path, env_path_to_str),
    'COMPLETIONS_DISPLAY': (is_completions_display_value, to_completions_display_value, str),
    'COMPLETIONS_MENU_ROWS': (is_int, int, str),
    'FORCE_POSIX_PATHS': (is_bool, to_bool, bool_to_str),
    'HISTCONTROL': (is_string_set, csv_to_set, set_to_csv),
    'IGNOREEOF': (is_bool, to_bool, bool_to_str),
    'LC_COLLATE': (always_false, locale_convert('LC_COLLATE'), ensure_string),
    'LC_CTYPE': (always_false, locale_convert('LC_CTYPE'), ensure_string),
    'LC_MESSAGES': (always_false, locale_convert('LC_MESSAGES'), ensure_string),
    'LC_MONETARY': (always_false, locale_convert('LC_MONETARY'), ensure_string),
    'LC_NUMERIC': (always_false, locale_convert('LC_NUMERIC'), ensure_string),
    'LC_TIME': (always_false, locale_convert('LC_TIME'), ensure_string),
    'MOUSE_SUPPORT': (is_bool, to_bool, bool_to_str),
    re.compile('\w*PATH$'): (is_env_path, str_to_env_path, env_path_to_str),
    'PATHEXT': (is_env_path, str_to_env_path, env_path_to_str),
    'TEEPTY_PIPE_DELAY': (is_float, float, str),
    'XONSHRC': (is_env_path, str_to_env_path, env_path_to_str),
    'XONSH_ENCODING': (is_string, ensure_string, ensure_string),
    'XONSH_ENCODING_ERRORS': (is_string, ensure_string, ensure_string),
    'XONSH_HISTORY_SIZE': (is_history_tuple, to_history_tuple, history_tuple_to_str),
    'XONSH_LOGIN': (is_bool, to_bool, bool_to_str),
    'XONSH_STORE_STDOUT': (is_bool, to_bool, bool_to_str),
    'VI_MODE': (is_bool, to_bool, bool_to_str),
}

#
# Defaults
#
def default_value(f):
    """Decorator for making callable default values."""
    f._xonsh_callable_default = True
    return f

def is_callable_default(x):
    """Checks if a value is a callable default."""
    return callable(x) and getattr(x, '_xonsh_callable_default', False)
if ON_WINDOWS:
    DEFAULT_PROMPT = ('{BOLD_GREEN}{user}@{hostname}{BOLD_CYAN} '
                      '{cwd}{branch_color}{curr_branch} '
                      '{BOLD_WHITE}{prompt_end}{NO_COLOR} ')
else:
    DEFAULT_PROMPT = ('{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
                      '{cwd}{branch_color}{curr_branch} '
                      '{BOLD_BLUE}{prompt_end}{NO_COLOR} ')

DEFAULT_TITLE = '{current_job}{user}@{hostname}: {cwd} | xonsh'

@default_value
def xonsh_data_dir(env):
    """Ensures and returns the $XONSH_DATA_DIR"""
    xdd = os.path.join(env.get('XDG_DATA_HOME'), 'xonsh')
    os.makedirs(xdd, exist_ok=True)
    return xdd


@default_value
def xonsh_config_dir(env):
    """Ensures and returns the $XONSH_CONFIG_DIR"""
    xcd = os.path.join(env.get('XDG_CONFIG_HOME'), 'xonsh')
    os.makedirs(xcd, exist_ok=True)
    return xcd


@default_value
def xonshconfig(env):
    """Ensures and returns the $XONSHCONFIG"""
    xcd = env.get('XONSH_CONFIG_DIR')
    xc = os.path.join(xcd, 'config.json')
    return xc


# Default values should generally be immutable, that way if a user wants
# to set them they have to do a copy and write them to the environment.
# try to keep this sorted.
DEFAULT_VALUES = {
    'AUTO_CD': False,
    'AUTO_PUSHD': False,
    'AUTO_SUGGEST': True,
    'BASH_COMPLETIONS': (('/usr/local/etc/bash_completion',
                             '/opt/local/etc/profile.d/bash_completion.sh')
                        if ON_MAC else
                        ('/usr/share/bash-completion/bash_completion',
                             '/usr/share/bash-completion/completions/git')
                        if ON_ARCH else
                        ('/etc/bash_completion',
                             '/usr/share/bash-completion/completions/git')),
    'CASE_SENSITIVE_COMPLETIONS': ON_LINUX,
    'CDPATH': (),
    'COMPLETIONS_DISPLAY': 'multi',
    'COMPLETIONS_MENU_ROWS': 5,
    'DIRSTACK_SIZE': 20,
    'EXPAND_ENV_VARS': True,
    'FORCE_POSIX_PATHS': False,
    'HISTCONTROL': set(),
    'IGNOREEOF': False,
    'INDENT': '    ',
    'LC_CTYPE': locale.setlocale(locale.LC_CTYPE),
    'LC_COLLATE': locale.setlocale(locale.LC_COLLATE),
    'LC_TIME': locale.setlocale(locale.LC_TIME),
    'LC_MONETARY': locale.setlocale(locale.LC_MONETARY),
    'LC_NUMERIC': locale.setlocale(locale.LC_NUMERIC),
    'MOUSE_SUPPORT': False,
    'MULTILINE_PROMPT': '.',
    'PATH': (),
    'PATHEXT': (),
    'PROMPT': DEFAULT_PROMPT,
    'PROMPT_TOOLKIT_COLORS': {},
    'PROMPT_TOOLKIT_STYLES': None,
    'PUSHD_MINUS': False,
    'PUSHD_SILENT': False,
    'SHELL_TYPE': 'prompt_toolkit' if ON_WINDOWS else 'readline',
    'SUGGEST_COMMANDS': True,
    'SUGGEST_MAX_NUM': 5,
    'SUGGEST_THRESHOLD': 3,
    'TEEPTY_PIPE_DELAY': 0.01,
    'TITLE': DEFAULT_TITLE,
    'VI_MODE': False,
    'XDG_CONFIG_HOME': os.path.expanduser(os.path.join('~', '.config')),
    'XDG_DATA_HOME': os.path.expanduser(os.path.join('~', '.local', 'share')),
    'XONSHCONFIG': xonshconfig,
    'XONSHRC': ((os.path.join(os.environ['ALLUSERSPROFILE'],
                              'xonsh', 'xonshrc'),
                os.path.expanduser('~/.xonshrc')) if ON_WINDOWS
               else ('/etc/xonshrc', os.path.expanduser('~/.xonshrc'))),
    'XONSH_CONFIG_DIR': xonsh_config_dir,
    'XONSH_DATA_DIR': xonsh_data_dir,
    'XONSH_ENCODING': DEFAULT_ENCODING,
    'XONSH_ENCODING_ERRORS': 'surrogateescape',
    'XONSH_HISTORY_FILE': os.path.expanduser('~/.xonsh_history.json'),
    'XONSH_HISTORY_SIZE': (8128, 'commands'),
    'XONSH_LOGIN': False,
    'XONSH_SHOW_TRACEBACK': False,
    'XONSH_STORE_STDOUT': False,
}
if hasattr(locale, 'LC_MESSAGES'):
    DEFAULT_VALUES['LC_MESSAGES'] = locale.setlocale(locale.LC_MESSAGES)

class DefaultNotGivenType(object):
    """Singleton for representing when no default value is given."""


DefaultNotGiven = DefaultNotGivenType()

VarDocs = namedtuple('VarDocs', ['docstr', 'configurable', 'default'])
VarDocs.__doc__ = """Named tuple for environment variable documentation
    
Parameters
----------
docstr : str
   The environment variable docstring.
configurable : bool, optional
    Flag for whether the environment variable is configurable or not.
default : str, optional
    Custom docstring for the default value for complex defaults.
    Is this is DefaultNotGiven, then the default will be looked up 
    from DEFAULT_VALUES and converted to a str.
"""
VarDocs.__new__.__defaults__ = (True, DefaultNotGiven)  # iterates from back

# Please keep the following in alphabetic order - scopatz
DEFAULT_DOCS = {
    'ANSICON': VarDocs('This is used on Windows to set the title, '
                       'if available.', configurable=ON_WINDOWS),
    'AUTO_CD': VarDocs(
        'Flag to enable changing to a directory by entering the dirname or '
        'full path only (without the cd command).'),
    'AUTO_PUSHD': VarDocs(
        'Flag for automatically pushing directories onto the directory stack.'
        ),
    'AUTO_SUGGEST': VarDocs(
        ('``True``
        ('Enable automatic command suggestions based on history (like in fish shell).
      
        Pressing the right arrow key inserts the currently displayed suggestion.
        
        (Only usable with SHELL_TYPE=prompt_toolkit)
    'BASH_COMPLETIONS': VarDocs(
        ('Normally this is ``('/etc/bash_completion', '/usr/share/bash-completion/completions/git')``
        but on Mac is ``('/usr/local/etc/bash_completion', '/opt/local/etc/profile.d/bash_completion.sh')``
        and on Arch Linux is ``('/usr/share/bash-completion/bash_completion',
        '/usr/share/bash-completion/completions/git')``.
        ('This is a list (or tuple) of strings that specifies where the BASH completion 
        files may be found. The default values are platform dependent, but sane. 
        To specify an alternate list, do so in the run control file.
    'CASE_SENSITIVE_COMPLETIONS': VarDocs(
        ('``True`` on Linux, otherwise ``False``
        ('Sets whether completions should be case sensitive or case insensitive.
    'CDPATH': VarDocs(
        ('``[]``
        ('A list of paths to be used as roots for a ``cd``, breaking compatibility with 
        bash, xonsh always prefer an existing relative path.
    'COMPLETIONS_DISPLAY': VarDocs(
        ('``'multi'``
        ('Configure if and how Python completions are displayed by the prompt_toolkit shell.
      
        This option does not affect bash completions, auto-suggestions etc.
        
        Changing it at runtime will take immediate effect, so you can quickly
        disable and enable completions during shell sessions.
        
          ('If COMPLETIONS_DISPLAY is ``'none'`` or ``'false'``, do not display those completions.
        
          ('If COMPLETIONS_DISPLAY is ``'single'``, display completions in a single column while typing.
        
          ('If COMPLETIONS_DISPLAY is ``'multi'`` or ``'true'``, display completions in multiple columns while typing.
        
        These option values are not case- or type-sensitive, so e.g.
        writing ``$COMPLETIONS_DISPLAY = None`` and ``$COMPLETIONS_DISPLAY = 'none'`` is equivalent.
        
        (Only usable with SHELL_TYPE=prompt_toolkit)
    'COMPLETIONS_MENU_ROWS': VarDocs(
        ('``5``
        ('Number of rows to reserve for tab-completions menu if
        ``$COMPLETIONS_DISPLAY`` is ``'single'`` or ``'multi'``. This only 
        effects the prompt-toolkit shell.
    'DIRSTACK_SIZE': VarDocs(
        ('``20``
        ('Maximum size of the directory stack.
    'EXPAND_ENV_VARS': VarDocs(
        ('``True``
        ('Toggles whether environment variables are expanded inside of strings in subprocess mode.
    'FORCE_POSIX_PATHS': VarDocs(
        ('``False``
        ('Forces forward slashes (``/``) on Windows systems when using auto completion if 
        set to anything truthy.
    'FORMATTER_DICT': VarDocs(
        ('xonsh.environ.FORMATTER_DICT  
        ('Dictionary containing variables to be used when formatting PROMPT and TITLE 
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    'HISTCONTROL': VarDocs(
        ('``set([])``
        ('A set of strings (comma-separated list in string form) of options that
        determine what commands are saved to the history list. By default all
        commands are saved. The option ``ignoredups`` will not save the command
        if it matches the previous command. The option ``ignoreerr`` will cause
        any commands that fail (i.e. return non-zero exit status) to not be
        added to the history list.
    'IGNOREEOF': VarDocs(
        ('``False``
        ('Prevents Ctrl-D from exiting the shell.
    'INDENT': VarDocs(
        ('``'    '``
        ('Indentation string for multiline input
    'MOUSE_SUPPORT': VarDocs(
        ('``False``
        ('Enable mouse support in the prompt_toolkit shell.
        
        This allows clicking for positioning the cursor or selecting a completion. In some terminals
        however, this disables the ability to scroll back through the history of the terminal.
        
        (Only usable with SHELL_TYPE=prompt_toolkit)
    'MULTILINE_PROMPT': VarDocs(
        ('``'.'``
        ('Prompt text for 2nd+ lines of input, may be str or function which returns 
        a str.
    'OLDPWD': VarDocs(
        ('No default
        ('Used to represent a previous present working directory.
    'PATH': VarDocs(
        ('``()``
        ('List of strings representing where to look for executables.
    'PATHEXT': VarDocs(
        ('``()``
        ('List of strings for filtering valid exeutables by.
    'PROMPT': VarDocs(
        ('xonsh.environ.DEFAULT_PROMPT  
        ('The prompt text.  May contain keyword arguments which are auto-formatted,
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    'PROMPT_TOOLKIT_COLORS': VarDocs(
        ('``{}``
        ('This is a mapping of from color names to HTML color codes.  Whenever
        prompt-toolkit would color a word a particular color (in the prompt, or
        in syntax highlighting), it will use the value specified here to
        represent that color, instead of its default.  If a color is not
        specified here, prompt-toolkit uses the colors from
        ``xonsh.tools._PT_COLORS``.
    'PROMPT_TOOLKIT_STYLES': VarDocs(
        ('``None``
        ('This is a mapping of user-specified styles for prompt-toolkit. See the 
        prompt-toolkit documentation for more details. If None, this is skipped.
    'PUSHD_MINUS': VarDocs(
        ('``False``
        ('Flag for directory pushing functionality. False is the normal behaviour.
    'PUSHD_SILENT': VarDocs(
        ('``False``
        ('Whether or not to supress directory stack manipulation output.
    'SHELL_TYPE': VarDocs(
        ('``'prompt_toolkit'`` if on Windows, otherwise ``'readline'``
        ('Which shell is used. Currently two base shell types are supported: 
        ``'readline'`` that is backed by Python's readline module, and 
        ``'prompt_toolkit'`` that uses external library of the same name. 
        To use the prompt_toolkit shell you need to have 
        `prompt_toolkit <https://github.com/jonathanslenders/python-prompt-toolkit>`_
        library installed. To specify which shell should be used, do so in the run 
        control file. Additionally, you may also set this value to ``'random'``
        to get a random choice of shell type on startup.
    'SUGGEST_COMMANDS': VarDocs(
        ('``True``
        ('When a user types an invalid command, xonsh will try to offer suggestions of 
        similar valid commands if this is ``True``.
    'SUGGEST_MAX_NUM': VarDocs(
        ('``5``
        ('xonsh will show at most this many suggestions in response to an invalid command.
        If negative, there is no limit to how many suggestions are shown.
    'SUGGEST_THRESHOLD': VarDocs(
        ('``3``
        ('An error threshold. If the Levenshtein distance between the entered command and 
        a valid command is less than this value, the valid command will be offered as a 
        suggestion.
    'TEEPTY_PIPE_DELAY': VarDocs(
        ('``0.01``
        ('The number of [seconds] to delay a spawned process if it has information
        being piped in via stdin. This value must be a float. If a value less than 
        or equal to zero is passed in, no delay is used. This can be used to fix 
        situations where a spawned process, such as piping into ``grep``, exits
        too quickly for the piping operation itself. TeePTY (and thus this variable)
        are currently only used when ``$XONSH_STORE_STDOUT`` is ``True``.
    'TERM': VarDocs(
        ('No default
        ('TERM is sometimes set by the terminal emulator. This is used (when valid)
        to determine whether or not to set the title. Users shouldn't need to 
        set this themselves.
    'TITLE': VarDocs(
        ('xonsh.environ.DEFAULT_TITLE
        ('The title text for the window in which xonsh is running. Formatted in the same 
        manner as PROMPT, 
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    'VI_MODE': VarDocs(
        ('``False``
        ('Flag to enable ``vi_mode`` in the ``prompt_toolkit`` shell.  
    'XDG_CONFIG_HOME': VarDocs(
        ('``~/.config``
        ('Open desktop standard configuration home dir. This is the same default as
        used in the standard.
    'XDG_DATA_HOME': VarDocs(
        ('``~/.local/share``
        ('Open desktop standard data home dir. This is the same default as used
        in the standard.
    'XONSHCONFIG': VarDocs(
        ('``$XONSH_CONFIG_DIR/config.json``
        ('The location of the static xonsh configuration file, if it exists. This is
        in JSON format.
    'XONSHRC': VarDocs(
        ('``('/etc/xonshrc', '~/.xonshrc')`` (Linux and OSX) 
    	``('%ALLUSERSPROFILE%\xonsh\xonshrc', '~/.xonshrc')`` (Windows)
        ('A tuple of the locations of run control files, if they exist.  User defined
        run control file will supercede values set in system-wide control file if there
        is a naming collision.
    'XONSH_CONFIG_DIR': VarDocs(
        ('``$XDG_CONFIG_HOME/xonsh``
        ('This is location where xonsh configuration information is stored.
    'XONSH_DATA_DIR': VarDocs(
        ('``$XDG_DATA_HOME/xonsh``
        ('This is the location where xonsh data files are stored, such as history.
    'XONSH_ENCODING': VarDocs(
        ('``sys.getdefaultencoding()``
        ('This is the that xonsh should use for subrpocess operations.
    'XONSH_ENCODING_ERRORS': VarDocs(
        ('``'surrogateescape'``
        ('The flag for how to handle encoding errors should they happen.
        Any string flag that has been previously registered with Python
        is allowed. See the `Python codecs documentation <https://docs.python.org/3/library/codecs.html#error-handlers>`_
        for more information and available options. 
    'XONSH_HISTORY_FILE': VarDocs(
        ('``'~/.xonsh_history'``
        ('Location of history file (deprecated).
    'XONSH_HISTORY_SIZE': VarDocs(
        ('``(8128, 'commands')`` or ``'8128 commands'``           
        ('Value and units tuple that sets the size of history after garbage collection. 
        Canonical units are ``'commands'`` for the number of past commands executed, 
        ``'files'`` for the number of history files to keep, ``'s'`` for the number of
        seconds in the past that are allowed, and ``'b'`` for the number of bytes that 
        are allowed for history to consume. Common abbreviations, such as ``6 months``
        or ``1 GB`` are also allowed.
    'XONSH_INTERACTIVE': VarDocs(
        ('
        ('``True`` if xonsh is running interactively, and ``False`` otherwise.
    'XONSH_LOGIN': VarDocs(
        ('``True`` if xonsh is running as a login shell, and ``False`` otherwise.
        ('Whether or not xonsh is a login shell.
    'XONSH_SHOW_TRACEBACK': VarDocs(
        ('``False`` but not set
        ('Controls if a traceback is shown exceptions occur in the shell. Set ``True`` 
        to always show or ``False`` to always hide. If undefined then traceback is 
        hidden but a notice is shown on how to enable the traceback.
    'XONSH_STORE_STDOUT': VarDocs(
        ('``False``
        ('Whether or not to store the stdout and stderr streams in the history files.


    }

#
# actual environment
#

class Env(MutableMapping):
    """A xonsh environment, whose variables have limited typing
    (unlike BASH). Most variables are, by default, strings (like BASH).
    However, the following rules also apply based on variable-name:

    * PATH: any variable whose name ends in PATH is a list of strings.
    * XONSH_HISTORY_SIZE: this variable is an (int | float, str) tuple.
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
        self.defaults = DEFAULT_VALUES
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

    @contextmanager
    def swap(self, other):
        """Provides a context manager for temporarily swapping out certain
        environment variables with other values. On exit from the context
        manager, the original values are restored.
        """
        old = {}
        for k, v in other.items():
            old[k] = self.get(k, NotImplemented)
            self[k] = v
        yield self
        for k, v in old.items():
            if v is NotImplemented:
                del self[k]
            else:
                self[k] = v


    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, val):
        ensurer = self.get_ensurer(key)
        if not ensurer.validate(val):
            val = ensurer.convert(val)
        self._d[key] = val
        self._detyped = None

    def __delitem__(self, key):
        del self._d[key]
        self._detyped = None

    def get(self, key, default=DefaultNotGiven):
        """The environment will look up default values from its own defaults if a
        default is not given here.
        """
        m = self._arg_regex.match(key)
        if (m is not None) and (key not in self._d) and ('ARGS' in self._d):
            args = self._d['ARGS']
            ix = int(m.group(1))
            if ix >= len(args):
                e = "Not enough arguments given to access ARG{0}."
                raise IndexError(e.format(ix))
            val = self._d['ARGS'][ix]
        elif key in self._d:
            val = self._d[key]
        elif default is DefaultNotGiven:
            val = self.defaults.get(key, None)
            if is_callable_default(val):
                val = val(self)
        else:
            val = default
        if isinstance(val, (MutableSet, MutableSequence, MutableMapping)):
            self._detyped = None
        return val

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


def _replace_home(x):
    if ON_WINDOWS:
        home = (builtins.__xonsh_env__['HOMEDRIVE'] +
                builtins.__xonsh_env__['HOMEPATH'][0])
        if x.startswith(home):
            x = x.replace(home, '~', 1)

        if builtins.__xonsh_env__.get('FORCE_POSIX_PATHS'):
            x = x.replace(os.sep, os.altsep)

        return x
    else:
        home = builtins.__xonsh_env__['HOME']
        if x.startswith(home):
            x = x.replace(home, '~', 1)
        return x

_replace_home_cwd = lambda: _replace_home(builtins.__xonsh_env__['PWD'])

def _collapsed_pwd():
    sep = get_sep()
    pwd = _replace_home_cwd().split(sep)
    l = len(pwd)
    leader = sep if l>0 and len(pwd[0])==0 else ''
    base = [i[0] if ix != l-1 else i for ix,i in enumerate(pwd) if len(i) > 0]
    return leader + sep.join(base)


def _current_job():
    j = builtins.__xonsh_active_job__
    if j is not None:
        j = builtins.__xonsh_all_jobs__[j]
        if not j['bg']:
            cmd = j['cmds'][-1]
            s = cmd[0]
            if s == 'sudo' and len(cmd) > 1:
                s = cmd[1]
            return '{} | '.format(s)
    return ''


if ON_WINDOWS:
    USER = 'USERNAME'
else:
    USER = 'USER'


FORMATTER_DICT = dict(
    user=os.environ.get(USER, '<user>'),
    prompt_end='#' if IS_ROOT else '$',
    hostname=socket.gethostname().split('.', 1)[0],
    cwd=_replace_home_cwd,
    cwd_dir=lambda: os.path.dirname(_replace_home_cwd()),
    cwd_base=lambda: os.path.basename(_replace_home_cwd()),
    short_cwd=_collapsed_pwd,
    curr_branch=current_branch,
    branch_color=branch_color,
    current_job=_current_job,
    **TERM_COLORS)
DEFAULT_VALUES['FORMATTER_DICT'] = dict(FORMATTER_DICT)

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
    for name in included_names:
        if name is None:
            continue
        if name.startswith('$'):
            v = builtins.__xonsh_env__[name[1:]]
        else:
            v = fmtter[name]
        val = v() if callable(v) else v
        val = '' if val is None else val
        fmt[name] = val
    return template.format(**fmt)


RE_HIDDEN = re.compile('\001.*?\002')

def multiline_prompt():
    """Returns the filler text for the prompt in multiline scenarios."""
    curr = builtins.__xonsh_env__.get('PROMPT')
    curr = format_prompt(curr)
    line = curr.rsplit('\n', 1)[1] if '\n' in curr else curr
    line = RE_HIDDEN.sub('', line)  # gets rid of colors
    # most prompts end in whitespace, head is the part before that.
    head = line.rstrip()
    headlen = len(head)
    # tail is the trailing whitespace
    tail = line if headlen == 0 else line.rsplit(head[-1], 1)[1]
    # now to constuct the actual string
    dots = builtins.__xonsh_env__.get('MULTILINE_PROMPT')
    dots = dots() if callable(dots) else dots
    if dots is None or len(dots) == 0:
        return ''
    return (dots * (headlen // len(dots))) + dots[:headlen % len(dots)] + tail


BASE_ENV = {
    'BASH_COMPLETIONS': list(DEFAULT_VALUES['BASH_COMPLETIONS']),
    'FORMATTER_DICT': dict(DEFAULT_VALUES['FORMATTER_DICT']),
    'XONSH_VERSION': XONSH_VERSION,
}

def load_static_config(ctx):
    """Loads a static configuration file from a given context, rather than the
    current environment.
    """
    env = {}
    env['XDG_CONFIG_HOME'] = ctx.get('XDG_CONFIG_HOME',
                                     DEFAULT_VALUES['XDG_CONFIG_HOME'])
    env['XONSH_CONFIG_DIR'] = ctx['XONSH_CONFIG_DIR'] if 'XONSH_CONFIG_DIR' in ctx \
                              else xonsh_config_dir(env)
    env['XONSHCONFIG'] = ctx['XONSHCONFIG'] if 'XONSHCONFIG' in ctx \
                                  else xonshconfig(env)
    config = env['XONSHCONFIG']
    if os.path.isfile(config):
        with open(config, 'r') as f:
            conf = json.load(f)
    else:
        conf = {}
    return conf


def xonshrc_context(rcfiles=None, execer=None):
    """Attempts to read in xonshrc file, and return the contents."""
    if (rcfiles is None or execer is None
       or sum([os.path.isfile(rcfile) for rcfile in rcfiles]) == 0):
        return {}
    env = {}
    for rcfile in rcfiles:
        if not os.path.isfile(rcfile):
            continue
        with open(rcfile, 'r') as f:
            rc = f.read()
        if not rc.endswith('\n'):
            rc += '\n'
        fname = execer.filename
        try:
            execer.filename = rcfile
            execer.exec(rc, glbs=env)
        except SyntaxError as err:
            msg = 'syntax error in xonsh run control file {0!r}: {1!s}'
            warn(msg.format(rcfile, err), RuntimeWarning)
        finally:
            execer.filename = fname
    return env


def windows_env_fixes(ctx):
    """Environment fixes for Windows. Operates in-place."""
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


def default_env(env=None):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = dict(BASE_ENV)
    ctx.update(os.environ)
    conf = load_static_config(ctx)
    ctx.update(conf.get('env', ()))
    ctx.update(load_foreign_envs(shells=conf.get('foreign_shells', DEFAULT_SHELLS),
                                 issue_warning=False))
    if ON_WINDOWS:
        windows_env_fixes(ctx)
    # finalize env
    if env is not None:
        ctx.update(env)
    return ctx
