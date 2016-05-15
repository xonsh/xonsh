# -*- coding: utf-8 -*-
"""Environment for the xonsh shell."""
import builtins
from collections import Mapping, MutableMapping, MutableSequence, MutableSet, namedtuple
from contextlib import contextmanager
from functools import wraps
from itertools import chain
import json
import locale
import os
from pprint import pformat
import re
import socket
import string
import subprocess
import sys
from warnings import warn

from xonsh import __version__ as XONSH_VERSION
from xonsh.codecache import run_script_with_cache
from xonsh.dirstack import _get_cwd
from xonsh.foreign_shells import DEFAULT_SHELLS, load_foreign_envs
from xonsh.platform import (BASH_COMPLETIONS_DEFAULT, ON_ANACONDA, ON_LINUX,
                            ON_WINDOWS, DEFAULT_ENCODING)
from xonsh.tools import (
    IS_SUPERUSER, always_true, always_false, ensure_string, is_env_path,
    str_to_env_path, env_path_to_str, is_bool, to_bool, bool_to_str,
    is_history_tuple, to_history_tuple, history_tuple_to_str, is_float,
    is_string, is_completions_display_value, to_completions_display_value,
    is_string_set, csv_to_set, set_to_csv, get_sep, is_int, is_bool_seq,
    csv_to_bool_seq, bool_seq_to_csv, DefaultNotGiven, print_exception,
    setup_win_unicode_console, intensify_colors_on_win_setter
)


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
    'AUTO_PUSHD': (is_bool, to_bool, bool_to_str),
    'AUTO_SUGGEST': (is_bool, to_bool, bool_to_str),
    'BASH_COMPLETIONS': (is_env_path, str_to_env_path, env_path_to_str),
    'CASE_SENSITIVE_COMPLETIONS': (is_bool, to_bool, bool_to_str),
    re.compile('\w*DIRS$'): (is_env_path, str_to_env_path, env_path_to_str),
    'COMPLETIONS_DISPLAY': (is_completions_display_value, to_completions_display_value, str),
    'COMPLETIONS_MENU_ROWS': (is_int, int, str),
    'FORCE_POSIX_PATHS': (is_bool, to_bool, bool_to_str),
    'HISTCONTROL': (is_string_set, csv_to_set, set_to_csv),
    'IGNOREEOF': (is_bool, to_bool, bool_to_str),
    'INTENSIFY_COLORS_ON_WIN':(always_false, intensify_colors_on_win_setter, bool_to_str),
    'LC_COLLATE': (always_false, locale_convert('LC_COLLATE'), ensure_string),
    'LC_CTYPE': (always_false, locale_convert('LC_CTYPE'), ensure_string),
    'LC_MESSAGES': (always_false, locale_convert('LC_MESSAGES'), ensure_string),
    'LC_MONETARY': (always_false, locale_convert('LC_MONETARY'), ensure_string),
    'LC_NUMERIC': (always_false, locale_convert('LC_NUMERIC'), ensure_string),
    'LC_TIME': (always_false, locale_convert('LC_TIME'), ensure_string),
    'LOADED_CONFIG': (is_bool, to_bool, bool_to_str),
    'LOADED_RC_FILES': (is_bool_seq, csv_to_bool_seq, bool_seq_to_csv),
    'MOUSE_SUPPORT': (is_bool, to_bool, bool_to_str),
    re.compile('\w*PATH$'): (is_env_path, str_to_env_path, env_path_to_str),
    'PATHEXT': (is_env_path, str_to_env_path, env_path_to_str),
    'RAISE_SUBPROC_ERROR': (is_bool, to_bool, bool_to_str),
    'RIGHT_PROMPT': (is_string, ensure_string, ensure_string),
    'TEEPTY_PIPE_DELAY': (is_float, float, str),
    'UPDATE_OS_ENVIRON': (is_bool, to_bool, bool_to_str),
    'XONSHRC': (is_env_path, str_to_env_path, env_path_to_str),
    'XONSH_CACHE_SCRIPTS': (is_bool, to_bool, bool_to_str),
    'XONSH_CACHE_EVERYTHING': (is_bool, to_bool, bool_to_str),
    'XONSH_COLOR_STYLE': (is_string, ensure_string, ensure_string),
    'XONSH_ENCODING': (is_string, ensure_string, ensure_string),
    'XONSH_ENCODING_ERRORS': (is_string, ensure_string, ensure_string),
    'XONSH_HISTORY_SIZE': (is_history_tuple, to_history_tuple, history_tuple_to_str),
    'XONSH_LOGIN': (is_bool, to_bool, bool_to_str),
    'XONSH_STORE_STDOUT': (is_bool, to_bool, bool_to_str),
    'XONSH_STORE_STDIN': (is_bool, to_bool, bool_to_str),
    'VI_MODE': (is_bool, to_bool, bool_to_str),
    'VIRTUAL_ENV': (is_string, ensure_string, ensure_string),
    'WIN_UNICODE_CONSOLE': (always_false, setup_win_unicode_console, bool_to_str),
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
    DEFAULT_PROMPT = ('{env_name}'
                      '{BOLD_INTENSE_GREEN}{user}@{hostname}{BOLD_INTENSE_CYAN} '
                      '{cwd}{branch_color}{curr_branch}{NO_COLOR} '
                      '{BOLD_INTENSE_CYAN}{prompt_end}{NO_COLOR} ')
else:
    DEFAULT_PROMPT = ('{env_name}'
                      '{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
                      '{cwd}{branch_color}{curr_branch}{NO_COLOR} '
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
    'BASH_COMPLETIONS': BASH_COMPLETIONS_DEFAULT,
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
    'INTENSIFY_COLORS_ON_WIN': True,
    'LC_CTYPE': locale.setlocale(locale.LC_CTYPE),
    'LC_COLLATE': locale.setlocale(locale.LC_COLLATE),
    'LC_TIME': locale.setlocale(locale.LC_TIME),
    'LC_MONETARY': locale.setlocale(locale.LC_MONETARY),
    'LC_NUMERIC': locale.setlocale(locale.LC_NUMERIC),
    'LOADED_CONFIG': False,
    'LOADED_RC_FILES': (),
    'MOUSE_SUPPORT': False,
    'MULTILINE_PROMPT': '.',
    'PATH': (),
    'PATHEXT': (),
    'PROMPT': DEFAULT_PROMPT,
    'PUSHD_MINUS': False,
    'PUSHD_SILENT': False,
    'RAISE_SUBPROC_ERROR': False,
    'RIGHT_PROMPT': '',
    'SHELL_TYPE': 'best',
    'SUGGEST_COMMANDS': True,
    'SUGGEST_MAX_NUM': 5,
    'SUGGEST_THRESHOLD': 3,
    'TEEPTY_PIPE_DELAY': 0.01,
    'TITLE': DEFAULT_TITLE,
    'UPDATE_OS_ENVIRON': False,
    'VI_MODE': False,
    'WIN_UNICODE_CONSOLE': True,
    'XDG_CONFIG_HOME': os.path.expanduser(os.path.join('~', '.config')),
    'XDG_DATA_HOME': os.path.expanduser(os.path.join('~', '.local', 'share')),
    'XONSHCONFIG': xonshconfig,
    'XONSHRC': ((os.path.join(os.environ['ALLUSERSPROFILE'],
                              'xonsh', 'xonshrc'),
                os.path.expanduser('~/.xonshrc')) if ON_WINDOWS
               else ('/etc/xonshrc', os.path.expanduser('~/.xonshrc'))),
    'XONSH_CACHE_SCRIPTS': True,
    'XONSH_CACHE_EVERYTHING': False,
    'XONSH_COLOR_STYLE': 'default',
    'XONSH_CONFIG_DIR': xonsh_config_dir,
    'XONSH_DATA_DIR': xonsh_data_dir,
    'XONSH_ENCODING': DEFAULT_ENCODING,
    'XONSH_ENCODING_ERRORS': 'surrogateescape',
    'XONSH_HISTORY_FILE': os.path.expanduser('~/.xonsh_history.json'),
    'XONSH_HISTORY_SIZE': (8128, 'commands'),
    'XONSH_LOGIN': False,
    'XONSH_SHOW_TRACEBACK': False,
    'XONSH_STORE_STDIN': False,
    'XONSH_STORE_STDOUT': False,
}
if hasattr(locale, 'LC_MESSAGES'):
    DEFAULT_VALUES['LC_MESSAGES'] = locale.setlocale(locale.LC_MESSAGES)

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
                       'if available.', configurable=False),
    'AUTO_CD': VarDocs(
        'Flag to enable changing to a directory by entering the dirname or '
        'full path only (without the cd command).'),
    'AUTO_PUSHD': VarDocs(
        'Flag for automatically pushing directories onto the directory stack.'
        ),
    'AUTO_SUGGEST': VarDocs(
        'Enable automatic command suggestions based on history, like in the fish '
        'shell.\n\nPressing the right arrow key inserts the currently '
        'displayed suggestion. Only usable with $SHELL_TYPE=prompt_toolkit.'),
    'BASH_COMPLETIONS': VarDocs(
        'This is a list (or tuple) of strings that specifies where the BASH '
        'completion files may be found. The default values are platform '
        'dependent, but sane. To specify an alternate list, do so in the run '
        'control file.', default=(
        "Normally this is:\n\n"
        "    ('/etc/bash_completion',\n"
        "     '/usr/share/bash-completion/completions/git')\n\n"
        "But, on Mac it is:\n\n"
        "    ('/usr/local/etc/bash_completion',\n"
        "     '/opt/local/etc/profile.d/bash_completion.sh')\n\n"
        "And on Arch Linux it is:\n\n"
        "    ('/usr/share/bash-completion/bash_completion',\n"
        "     '/usr/share/bash-completion/completions/git')\n\n"
        "Other OS-specific defaults may be added in the future.")),
    'CASE_SENSITIVE_COMPLETIONS': VarDocs(
        'Sets whether completions should be case sensitive or case '
        'insensitive.', default='True on Linux, False otherwise.'),
    'CDPATH': VarDocs(
        'A list of paths to be used as roots for a cd, breaking compatibility '
        'with Bash, xonsh always prefer an existing relative path.'),
    'COMPLETIONS_DISPLAY': VarDocs(
        'Configure if and how Python completions are displayed by the '
        'prompt_toolkit shell.\n\nThis option does not affect Bash '
        'completions, auto-suggestions, etc.\n\nChanging it at runtime will '
        'take immediate effect, so you can quickly disable and enable '
        'completions during shell sessions.\n\n'
        "- If $COMPLETIONS_DISPLAY is 'none' or 'false', do not display\n"
        "  those completions.\n"
        "- If $COMPLETIONS_DISPLAY is 'single', display completions in a\n"
        '  single column while typing.\n'
        "- If $COMPLETIONS_DISPLAY is 'multi' or 'true', display completions\n"
        "  in multiple columns while typing.\n\n"
        'These option values are not case- or type-sensitive, so e.g.'
        "writing \"$COMPLETIONS_DISPLAY = None\" and \"$COMPLETIONS_DISPLAY "
        "= 'none'\" are equivalent. Only usable with "
        "$SHELL_TYPE=prompt_toolkit"),
    'COMPLETIONS_MENU_ROWS': VarDocs(
        'Number of rows to reserve for tab-completions menu if '
        "$COMPLETIONS_DISPLAY is 'single' or 'multi'. This only affects the "
        'prompt-toolkit shell.'),
    'DIRSTACK_SIZE': VarDocs('Maximum size of the directory stack.'),
    'EXPAND_ENV_VARS': VarDocs(
        'Toggles whether environment variables are expanded inside of strings '
        'in subprocess mode.'),
    'FORCE_POSIX_PATHS': VarDocs(
        "Forces forward slashes ('/') on Windows systems when using auto "
        'completion if set to anything truthy.', configurable=ON_WINDOWS),
    'FORMATTER_DICT': VarDocs(
        'Dictionary containing variables to be used when formatting $PROMPT '
        "and $TITLE. See 'Customizing the Prompt' "
        'http://xon.sh/tutorial.html#customizing-the-prompt',
        configurable=False, default='xonsh.environ.FORMATTER_DICT'),
    'HISTCONTROL': VarDocs(
        'A set of strings (comma-separated list in string form) of options '
        'that determine what commands are saved to the history list. By '
        "default all commands are saved. The option 'ignoredups' will not "
        "save the command if it matches the previous command. The option "
        "'ignoreerr' will cause any commands that fail (i.e. return non-zero "
        "exit status) to not be added to the history list."),
    'IGNOREEOF': VarDocs('Prevents Ctrl-D from exiting the shell.'),
    'INDENT': VarDocs('Indentation string for multiline input'),
    'INTENSIFY_COLORS_ON_WIN': VarDocs('Enhance style colors for readability '
        'when using the default terminal (cmd.exe) on winodws. Blue colors, '
        'which are hard to read, are replaced with cyan. Other colors are '
        'generally replaced by their bright counter parts.',
        configurable=ON_WINDOWS),
    'LOADED_CONFIG': VarDocs('Whether or not the xonsh config file was loaded',
        configurable=False),
    'LOADED_RC_FILES': VarDocs(
        'Whether or not any of the xonsh run control files were loaded at '
        'startup. This is a sequence of bools in Python that is converted '
        "to a CSV list in string form, ie [True, False] becomes 'True,False'.",
        configurable=False),
    'MOUSE_SUPPORT': VarDocs(
        'Enable mouse support in the prompt_toolkit shell. This allows '
        'clicking for positioning the cursor or selecting a completion. In '
        'some terminals however, this disables the ability to scroll back '
        'through the history of the terminal. Only usable with '
        '$SHELL_TYPE=prompt_toolkit'),
    'MULTILINE_PROMPT': VarDocs(
        'Prompt text for 2nd+ lines of input, may be str or function which '
        'returns a str.'),
    'OLDPWD': VarDocs('Used to represent a previous present working directory.',
        configurable=False),
    'PATH': VarDocs(
        'List of strings representing where to look for executables.'),
    'PATHEXT': VarDocs('List of strings for filtering valid executables by.'),
    'PROMPT': VarDocs(
        'The prompt text. May contain keyword arguments which are '
        "auto-formatted, see 'Customizing the Prompt' at "
        'http://xon.sh/tutorial.html#customizing-the-prompt.',
        default='xonsh.environ.DEFAULT_PROMPT'),
    'PUSHD_MINUS': VarDocs(
        'Flag for directory pushing functionality. False is the normal '
        'behavior.'),
    'PUSHD_SILENT': VarDocs(
        'Whether or not to suppress directory stack manipulation output.'),
    'RAISE_SUBPROC_ERROR': VarDocs(
        'Whether or not to raise an error if a subprocess (captured or '
        'uncaptured) returns a non-zero exit status, which indicates failure. '
        'This is most useful in xonsh scripts or modules where failures '
        'should cause an end to execution. This is less useful at a terminal. '
        'The error that is raised is a subprocess.CalledProcessError.'),
    'RIGHT_PROMPT': VarDocs('Template string for right-aligned text '
        'at the prompt. This may be parameterized in the same way as '
        'the $PROMPT variable. Currently, this is only available in the '
        'prompt-toolkit shell.'),
    'SHELL_TYPE': VarDocs(
        'Which shell is used. Currently two base shell types are supported:\n\n'
        "    - 'readline' that is backed by Python's readline module\n"
        "    - 'prompt_toolkit' that uses external library of the same name\n"
        "    - 'random' selects a random shell from the above on startup\n"
        "    - 'best' selects the most feature-rich shell available on the\n"
        "       user's system\n\n"
        'To use the prompt_toolkit shell you need to have the prompt_toolkit '
        '(https://github.com/jonathanslenders/python-prompt-toolkit) '
        'library installed. To specify which shell should be used, do so in '
        'the run control file.'),
    'SUGGEST_COMMANDS': VarDocs(
        'When a user types an invalid command, xonsh will try to offer '
        'suggestions of similar valid commands if this is True.'),
    'SUGGEST_MAX_NUM': VarDocs(
        'xonsh will show at most this many suggestions in response to an '
        'invalid command. If negative, there is no limit to how many '
        'suggestions are shown.'),
    'SUGGEST_THRESHOLD': VarDocs(
        'An error threshold. If the Levenshtein distance between the entered '
        'command and a valid command is less than this value, the valid '
        'command will be offered as a suggestion.'),
    'TEEPTY_PIPE_DELAY': VarDocs(
        'The number of [seconds] to delay a spawned process if it has '
        'information being piped in via stdin. This value must be a float. '
        'If a value less than or equal to zero is passed in, no delay is '
        'used. This can be used to fix situations where a spawned process, '
        'such as piping into \'grep\', exits too quickly for the piping '
        'operation itself. TeePTY (and thus this variable) are currently '
        'only used when $XONSH_STORE_STDOUT is True.',
        configurable=ON_LINUX),
    'TERM': VarDocs(
        'TERM is sometimes set by the terminal emulator. This is used (when '
        "valid) to determine whether or not to set the title. Users shouldn't "
        "need to set this themselves. Note that this variable should be set as "
        "early as possible in order to ensure it is effective. Here are a few "
        "options:\n\n"
        "* Set this from the program that launches xonsh. On posix systems, \n"
        "  this can be performed by using env, e.g. \n"
        "  '/usr/bin/env TERM=xterm-color xonsh' or similar.\n"
        "* From the xonsh command line, namely 'xonsh -DTERM=xterm-color'.\n"
        "* In the config file with '{\"env\": {\"TERM\": \"xterm-color\"}}'.\n"
        "* Lastly, in xonshrc with '$TERM'\n\n"
        "Ideally, your terminal emulator will set this correctly but that does "
        "not always happen.", configurable=False),
    'TITLE': VarDocs(
        'The title text for the window in which xonsh is running. Formatted '
        "in the same manner as $PROMPT, see 'Customizing the Prompt' "
        'http://xon.sh/tutorial.html#customizing-the-prompt.',
        default='xonsh.environ.DEFAULT_TITLE'),
    'UPDATE_OS_ENVIRON': VarDocs("If True os.environ will always be updated "
        "when the xonsh environment changes. The environment can be reset to "
        "the default value by calling '__xonsh_env__.undo_replace_env()'"),
    'VI_MODE': VarDocs(
        "Flag to enable 'vi_mode' in the 'prompt_toolkit' shell."),
    'VIRTUAL_ENV': VarDocs(
        'Path to the currently active Python environment.', configurable=False),
    'WIN_UNICODE_CONSOLE': VarDocs(
        "Enables unicode support in windows terminals. Requires the external "
        "library 'win_unicode_console'.",
        configurable=ON_WINDOWS),
    'XDG_CONFIG_HOME': VarDocs(
        'Open desktop standard configuration home dir. This is the same '
        'default as used in the standard.', configurable=False,
        default="'~/.config'"),
    'XDG_DATA_HOME': VarDocs(
        'Open desktop standard data home dir. This is the same default as '
        'used in the standard.', default="'~/.local/share'"),
    'XONSHCONFIG': VarDocs(
        'The location of the static xonsh configuration file, if it exists. '
        'This is in JSON format.', configurable=False,
        default="'$XONSH_CONFIG_DIR/config.json'"),
    'XONSHRC': VarDocs(
        'A tuple of the locations of run control files, if they exist.  User '
        'defined run control file will supersede values set in system-wide '
        'control file if there is a naming collision.', default=(
        "On Linux & Mac OSX: ('/etc/xonshrc', '~/.xonshrc')\n"
        "On Windows: ('%ALLUSERSPROFILE%\\xonsh\\xonshrc', '~/.xonshrc')")),
    'XONSH_CACHE_SCRIPTS': VarDocs(
        'Controls whether the code for scripts run from xonsh will be cached'
        ' (``True``) or re-compiled each time (``False``).'),
    'XONSH_CACHE_EVERYTHING': VarDocs(
        'Controls whether all code (including code enetered at the interactive'
        ' prompt) will be cached.'),
    'XONSH_COLOR_STYLE': VarDocs(
        'Sets the color style for xonsh colors. This is a style name, not '
        'a color map.'),
    'XONSH_CONFIG_DIR': VarDocs(
        'This is the location where xonsh configuration information is stored.',
        configurable=False, default="'$XDG_CONFIG_HOME/xonsh'"),
    'XONSH_DATA_DIR': VarDocs(
        'This is the location where xonsh data files are stored, such as '
        'history.', default="'$XDG_DATA_HOME/xonsh'"),
    'XONSH_ENCODING': VarDocs(
        'This is the encoding that xonsh should use for subrpocess operations.',
        default='sys.getdefaultencoding()'),
    'XONSH_ENCODING_ERRORS': VarDocs(
        'The flag for how to handle encoding errors should they happen. '
        'Any string flag that has been previously registered with Python '
        "is allowed. See the 'Python codecs documentation' "
        "(https://docs.python.org/3/library/codecs.html#error-handlers) "
        'for more information and available options.',
        default="'surrogateescape'"),
    'XONSH_HISTORY_FILE': VarDocs('Location of history file (deprecated).',
        configurable=False, default="'~/.xonsh_history'"),
    'XONSH_HISTORY_SIZE': VarDocs(
        'Value and units tuple that sets the size of history after garbage '
        'collection. Canonical units are:\n\n'
        "- 'commands' for the number of past commands executed,\n"
        "- 'files' for the number of history files to keep,\n"
        "- 's' for the number of seconds in the past that are allowed, and\n"
        "- 'b' for the number of bytes that history may consume.\n\n"
        "Common abbreviations, such as '6 months' or '1 GB' are also allowed.",
        default="(8128, 'commands') or '8128 commands'"),
    'XONSH_INTERACTIVE': VarDocs(
        'True if xonsh is running interactively, and False otherwise.',
        configurable=False),
    'XONSH_LOGIN': VarDocs(
        'True if xonsh is running as a login shell, and False otherwise.',
        configurable=False),
    'XONSH_SHOW_TRACEBACK': VarDocs(
        'Controls if a traceback is shown if exceptions occur in the shell. '
        'Set to True to always show traceback or False to always hide. '
        'If undefined then the traceback is hidden but a notice is shown on how '
        'to enable the full traceback.'),
    'XONSH_STORE_STDIN': VarDocs(
        'Whether or not to store the stdin that is supplied to the !() and ![] '
        'operators.'),
    'XONSH_STORE_STDOUT': VarDocs(
        'Whether or not to store the stdout and stderr streams in the '
        'history files.'),
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
        self._orig_env = None
        self.ensurers = {k: Ensurer(*v) for k, v in DEFAULT_ENSURERS.items()}
        self.defaults = DEFAULT_VALUES
        self.docs = DEFAULT_DOCS
        if len(args) == 0 and len(kwargs) == 0:
            args = (os.environ, )
        for key, val in dict(*args, **kwargs).items():
            self[key] = val
        self._detyped = None

    @staticmethod
    def detypeable(val):
        return not (callable(val) or isinstance(val, MutableMapping))

    def detype(self):
        if self._detyped is not None:
            return self._detyped
        ctx = {}
        for key, val in self._d.items():
            if not self.detypeable(val):
                continue
            if not isinstance(key, str):
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
            if isinstance(k, str):
                continue
            if k.match(key) is not None:
                break
        else:
            ensurer = default
        self.ensurers[key] = ensurer
        return ensurer

    def get_docs(self, key, default=VarDocs('<no documentation>')):
        """Gets the documentation for the environment variable."""
        vd = self.docs.get(key, None)
        if vd is None:
            return default
        if vd.default is DefaultNotGiven:
            dval = pformat(self.defaults.get(key, '<default not set>'))
            vd = vd._replace(default=dval)
            self.docs[key] = vd
        return vd

    @contextmanager
    def swap(self, other=None, **kwargs):
        """Provides a context manager for temporarily swapping out certain
        environment variables with other values. On exit from the context
        manager, the original values are restored.
        """
        old = {}

        # single positional argument should be a dict-like object
        if other is not None:
            for k, v in other.items():
                old[k] = self.get(k, NotImplemented)
                self[k] = v

        # kwargs could also have been sent in
        for k, v in kwargs.items():
            old[k] = self.get(k, NotImplemented)
            self[k] = v

        yield self

        # restore the values
        for k, v in old.items():
            if v is NotImplemented:
                del self[k]
            else:
                self[k] = v


    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        if key is Ellipsis:
            return self
        m = self._arg_regex.match(key)
        if (m is not None) and (key not in self._d) and ('ARGS' in self._d):
            args = self._d['ARGS']
            ix = int(m.group(1))
            if ix >= len(args):
                e = "Not enough arguments given to access ARG{0}."
                raise KeyError(e.format(ix))
            val = self._d['ARGS'][ix]
        elif key in self._d:
            val = self._d[key]
        elif key in self.defaults:
            val = self.defaults[key]
            if is_callable_default(val):
                val = val(self)
        else:
            e = "Unknown environment variable: ${}"
            raise KeyError(e.format(key))
        if isinstance(val, (MutableSet, MutableSequence, MutableMapping)):
            self._detyped = None
        return val

    def __setitem__(self, key, val):
        ensurer = self.get_ensurer(key)
        if not ensurer.validate(val):
            val = ensurer.convert(val)
        self._d[key] = val
        if self.detypeable(val):
            self._detyped = None
            if self.get('UPDATE_OS_ENVIRON'):
                if self._orig_env is None:
                    self.replace_env()
                else:
                    os.environ[key] = ensurer.detype(val)

    def __delitem__(self, key):
        val = self._d.pop(key)
        if self.detypeable(val):
            self._detyped = None
            if self.get('UPDATE_OS_ENVIRON') and key in os.environ:
                del os.environ[key]

    def get(self, key, default=None):
        """The environment will look up default values from its own defaults if a
        default is not given here.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        yield from (set(self._d) | set(self.defaults))

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


def _is_executable_file(path):
    """Checks that path is an executable regular file, or a symlink towards one.
    This is roughly ``os.path isfile(path) and os.access(path, os.X_OK)``.

    This function was forked from pexpect originally:

    Copyright (c) 2013-2014, Pexpect development team
    Copyright (c) 2012, Noah Spurrier <noah@noah.org>

    PERMISSION TO USE, COPY, MODIFY, AND/OR DISTRIBUTE THIS SOFTWARE FOR ANY
    PURPOSE WITH OR WITHOUT FEE IS HEREBY GRANTED, PROVIDED THAT THE ABOVE
    COPYRIGHT NOTICE AND THIS PERMISSION NOTICE APPEAR IN ALL COPIES.
    THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
    WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
    MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
    ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
    WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
    ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
    OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
    """
    # follow symlinks,
    fpath = os.path.realpath(path)

    if not os.path.isfile(fpath):
        # non-files (directories, fifo, etc.)
        return False

    return os.access(fpath, os.X_OK)


def yield_executables_windows(directory, name):
    normalized_name = os.path.normcase(name)
    extensions = builtins.__xonsh_env__.get('PATHEXT')
    try:
        names = os.listdir(directory)
    except PermissionError:
        return
    for a_file in names:
        normalized_file_name = os.path.normcase(a_file)
        base_name, ext = os.path.splitext(normalized_file_name)

        if (
            normalized_name == base_name or normalized_name == normalized_file_name
        ) and ext.upper() in extensions:
            yield os.path.join(directory, a_file)


def yield_executables_posix(directory, name):
    try:
        names = os.listdir(directory)
    except PermissionError:
        return
    if name in names:
        path = os.path.join(directory, name)
        if _is_executable_file(path):
            yield path


yield_executables = yield_executables_windows if ON_WINDOWS else yield_executables_posix


def locate_binary(name):
    if os.path.isfile(name) and name != os.path.basename(name):
        return name

    directories = builtins.__xonsh_env__.get('PATH')

    # Windows users expect t obe able to execute files in the same directory without `./`
    if ON_WINDOWS:
        directories = [_get_cwd()] + directories

    try:
        return next(chain.from_iterable(yield_executables(directory, name) for
                    directory in directories if os.path.isdir(directory)))
    except StopIteration:
        return None


def _get_parent_dir_for(path, dir_name):
    # walk up the directory tree to see if we are inside an hg repo
    previous_path = ''
    while path != previous_path:
        if os.path.isdir(os.path.join(path, dir_name)):
            return path

        previous_path = path
        path, _ = os.path.split(path)

    return False


def ensure_git(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cwd = kwargs.get('cwd', _get_cwd())
        if cwd is None:
            return

        # step out completely if git is not installed
        if locate_binary('git') is None:
            return

        root_path = _get_parent_dir_for(cwd, '.git')
        # Bail if we're not in a repo
        if not root_path:
            return

        kwargs['cwd'] = cwd

        return func(*args, **kwargs)
    return wrapper


def ensure_hg(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cwd = kwargs.get('cwd', _get_cwd())
        if cwd is None:
            return

        # step out completely if hg is not installed
        if locate_binary('hg') is None:
            return

        root_path = _get_parent_dir_for(cwd, '.hg')
        # Bail if we're not in a repo
        if not root_path:
            return

        kwargs['cwd'] = cwd
        kwargs['root'] = root_path

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
            if len(s) == 0:
                # Workaround for a bug in ConEMU/cmder
                # retry without redirection
                s = subprocess.check_output(cmd,
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
    hg_env = builtins.__xonsh_env__.detype()
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
            branch = 'default'

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


def git_dirty_working_directory(cwd=None, include_untracked=False):
    try:
        cmd = ['git', 'status', '--porcelain']
        if include_untracked:
            cmd.append('--untracked-files=normal')
        else:
            cmd.append('--untracked-files=no')
        s = subprocess.check_output(cmd,
                                    stderr=subprocess.PIPE,
                                    cwd=cwd,
                                    universal_newlines=True)
        if len(s) == 0:
            # Workaround for a bug in ConEMU/cmder
            # retry without redirection
            s = subprocess.check_output(cmd,
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
    return ('{BOLD_INTENSE_RED}' if dirty_working_directory() else
            '{BOLD_INTENSE_GREEN}')


def branch_bg_color():
    """Return red if the current branch is dirty, otherwise green"""
    return ('{BACKGROUND_RED}' if dirty_working_directory() else
            '{BACKGROUND_GREEN}')


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


def env_name(pre_chars='(', post_chars=') '):
    """Extract the current environment name from $VIRTUAL_ENV or
    $CONDA_DEFAULT_ENV if that is set
    """
    env_path = builtins.__xonsh_env__.get('VIRTUAL_ENV', '')
    if len(env_path) == 0 and ON_ANACONDA:
        pre_chars, post_chars = '[', '] '
        env_path = builtins.__xonsh_env__.get('CONDA_DEFAULT_ENV', '')
    env_name = os.path.basename(env_path)
    return pre_chars + env_name + post_chars if env_name else ''


if ON_WINDOWS:
    USER = 'USERNAME'
else:
    USER = 'USER'


FORMATTER_DICT = dict(
    user=os.environ.get(USER, '<user>'),
    prompt_end='#' if IS_SUPERUSER else '$',
    hostname=socket.gethostname().split('.', 1)[0],
    cwd=_replace_home_cwd,
    cwd_dir=lambda: os.path.dirname(_replace_home_cwd()),
    cwd_base=lambda: os.path.basename(_replace_home_cwd()),
    short_cwd=_collapsed_pwd,
    curr_branch=current_branch,
    branch_color=branch_color,
    branch_bg_color=branch_bg_color,
    current_job=_current_job,
    env_name=env_name,
    )

DEFAULT_VALUES['FORMATTER_DICT'] = dict(FORMATTER_DICT)

_FORMATTER = string.Formatter()


def is_template_string(template, formatter_dict=None):
    """Returns whether or not the string is a valid template."""
    template = template() if callable(template) else template
    try:
        included_names = set(i[1] for i in _FORMATTER.parse(template))
    except ValueError:
        return False
    included_names.discard(None)
    if formatter_dict is None:
        fmtter = builtins.__xonsh_env__.get('FORMATTER_DICT', FORMATTER_DICT)
    else:
        fmtter = formatter_dict
    known_names = set(fmtter.keys())
    return included_names <= known_names


def _get_fmtter(formatter_dict=None):
    if formatter_dict is None:
        fmtter = builtins.__xonsh_env__.get('FORMATTER_DICT', FORMATTER_DICT)
    else:
        fmtter = formatter_dict
    return fmtter


def format_prompt(template=DEFAULT_PROMPT, formatter_dict=None):
    """Formats a xonsh prompt template string."""
    template = template() if callable(template) else template
    fmtter = _get_fmtter(formatter_dict)
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


def partial_format_prompt(template=DEFAULT_PROMPT, formatter_dict=None):
    """Formats a xonsh prompt template string."""
    template = template() if callable(template) else template
    fmtter = _get_fmtter(formatter_dict)
    bopen = '{'
    bclose = '}'
    colon = ':'
    expl = '!'
    toks = []
    for literal, field, spec, conv in _FORMATTER.parse(template):
        toks.append(literal)
        if field is None:
            continue
        elif field.startswith('$'):
            v = builtins.__xonsh_env__[name[1:]]  # FIXME `name` is an unresolved ref
            v = _FORMATTER.convert_field(v, conv)
            v = _FORMATTER.format_field(v, spec)
            toks.append(v)
            continue
        elif field in fmtter:
            v = fmtter[field]
            val = v() if callable(v) else v
            val = '' if val is None else val
            toks.append(val)
        else:
            toks.append(bopen)
            toks.append(field)
            if conv is not None and len(conv) > 0:
                toks.append(expl)
                toks.append(conv)
            if spec is not None and len(spec) > 0:
                toks.append(colon)
                toks.append(spec)
            toks.append(bclose)
    return ''.join(toks)


RE_HIDDEN = re.compile('\001.*?\002')

def multiline_prompt(curr=''):
    """Returns the filler text for the prompt in multiline scenarios."""
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

def load_static_config(ctx, config=None):
    """Loads a static configuration file from a given context, rather than the
    current environment.  Optionally may pass in configuration file name.
    """
    env = {}
    env['XDG_CONFIG_HOME'] = ctx.get('XDG_CONFIG_HOME',
                                     DEFAULT_VALUES['XDG_CONFIG_HOME'])
    env['XONSH_CONFIG_DIR'] = ctx['XONSH_CONFIG_DIR'] if 'XONSH_CONFIG_DIR' in ctx \
                              else xonsh_config_dir(env)
    if config is not None:
        env['XONSHCONFIG'] = ctx['XONSHCONFIG'] = config
    elif 'XONSHCONFIG' in ctx:
        config = env['XONSHCONFIG'] = ctx['XONSHCONFIG']
    else:
        # don't set in ctx in order to maintain default
        config = env['XONSHCONFIG'] = xonshconfig(env)
    if os.path.isfile(config):
        # Note that an Env instance at __xonsh_env__ has not been started yet,
        # per se, so we have to use os.environ
        encoding = os.environ.get('XONSH_ENCODING',
                                  DEFAULT_VALUES.get('XONSH_ENCODING', 'utf8'))
        errors = os.environ.get('XONSH_ENCODING_ERRORS',
                                DEFAULT_VALUES.get('XONSH_ENCODING_ERRORS',
                                                   'surrogateescape'))
        with open(config, 'r', encoding=encoding, errors=errors) as f:
            try:
                conf = json.load(f)
                assert isinstance(conf, Mapping)
                ctx['LOADED_CONFIG'] = True
            except Exception as e:
                conf = {}
                ctx['LOADED_CONFIG'] = False
                print_exception()
                # JSONDecodeError was added in Python v3.5
                jerr = json.JSONDecodeError \
                       if hasattr(json, 'JSONDecodeError') else ValueError
                if isinstance(e, jerr):
                    msg = 'Xonsh config file is not valid JSON.'
                else:
                    msg = 'Could not load xonsh config.'
                print(msg, file=sys.stderr)
    else:
        conf = {}
        ctx['LOADED_CONFIG'] = False
    builtins.__xonsh_config__ = conf
    return conf


def xonshrc_context(rcfiles=None, execer=None):
    """Attempts to read in xonshrc file, and return the contents."""
    loaded = builtins.__xonsh_env__['LOADED_RC_FILES'] = []
    if rcfiles is None or execer is None:
        return {}
    env = {}
    for rcfile in rcfiles:
        if not os.path.isfile(rcfile):
            loaded.append(False)
            continue
        try:
            run_script_with_cache(rcfile, execer, env)
            loaded.append(True)
        except SyntaxError as err:
            loaded.append(False)
            msg = 'syntax error in xonsh run control file {0!r}: {1!s}'
            warn(msg.format(rcfile, err), RuntimeWarning)
            continue
    return env


def windows_foreign_env_fixes(ctx):
    """Environment fixes for Windows. Operates in-place."""
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


def default_env(env=None, config=None, login=True):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = dict(BASE_ENV)
    ctx.update(os.environ)
    if ON_WINDOWS:
        # Windows style PROMPT definitions don't work in XONSH:
        try:
            del ctx['PROMPT']
        except KeyError:
            pass

    if login:
        conf = load_static_config(ctx, config=config)

        foreign_env = load_foreign_envs(shells=conf.get('foreign_shells', DEFAULT_SHELLS),
                                        issue_warning=False)
        if ON_WINDOWS:
            windows_foreign_env_fixes(foreign_env)

        ctx.update(foreign_env)

        # Do static config environment last, to allow user to override any of
        # our environment choices
        ctx.update(conf.get('env', ()))

    # finalize env
    if env is not None:
        ctx.update(env)
    return ctx
