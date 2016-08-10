# -*- coding: utf-8 -*-
"""Environment for the xonsh shell."""
import os
import re
import sys
import time
import json
import socket
import shutil
import string
import pprint
import locale
import builtins
import warnings
import traceback
import itertools
import contextlib
import subprocess
import collections
import collections.abc as abc

from xonsh import __version__ as XONSH_VERSION
from xonsh.jobs import get_next_task
from xonsh.lazyasd import LazyObject, lazyobject
from xonsh.codecache import run_script_with_cache
from xonsh.dirstack import _get_cwd
from xonsh.foreign_shells import load_foreign_envs
from xonsh.platform import (
    BASH_COMPLETIONS_DEFAULT, DEFAULT_ENCODING, PATH_DEFAULT,
    ON_WINDOWS, ON_ANACONDA, ON_LINUX, ON_CYGWIN,
)
from xonsh.tools import (
    is_superuser, always_true, always_false, ensure_string, is_env_path,
    str_to_env_path, env_path_to_str, is_bool, to_bool, bool_to_str,
    is_history_tuple, to_history_tuple, history_tuple_to_str, is_float,
    is_string, is_string_or_callable,
    is_completions_display_value, to_completions_display_value,
    is_string_set, csv_to_set, set_to_csv, get_sep, is_int, is_bool_seq,
    to_bool_or_int, bool_or_int_to_str,
    csv_to_bool_seq, bool_seq_to_csv, DefaultNotGiven, print_exception,
    setup_win_unicode_console, intensify_colors_on_win_setter, format_color,
    is_dynamic_cwd_width, to_dynamic_cwd_tuple, dynamic_cwd_tuple_to_str,
    is_logfile_opt, to_logfile_opt, logfile_opt_to_str, executables_in,
    is_nonstring_seq_of_strings, pathsep_to_upper_seq,
    seq_to_upper_pathsep,
)


@lazyobject
def LOCALE_CATS():
    lc = {'LC_CTYPE': locale.LC_CTYPE,
          'LC_COLLATE': locale.LC_COLLATE,
          'LC_NUMERIC': locale.LC_NUMERIC,
          'LC_MONETARY': locale.LC_MONETARY,
          'LC_TIME': locale.LC_TIME,
          }
    if hasattr(locale, 'LC_MESSAGES'):
        lc['LC_MESSAGES'] = locale.LC_MESSAGES
    return lc


def locale_convert(key):
    """Creates a converter for a locale key."""

    def lc_converter(val):
        try:
            locale.setlocale(LOCALE_CATS[key], val)
            val = locale.setlocale(LOCALE_CATS[key])
        except (locale.Error, KeyError):
            msg = 'Failed to set locale {0!r} to {1!r}'.format(key, val)
            warnings.warn(msg, RuntimeWarning)
        return val

    return lc_converter


def to_debug(x):
    """Converts value using to_bool_or_int() and sets this value on as the
    execer's debug level.
    """
    val = to_bool_or_int(x)
    if hasattr(builtins, '__xonsh_execer__'):
        builtins.__xonsh_execer__.debug_level = val
    return val


Ensurer = collections.namedtuple('Ensurer', ['validate', 'convert', 'detype'])
Ensurer.__doc__ = """Named tuples whose elements are functions that
represent environment variable validation, conversion, detyping.
"""


@lazyobject
def DEFAULT_ENSURERS():
    return {
    'AUTO_CD': (is_bool, to_bool, bool_to_str),
    'AUTO_PUSHD': (is_bool, to_bool, bool_to_str),
    'AUTO_SUGGEST': (is_bool, to_bool, bool_to_str),
    'BASH_COMPLETIONS': (is_env_path, str_to_env_path, env_path_to_str),
    'CASE_SENSITIVE_COMPLETIONS': (is_bool, to_bool, bool_to_str),
    re.compile('\w*DIRS$'): (is_env_path, str_to_env_path, env_path_to_str),
    'COLOR_INPUT': (is_bool, to_bool, bool_to_str),
    'COLOR_RESULTS': (is_bool, to_bool, bool_to_str),
    'COMPLETIONS_DISPLAY': (is_completions_display_value,
                            to_completions_display_value, str),
    'COMPLETIONS_MENU_ROWS': (is_int, int, str),
    'DYNAMIC_CWD_WIDTH': (is_dynamic_cwd_width, to_dynamic_cwd_tuple,
                          dynamic_cwd_tuple_to_str),
    'FORCE_POSIX_PATHS': (is_bool, to_bool, bool_to_str),
    'FUZZY_PATH_COMPLETION': (is_bool, to_bool, bool_to_str),
    'GLOB_SORTED': (is_bool, to_bool, bool_to_str),
    'HISTCONTROL': (is_string_set, csv_to_set, set_to_csv),
    'IGNOREEOF': (is_bool, to_bool, bool_to_str),
    'INTENSIFY_COLORS_ON_WIN': (always_false, intensify_colors_on_win_setter,
                                bool_to_str),
    'LANG': (is_string, ensure_string, ensure_string),
    'LC_COLLATE': (always_false, locale_convert('LC_COLLATE'), ensure_string),
    'LC_CTYPE': (always_false, locale_convert('LC_CTYPE'), ensure_string),
    'LC_MESSAGES': (always_false, locale_convert('LC_MESSAGES'), ensure_string),
    'LC_MONETARY': (always_false, locale_convert('LC_MONETARY'), ensure_string),
    'LC_NUMERIC': (always_false, locale_convert('LC_NUMERIC'), ensure_string),
    'LC_TIME': (always_false, locale_convert('LC_TIME'), ensure_string),
    'LOADED_CONFIG': (is_bool, to_bool, bool_to_str),
    'LOADED_RC_FILES': (is_bool_seq, csv_to_bool_seq, bool_seq_to_csv),
    'MOUSE_SUPPORT': (is_bool, to_bool, bool_to_str),
    'MULTILINE_PROMPT': (is_string_or_callable, ensure_string, ensure_string),
    re.compile('\w*PATH$'): (is_env_path, str_to_env_path, env_path_to_str),
    'PATHEXT': (is_nonstring_seq_of_strings, pathsep_to_upper_seq,
                seq_to_upper_pathsep),
    'PRETTY_PRINT_RESULTS': (is_bool, to_bool, bool_to_str),
    'PROMPT': (is_string_or_callable, ensure_string, ensure_string),
    'RAISE_SUBPROC_ERROR': (is_bool, to_bool, bool_to_str),
    'RIGHT_PROMPT': (is_string_or_callable, ensure_string, ensure_string),
    'SUBSEQUENCE_PATH_COMPLETION': (is_bool, to_bool, bool_to_str),
    'SUPPRESS_BRANCH_TIMEOUT_MESSAGE': (is_bool, to_bool, bool_to_str),
    'TEEPTY_PIPE_DELAY': (is_float, float, str),
    'UPDATE_OS_ENVIRON': (is_bool, to_bool, bool_to_str),
    'VC_BRANCH_TIMEOUT': (is_float, float, str),
    'VI_MODE': (is_bool, to_bool, bool_to_str),
    'VIRTUAL_ENV': (is_string, ensure_string, ensure_string),
    'WIN_UNICODE_CONSOLE': (always_false, setup_win_unicode_console, bool_to_str),
    'XONSHRC': (is_env_path, str_to_env_path, env_path_to_str),
    'XONSH_CACHE_SCRIPTS': (is_bool, to_bool, bool_to_str),
    'XONSH_CACHE_EVERYTHING': (is_bool, to_bool, bool_to_str),
    'XONSH_COLOR_STYLE': (is_string, ensure_string, ensure_string),
    'XONSH_DEBUG': (always_false, to_debug, bool_or_int_to_str),
    'XONSH_ENCODING': (is_string, ensure_string, ensure_string),
    'XONSH_ENCODING_ERRORS': (is_string, ensure_string, ensure_string),
    'XONSH_HISTORY_SIZE': (is_history_tuple, to_history_tuple, history_tuple_to_str),
    'XONSH_LOGIN': (is_bool, to_bool, bool_to_str),
    'XONSH_SHOW_TRACEBACK': (is_bool, to_bool, bool_to_str),
    'XONSH_STORE_STDOUT': (is_bool, to_bool, bool_to_str),
    'XONSH_STORE_STDIN': (is_bool, to_bool, bool_to_str),
    'XONSH_TRACEBACK_LOGFILE': (is_logfile_opt, to_logfile_opt, logfile_opt_to_str),
    'XONSH_DATETIME_FORMAT': (is_string, ensure_string, ensure_string),
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


def default_prompt():
    """Creates a new instance of the default prompt."""
    if ON_CYGWIN:
        dp = ('{env_name:{} }{BOLD_GREEN}{user}@{hostname}'
              '{BOLD_BLUE} {cwd} {prompt_end}{NO_COLOR} ')
    elif ON_WINDOWS:
        dp = ('{env_name:{} }'
              '{BOLD_INTENSE_GREEN}{user}@{hostname}{BOLD_INTENSE_CYAN} '
              '{cwd}{branch_color}{curr_branch: {}}{NO_COLOR} '
              '{BOLD_INTENSE_CYAN}{prompt_end}{NO_COLOR} ')
    else:
        dp = ('{env_name:{} }'
              '{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
              '{cwd}{branch_color}{curr_branch: {}}{NO_COLOR} '
              '{BOLD_BLUE}{prompt_end}{NO_COLOR} ')
    return dp


DEFAULT_PROMPT = LazyObject(default_prompt, globals(), 'DEFAULT_PROMPT')
DEFAULT_TITLE = '{current_job:{} | }{user}@{hostname}: {cwd} | xonsh'


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


def default_xonshrc():
    """Creates a new instance of the default xonshrc tuple."""
    if ON_WINDOWS:
        dxrc = (os.path.join(os.environ['ALLUSERSPROFILE'],
                             'xonsh', 'xonshrc'),
                os.path.expanduser('~/.xonshrc'))
    else:
        dxrc = ('/etc/xonshrc', os.path.expanduser('~/.xonshrc'))
    return dxrc


DEFAULT_XONSHRC = LazyObject(default_xonshrc, globals(), 'DEFAULT_XONSHRC')


# Default values should generally be immutable, that way if a user wants
# to set them they have to do a copy and write them to the environment.
# try to keep this sorted.
@lazyobject
def DEFAULT_VALUES():
    dv = {
        'AUTO_CD': False,
        'AUTO_PUSHD': False,
        'AUTO_SUGGEST': True,
        'BASH_COMPLETIONS': BASH_COMPLETIONS_DEFAULT,
        'CASE_SENSITIVE_COMPLETIONS': ON_LINUX,
        'CDPATH': (),
        'COLOR_INPUT': True,
        'COLOR_RESULTS': True,
        'COMPLETIONS_DISPLAY': 'multi',
        'COMPLETIONS_MENU_ROWS': 5,
        'DIRSTACK_SIZE': 20,
        'DYNAMIC_CWD_WIDTH': (float('inf'), 'c'),
        'EXPAND_ENV_VARS': True,
        'FORCE_POSIX_PATHS': False,
        'FORMATTER_DICT': dict(FORMATTER_DICT),
        'FUZZY_PATH_COMPLETION': True,
        'GLOB_SORTED': True,
        'HISTCONTROL': set(),
        'IGNOREEOF': False,
        'INDENT': '    ',
        'INTENSIFY_COLORS_ON_WIN': True,
        'LANG': 'C.UTF-8',
        'LC_CTYPE': locale.setlocale(locale.LC_CTYPE),
        'LC_COLLATE': locale.setlocale(locale.LC_COLLATE),
        'LC_TIME': locale.setlocale(locale.LC_TIME),
        'LC_MONETARY': locale.setlocale(locale.LC_MONETARY),
        'LC_NUMERIC': locale.setlocale(locale.LC_NUMERIC),
        'LOADED_CONFIG': False,
        'LOADED_RC_FILES': (),
        'MOUSE_SUPPORT': False,
        'MULTILINE_PROMPT': '.',
        'PATH': PATH_DEFAULT,
        'PATHEXT': ['.COM', '.EXE', '.BAT', '.CMD'] if ON_WINDOWS else [],
        'PRETTY_PRINT_RESULTS': True,
        'PROMPT': default_prompt(),
        'PUSHD_MINUS': False,
        'PUSHD_SILENT': False,
        'RAISE_SUBPROC_ERROR': False,
        'RIGHT_PROMPT': '',
        'SHELL_TYPE': 'best',
        'SUBSEQUENCE_PATH_COMPLETION': True,
        'SUPPRESS_BRANCH_TIMEOUT_MESSAGE': False,
        'SUGGEST_COMMANDS': True,
        'SUGGEST_MAX_NUM': 5,
        'SUGGEST_THRESHOLD': 3,
        'TEEPTY_PIPE_DELAY': 0.01,
        'TITLE': DEFAULT_TITLE,
        'UPDATE_OS_ENVIRON': False,
        'VC_BRANCH_TIMEOUT': 0.2 if ON_WINDOWS else 0.1,
        'VI_MODE': False,
        'WIN_UNICODE_CONSOLE': True,
        'XDG_CONFIG_HOME': os.path.expanduser(os.path.join('~', '.config')),
        'XDG_DATA_HOME': os.path.expanduser(os.path.join('~', '.local',
                                                         'share')),
        'XONSHCONFIG': xonshconfig,
        'XONSHRC': default_xonshrc(),
        'XONSH_CACHE_SCRIPTS': True,
        'XONSH_CACHE_EVERYTHING': False,
        'XONSH_COLOR_STYLE': 'default',
        'XONSH_CONFIG_DIR': xonsh_config_dir,
        'XONSH_DATA_DIR': xonsh_data_dir,
        'XONSH_DEBUG': False,
        'XONSH_ENCODING': DEFAULT_ENCODING,
        'XONSH_ENCODING_ERRORS': 'surrogateescape',
        'XONSH_HISTORY_FILE': os.path.expanduser('~/.xonsh_history.json'),
        'XONSH_HISTORY_SIZE': (8128, 'commands'),
        'XONSH_LOGIN': False,
        'XONSH_SHOW_TRACEBACK': False,
        'XONSH_STORE_STDIN': False,
        'XONSH_STORE_STDOUT': False,
        'XONSH_TRACEBACK_LOGFILE': None,
        'XONSH_DATETIME_FORMAT': '%Y-%m-%d %H:%M',
    }
    if hasattr(locale, 'LC_MESSAGES'):
        dv['LC_MESSAGES'] = locale.setlocale(locale.LC_MESSAGES)
    return dv


VarDocs = collections.namedtuple('VarDocs', ['docstr', 'configurable',
                                             'default', 'store_as_str'])
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
store_as_str : bool, optional
    Flag for whether the environment variable should be stored as a
    string. This is used when persisting a variable that is not JSON
    serializable to the config file. For example, sets, frozensets, and
    potentially other non-trivial data types. default, False.
"""
# iterates from back
VarDocs.__new__.__defaults__ = (True, DefaultNotGiven, False)


# Please keep the following in alphabetic order - scopatz
@lazyobject
def DEFAULT_DOCS():
    return {
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
    'COLOR_INPUT': VarDocs('Flag for syntax highlighting interactive input.'),
    'COLOR_RESULTS': VarDocs('Flag for syntax highlighting return values.'),
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
    'DYNAMIC_CWD_WIDTH': VarDocs(
        'Maximum length in number of characters '
        'or as a percentage for the `cwd` prompt variable. For example, '
        '"20" is a twenty character width and "10%" is ten percent of the '
        'number of columns available.'),
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
    'FUZZY_PATH_COMPLETION': VarDocs(
        "Toggles 'fuzzy' matching of paths for tab completion, which is only "
        "used as a fallback if no other completions succeed but can be used "
        "as a way to adjust for typographical errors. If ``True``, then, e.g.,"
        " ``xonhs`` will match ``xonsh``."),
    'GLOB_SORTED': VarDocs(
        "Toggles whether globbing results are manually sorted. If ``False``, "
        "the results are returned in arbitrary order."),
    'HISTCONTROL': VarDocs(
        'A set of strings (comma-separated list in string form) of options '
        'that determine what commands are saved to the history list. By '
        "default all commands are saved. The option 'ignoredups' will not "
        "save the command if it matches the previous command. The option "
        "'ignoreerr' will cause any commands that fail (i.e. return non-zero "
        "exit status) to not be added to the history list.",
        store_as_str=True),
    'IGNOREEOF': VarDocs('Prevents Ctrl-D from exiting the shell.'),
    'INDENT': VarDocs('Indentation string for multiline input'),
    'INTENSIFY_COLORS_ON_WIN': VarDocs(
        'Enhance style colors for readability '
        'when using the default terminal (cmd.exe) on Windows. Blue colors, '
        'which are hard to read, are replaced with cyan. Other colors are '
        'generally replaced by their bright counter parts.',
        configurable=ON_WINDOWS),
    'LANG': VarDocs('Fallback locale setting for systems where it matters'),
    'LOADED_CONFIG': VarDocs(
        'Whether or not the xonsh config file was loaded',
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
    'PATHEXT': VarDocs('Sequence of extention strings (eg, ".EXE") for '
                       'filtering valid executables by. Each element must be '
                       'uppercase.'),
    'PRETTY_PRINT_RESULTS': VarDocs(
        'Flag for "pretty printing" return values.'),
    'PROMPT': VarDocs(
        'The prompt text. May contain keyword arguments which are '
        "auto-formatted, see 'Customizing the Prompt' at "
        'http://xon.sh/tutorial.html#customizing-the-prompt. '
        'This value is never inherited from parent processes.',
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
    'RIGHT_PROMPT': VarDocs(
        'Template string for right-aligned text '
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
    'SUBSEQUENCE_PATH_COMPLETION': VarDocs(
        "Toggles subsequence matching of paths for tab completion. "
        "If ``True``, then, e.g., ``~/u/ro`` can match ``~/lou/carcolh``."),
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
        'command will be offered as a suggestion.  Also used for "fuzzy" '
        'tab completion of paths.'),
    'SUPPRESS_BRANCH_TIMEOUT_MESSAGE': VarDocs(
        'Whether or not to supress branch timeout warning messages.'),
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
        "* Set this from the program that launches xonsh. On POSIX systems, \n"
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
    'UPDATE_OS_ENVIRON': VarDocs(
        "If True os.environ will always be updated "
        "when the xonsh environment changes. The environment can be reset to "
        "the default value by calling '__xonsh_env__.undo_replace_env()'"),
    'VC_BRANCH_TIMEOUT': VarDocs(
        'The timeout (in seconds) for version control '
        'branch computations. This is a timeout per subprocess call, so the '
        'total time to compute will be larger than this in many cases.'),
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
        'Controls whether all code (including code entered at the interactive'
        ' prompt) will be cached.'),
    'XONSH_COLOR_STYLE': VarDocs(
        'Sets the color style for xonsh colors. This is a style name, not '
        'a color map. Run ``xonfig styles`` to see the available styles.'),
    'XONSH_CONFIG_DIR': VarDocs(
        'This is the location where xonsh configuration information is stored.',
        configurable=False, default="'$XDG_CONFIG_HOME/xonsh'"),
    'XONSH_DEBUG': VarDocs(
        'Sets the xonsh debugging level. This may be an integer or a boolean, '
        'with higher values cooresponding to higher debuging levels and more '
        'information presented. Setting this variable prior to stating xonsh '
        'will supress amalgamated imports.', configurable=False),
    'XONSH_DATA_DIR': VarDocs(
        'This is the location where xonsh data files are stored, such as '
        'history.', default="'$XDG_DATA_HOME/xonsh'"),
    'XONSH_ENCODING': VarDocs(
        'This is the encoding that xonsh should use for subprocess operations.',
        default='sys.getdefaultencoding()'),
    'XONSH_ENCODING_ERRORS': VarDocs(
        'The flag for how to handle encoding errors should they happen. '
        'Any string flag that has been previously registered with Python '
        "is allowed. See the 'Python codecs documentation' "
        "(https://docs.python.org/3/library/codecs.html#error-handlers) "
        'for more information and available options.',
        default="'surrogateescape'"),
    'XONSH_HISTORY_FILE': VarDocs(
        'Location of history file (deprecated).',
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
    'XONSH_SOURCE': VarDocs(
        "When running a xonsh script, this variable contains the absolute path "
        "to the currently executing script's file.",
        configurable=False),
    'XONSH_STORE_STDIN': VarDocs(
        'Whether or not to store the stdin that is supplied to the !() and ![] '
        'operators.'),
    'XONSH_STORE_STDOUT': VarDocs(
        'Whether or not to store the stdout and stderr streams in the '
        'history files.'),
    'XONSH_TRACEBACK_LOGFILE': VarDocs(
        'Specifies a file to store the traceback log to, regardless of whether '
        'XONSH_SHOW_TRACEBACK has been set. Its value must be a writable file '
        'or None / the empty string if traceback logging is not desired. '
        'Logging to a file is not enabled by default.'),
    'XONSH_DATETIME_FORMAT': VarDocs(
        'The format that is used for ``datetime.strptime()`` in various places'
        'i.e the history timestamp option'),
    }


#
# actual environment
#

class Env(abc.MutableMapping):
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

    _arg_regex = None

    def __init__(self, *args, **kwargs):
        """If no initial environment is given, os.environ is used."""
        self._d = {}
        self._orig_env = None
        self._ensurers = {k: Ensurer(*v) for k, v in DEFAULT_ENSURERS.items()}
        self._defaults = DEFAULT_VALUES
        self._docs = DEFAULT_DOCS
        if len(args) == 0 and len(kwargs) == 0:
            args = (os.environ,)
        for key, val in dict(*args, **kwargs).items():
            self[key] = val
        if 'PATH' not in self._d:
            # this is here so the PATH is accessible to subprocs and so that
            # it can be modified in-place in the xonshrc file
            self._d['PATH'] = list(PATH_DEFAULT)
        self._detyped = None

    @property
    def arg_regex(self):
        if self._arg_regex is None:
            self._arg_regex = re.compile(r'ARG(\d+)')
        return self._arg_regex

    @staticmethod
    def detypeable(val):
        return not (callable(val) or isinstance(val, abc.MutableMapping))

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
        if key in self._ensurers:
            return self._ensurers[key]
        for k, ensurer in self._ensurers.items():
            if isinstance(k, str):
                continue
            if k.match(key) is not None:
                break
        else:
            ensurer = default
        self._ensurers[key] = ensurer
        return ensurer

    def get_docs(self, key, default=VarDocs('<no documentation>')):
        """Gets the documentation for the environment variable."""
        vd = self._docs.get(key, None)
        if vd is None:
            return default
        if vd.default is DefaultNotGiven:
            dval = pprint.pformat(self._defaults.get(key, '<default not set>'))
            vd = vd._replace(default=dval)
            self._docs[key] = vd
        return vd

    def is_manually_set(self, varname):
        """
        Checks if an environment variable has been manually set.
        """
        return varname in self._d

    @contextlib.contextmanager
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
        m = self.arg_regex.match(key)
        if (m is not None) and (key not in self._d) and ('ARGS' in self._d):
            args = self._d['ARGS']
            ix = int(m.group(1))
            if ix >= len(args):
                e = "Not enough arguments given to access ARG{0}."
                raise KeyError(e.format(ix))
            val = self._d['ARGS'][ix]
        elif key in self._d:
            val = self._d[key]
        elif key in self._defaults:
            val = self._defaults[key]
            if is_callable_default(val):
                val = val(self)
        else:
            e = "Unknown environment variable: ${}"
            raise KeyError(e.format(key))
        if isinstance(val, (abc.MutableSet, abc.MutableSequence,
                            abc.MutableMapping)):
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
        yield from (set(self._d) | set(self._defaults))

    def __contains__(self, item):
        return item in self._d or item in self._defaults

    def __len__(self):
        return len(self._d)

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return '{0}.{1}(...)'.format(self.__class__.__module__,
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


def _yield_executables(directory, name):
    if ON_WINDOWS:
        base_name, ext = os.path.splitext(name.lower())
        for fname in executables_in(directory):
            fbase, fext = os.path.splitext(fname.lower())
            if base_name == fbase and (len(ext) == 0 or ext == fext):
                yield os.path.join(directory, fname)
    else:
        for x in executables_in(directory):
            if x == name:
                yield os.path.join(directory, name)
                return


def locate_binary(name):
    """Locates an executable on the file system."""
    return builtins.__xonsh_commands_cache__.locate_binary(name)


def get_git_branch():
    """Attempts to find the current git branch.  If no branch is found, then
    an empty string is returned. If a timeout occured, the timeout exception
    (subprocess.TimeoutExpired) is returned.
    """
    branch = None
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    denv = env.detype()
    vcbt = env['VC_BRANCH_TIMEOUT']
    if not ON_WINDOWS:
        prompt_scripts = ['/usr/lib/git-core/git-sh-prompt',
                          '/usr/local/etc/bash_completion.d/git-prompt.sh']
        for script in prompt_scripts:
            # note that this is about 10x faster than bash -i "__git_ps1"
            inp = 'source {}; __git_ps1 "${{1:-%s}}"'.format(script)
            try:
                branch = subprocess.check_output(['bash'], cwd=cwd, input=inp,
                                                 stderr=subprocess.PIPE, timeout=vcbt, env=denv,
                                                 universal_newlines=True)
                break
            except subprocess.TimeoutExpired as e:
                branch = e
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    # fall back to using the git binary if the above failed
    if branch is None:
        cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        try:
            s = subprocess.check_output(cmd, cwd=cwd, timeout=vcbt, env=denv,
                                        stderr=subprocess.PIPE, universal_newlines=True)
            if ON_WINDOWS and len(s) == 0:
                # Workaround for a bug in ConEMU/cmder, retry without redirection
                s = subprocess.check_output(cmd, cwd=cwd, timeout=vcbt,
                                            env=denv, universal_newlines=True)
            branch = s.strip()
        except subprocess.TimeoutExpired as e:
            branch = e
        except (subprocess.CalledProcessError, FileNotFoundError):
            branch = None
    return branch


def _get_parent_dir_for(path, dir_name, timeout):
    # walk up the directory tree to see if we are inside an hg repo
    # the timeout makes sure that we don't thrash the file system
    previous_path = ''
    t0 = time.time()
    while path != previous_path and ((time.time() - t0) < timeout):
        if os.path.isdir(os.path.join(path, dir_name)):
            return path
        previous_path = path
        path, _ = os.path.split(path)
    return (path == previous_path)


def get_hg_branch(cwd=None, root=None):
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    root = _get_parent_dir_for(cwd, '.hg', env['VC_BRANCH_TIMEOUT'])
    if not isinstance(root, str):
        # Bail if we are not in a repo or we timed out
        if root:
            return None
        else:
            return subprocess.TimeoutExpired(['hg'], env['VC_BRANCH_TIMEOUT'])
    # get branch name
    branch_path = os.path.sep.join([root, '.hg', 'branch'])
    if os.path.exists(branch_path):
        with open(branch_path, 'r') as branch_file:
            branch = branch_file.read()
    else:
        branch = 'default'
    # add bookmark, if we can
    bookmark_path = os.path.sep.join([root, '.hg', 'bookmarks.current'])
    if os.path.exists(bookmark_path):
        with open(bookmark_path, 'r') as bookmark_file:
            active_bookmark = bookmark_file.read()
        branch = "{0}, {1}".format(*(b.strip(os.linesep) for b in
                                     (branch, active_bookmark)))
    else:
        branch = branch.strip(os.linesep)
    return branch


_FIRST_BRANCH_TIMEOUT = True


def _first_branch_timeout_message():
    global _FIRST_BRANCH_TIMEOUT
    sbtm = builtins.__xonsh_env__['SUPPRESS_BRANCH_TIMEOUT_MESSAGE']
    if not _FIRST_BRANCH_TIMEOUT or sbtm:
        return
    _FIRST_BRANCH_TIMEOUT = False
    print('xonsh: branch timeout: computing the branch name, color, or both '
          'timed out while formatting the prompt. You may avoid this by '
          'increaing the value of $VC_BRANCH_TIMEOUT or by removing branch '
          'fields, like {curr_branch}, from your $PROMPT. See the FAQ '
          'for more details. This message will be suppressed for the remainder '
          'of this session. To suppress this message permanently, set '
          '$SUPPRESS_BRANCH_TIMEOUT_MESSAGE = True in your xonshrc file.',
          file=sys.stderr)


def current_branch(pad=NotImplemented):
    """Gets the branch for a current working directory. Returns an empty string
    if the cwd is not a repository.  This currently only works for git and hg
    and should be extended in the future.  If a timeout occurred, the string
    '<branch-timeout>' is returned.
    """
    if pad is not NotImplemented:
        warnings.warn("The pad argument of current_branch has no effect now "
                      "and will be removed in the future")
    branch = None
    cmds = builtins.__xonsh_commands_cache__
    if cmds.lazy_locate_binary('git') or cmds.is_empty():
        branch = get_git_branch()
    if (cmds.lazy_locate_binary('hg') or cmds.is_empty()) and not branch:
        branch = get_hg_branch()
    if isinstance(branch, subprocess.TimeoutExpired):
        branch = '<branch-timeout>'
        _first_branch_timeout_message()
    return branch or None


def git_dirty_working_directory(cwd=None, include_untracked=False):
    """Returns whether or not the git directory is dirty. If this could not
    be determined (timeout, file not sound, etc.) then this returns None.
    """
    cmd = ['git', 'status', '--porcelain']
    if include_untracked:
        cmd.append('--untracked-files=normal')
    else:
        cmd.append('--untracked-files=no')
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    denv = env.detype()
    vcbt = env['VC_BRANCH_TIMEOUT']
    try:
        s = subprocess.check_output(cmd, stderr=subprocess.PIPE, cwd=cwd,
                                    timeout=vcbt, universal_newlines=True,
                                    env=denv)
        if ON_WINDOWS and len(s) == 0:
            # Workaround for a bug in ConEMU/cmder, retry without redirection
            s = subprocess.check_output(cmd, cwd=cwd, timeout=vcbt,
                                        env=denv, universal_newlines=True)
        return bool(s)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        return None


def hg_dirty_working_directory():
    """Computes whether or not the mercurial working directory is dirty or not.
    If this cannot be deterimined, None is returned.
    """
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    denv = env.detype()
    vcbt = env['VC_BRANCH_TIMEOUT']
    # Override user configurations settings and aliases
    denv['HGRCPATH'] = ''
    try:
        s = subprocess.check_output(['hg', 'identify', '--id'],
                                    stderr=subprocess.PIPE, cwd=cwd, timeout=vcbt,
                                    universal_newlines=True, env=denv)
        return s.strip(os.linesep).endswith('+')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        return None


def dirty_working_directory(cwd=None):
    """Returns a boolean as to whether there are uncommitted files in version
    control repository we are inside. If this cannot be determined, returns
    None. Currently supports git and hg.
    """
    dwd = None
    cmds = builtins.__xonsh_commands_cache__
    if cmds.lazy_locate_binary('git') or cmds.is_empty():
        dwd = git_dirty_working_directory()
    if (cmds.lazy_locate_binary('hg') or cmds.is_empty()) and (dwd is None):
        dwd = hg_dirty_working_directory()
    return dwd


def branch_color():
    """Return red if the current branch is dirty, yellow if the dirtiness can
    not be determined, and green if it clean. These are bold, intense colors
    for the foreground.
    """
    dwd = dirty_working_directory()
    if dwd is None:
        color = '{BOLD_INTENSE_YELLOW}'
    elif dwd:
        color = '{BOLD_INTENSE_RED}'
    else:
        color = '{BOLD_INTENSE_GREEN}'
    return color


def branch_bg_color():
    """Return red if the current branch is dirty, yellow if the dirtiness can
    not be determined, and green if it clean. These are bacground colors.
    """
    dwd = dirty_working_directory()
    if dwd is None:
        color = '{BACKGROUND_YELLOW}'
    elif dwd:
        color = '{BACKGROUND_RED}'
    else:
        color = '{BACKGROUND_GREEN}'
    return color


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


def _replace_home_cwd():
    return _replace_home(builtins.__xonsh_env__['PWD'])


def _collapsed_pwd():
    sep = get_sep()
    pwd = _replace_home_cwd().split(sep)
    l = len(pwd)
    leader = sep if l > 0 and len(pwd[0]) == 0 else ''
    base = [i[0] if ix != l - 1 else i for ix, i in enumerate(pwd) if len(i) > 0]
    return leader + sep.join(base)


def _dynamically_collapsed_pwd():
    """Return the compact current working directory.  It respects the
    environment variable DYNAMIC_CWD_WIDTH.
    """
    originial_path = _replace_home_cwd()
    target_width, units = builtins.__xonsh_env__['DYNAMIC_CWD_WIDTH']
    if target_width == float('inf'):
        return originial_path
    if (units == '%'):
        cols, _ = shutil.get_terminal_size()
        target_width = (cols * target_width) // 100
    sep = get_sep()
    pwd = originial_path.split(sep)
    last = pwd.pop()
    remaining_space = target_width - len(last)
    # Reserve space for separators
    remaining_space_for_text = remaining_space - len(pwd)
    parts = []
    for i in range(len(pwd)):
        part = pwd[i]
        part_len = int(min(len(part), max(1, remaining_space_for_text // (len(pwd) - i))))
        remaining_space_for_text -= part_len
        reduced_part = part[0:part_len]
        parts.append(reduced_part)
    parts.append(last)
    full = sep.join(parts)
    # If even if displaying one letter per dir we are too long
    if (len(full) > target_width):
        # We truncate the left most part
        full = "..." + full[int(-target_width) + 3:]
        # if there is not even a single separator we still
        # want to display at least the beginning of the directory
        if full.find(sep) == -1:
            full = ("..." + sep + last)[0:int(target_width)]
    return full


def _current_job():
    j = get_next_task()
    if j is not None:
        if not j['bg']:
            cmd = j['cmds'][-1]
            s = cmd[0]
            if s == 'sudo' and len(cmd) > 1:
                s = cmd[1]
            return s


def env_name(pre_chars='(', post_chars=')'):
    """Extract the current environment name from $VIRTUAL_ENV or
    $CONDA_DEFAULT_ENV if that is set
    """
    env_path = builtins.__xonsh_env__.get('VIRTUAL_ENV', '')
    if len(env_path) == 0 and ON_ANACONDA:
        env_path = builtins.__xonsh_env__.get('CONDA_DEFAULT_ENV', '')
    env_name = os.path.basename(env_path)
    if env_name:
        return pre_chars + env_name + post_chars


if ON_WINDOWS:
    USER = 'USERNAME'
else:
    USER = 'USER'


def vte_new_tab_cwd():
    """This prints an escape squence that tells VTE terminals the hostname
    and pwd. This should not be needed in most cases, but sometimes is for
    certain Linux terminals that do not read the PWD from the environment
    on startup. Note that this does not return a string, it simply prints
    and flushes the escape sequence to stdout directly.
    """
    env = builtins.__xonsh_env__
    t = '\033]7;file://{}{}\007'
    s = t.format(env.get('HOSTNAME'), env.get('PWD'))
    print(s, end='', flush=True)


FORMATTER_DICT = LazyObject(lambda: dict(
    user=os.environ.get(USER, '<user>'),
    prompt_end='#' if is_superuser() else '$',
    hostname=socket.gethostname().split('.', 1)[0],
    cwd=_dynamically_collapsed_pwd,
    cwd_dir=lambda: os.path.dirname(_replace_home_cwd()),
    cwd_base=lambda: os.path.basename(_replace_home_cwd()),
    short_cwd=_collapsed_pwd,
    curr_branch=current_branch,
    branch_color=branch_color,
    branch_bg_color=branch_bg_color,
    current_job=_current_job,
    env_name=env_name,
    vte_new_tab_cwd=vte_new_tab_cwd,
), globals(), 'FORMATTER_DICT')

_FORMATTER = LazyObject(string.Formatter, globals(), '_FORMATTER')


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


def _failover_template_format(template):
    if callable(template):
        try:
            # Exceptions raises from function of producing $PROMPT
            # in user's xonshrc should not crash xonsh
            return template()
        except Exception:
            print_exception()
            return '$ '
    return template


def partial_format_prompt(template=DEFAULT_PROMPT, formatter_dict=None):
    """Formats a xonsh prompt template string."""
    try:
        return _partial_format_prompt_main(template=template,
                                           formatter_dict=formatter_dict)
    except Exception:
        return _failover_template_format(template)


def _partial_format_prompt_main(template=DEFAULT_PROMPT, formatter_dict=None):
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
            val = builtins.__xonsh_env__[field[1:]]
            val = _format_value(val, spec, conv)
            toks.append(val)
        elif field in fmtter:
            v = fmtter[field]
            val = v() if callable(v) else v
            val = _format_value(val, spec, conv)
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


def _format_value(val, spec, conv):
    """Formats a value from a template string {val!conv:spec}. The spec is
    applied as a format string itself, but if the value is None, the result
    will be empty. The purpose of this is to allow optional parts in a
    prompt string. For example, if the prompt contains '{current_job:{} | }',
    and 'current_job' returns 'sleep', the result is 'sleep | ', and if
    'current_job' returns None, the result is ''.
    """
    if val is None:
        return ''
    val = _FORMATTER.convert_field(val, conv)
    if spec:
        val = _FORMATTER.format(spec, val)
    return val


RE_HIDDEN = LazyObject(lambda: re.compile('\001.*?\002'), globals(),
                       'RE_HIDDEN')


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
    tokstr = format_color(dots, hide=True)
    baselen = 0
    basetoks = []
    for x in tokstr.split('\001'):
        pre, sep, post = x.partition('\002')
        if len(sep) == 0:
            basetoks.append(('', pre))
            baselen += len(pre)
        else:
            basetoks.append(('\001' + pre + '\002', post))
            baselen += len(post)
    if baselen == 0:
        return format_color('{NO_COLOR}' + tail, hide=True)
    toks = basetoks * (headlen // baselen)
    n = headlen % baselen
    count = 0
    for tok in basetoks:
        slen = len(tok[1])
        newcount = slen + count
        if slen == 0:
            continue
        elif newcount <= n:
            toks.append(tok)
        else:
            toks.append((tok[0], tok[1][:n-count]))
        count = newcount
        if n <= count:
            break
    toks.append((format_color('{NO_COLOR}', hide=True), tail))
    rtn = ''.join(itertools.chain.from_iterable(toks))
    return rtn


BASE_ENV = LazyObject(lambda: {
    'BASH_COMPLETIONS': list(DEFAULT_VALUES['BASH_COMPLETIONS']),
    'FORMATTER_DICT': dict(DEFAULT_VALUES['FORMATTER_DICT']),
    'XONSH_VERSION': XONSH_VERSION,
}, globals(), 'BASE_ENV')


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
                assert isinstance(conf, abc.Mapping)
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


def xonshrc_context(rcfiles=None, execer=None, initial=None):
    """Attempts to read in xonshrc file, and return the contents."""
    loaded = builtins.__xonsh_env__['LOADED_RC_FILES'] = []
    if initial is None:
        env = {}
    else:
        env = initial
    if rcfiles is None or execer is None:
        return env
    env['XONSHRC'] = tuple(rcfiles)
    for rcfile in rcfiles:
        if not os.path.isfile(rcfile):
            loaded.append(False)
            continue
        try:
            run_script_with_cache(rcfile, execer, env)
            loaded.append(True)
        except SyntaxError as err:
            loaded.append(False)
            exc = traceback.format_exc()
            msg = '{0}\nsyntax error in xonsh run control file {1!r}: {2!s}'
            warnings.warn(msg.format(exc, rcfile, err), RuntimeWarning)
            continue
        except Exception as err:
            loaded.append(False)
            exc = traceback.format_exc()
            msg = '{0}\nerror running xonsh run control file {1!r}: {2!s}'
            warnings.warn(msg.format(exc, rcfile, err), RuntimeWarning)
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
    ctx['PWD'] = _get_cwd() or ''


def foreign_env_fixes(ctx):
    """Environment fixes for all operating systems"""
    if 'PROMPT' in ctx:
        del ctx['PROMPT']


def default_env(env=None, config=None, login=True):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = dict(BASE_ENV)
    ctx.update(os.environ)
    ctx['PWD'] = _get_cwd() or ''
    # other shells' PROMPT definitions generally don't work in XONSH:
    try:
        del ctx['PROMPT']
    except KeyError:
        pass
    if login:
        conf = load_static_config(ctx, config=config)
        foreign_env = load_foreign_envs(shells=conf.get('foreign_shells', ()),
                                        issue_warning=False)
        if ON_WINDOWS:
            windows_foreign_env_fixes(foreign_env)
        foreign_env_fixes(foreign_env)
        ctx.update(foreign_env)
        # Do static config environment last, to allow user to override any of
        # our environment choices
        ctx.update(conf.get('env', ()))
    # finalize env
    if env is not None:
        ctx.update(env)
    return ctx
