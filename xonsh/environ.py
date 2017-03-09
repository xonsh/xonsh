# -*- coding: utf-8 -*-
"""Environment for the xonsh shell."""
import os
import re
import sys
import json
import pprint
import textwrap
import locale
import builtins
import warnings
import contextlib
import collections
import collections.abc as cabc

from xonsh import __version__ as XONSH_VERSION
from xonsh.lazyasd import LazyObject, lazyobject
from xonsh.codecache import run_script_with_cache
from xonsh.dirstack import _get_cwd
from xonsh.events import events
from xonsh.foreign_shells import load_foreign_envs, load_foreign_aliases
from xonsh.xontribs import update_context, prompt_xontrib_install
from xonsh.platform import (
    BASH_COMPLETIONS_DEFAULT, DEFAULT_ENCODING, PATH_DEFAULT,
    ON_WINDOWS, ON_LINUX, os_environ
)

from xonsh.tools import (
    always_true, always_false, ensure_string, is_env_path,
    str_to_env_path, env_path_to_str, is_bool, to_bool, bool_to_str,
    is_history_tuple, to_history_tuple, history_tuple_to_str, is_float,
    is_string, is_string_or_callable,
    is_completions_display_value, to_completions_display_value,
    is_string_set, csv_to_set, set_to_csv, is_int, is_bool_seq,
    to_bool_or_int, bool_or_int_to_str,
    csv_to_bool_seq, bool_seq_to_csv, DefaultNotGiven, print_exception,
    setup_win_unicode_console, intensify_colors_on_win_setter,
    is_dynamic_cwd_width, to_dynamic_cwd_tuple, dynamic_cwd_tuple_to_str,
    is_logfile_opt, to_logfile_opt, logfile_opt_to_str, executables_in,
    is_nonstring_seq_of_strings, pathsep_to_upper_seq,
    seq_to_upper_pathsep, print_color, is_history_backend, to_itself,
    swap_values,
)
import xonsh.prompt.base as prompt


events.doc('on_envvar_new', """
on_envvar_new(name: str, value: Any) -> None

Fires after a new enviroment variable is created.
Note: Setting envvars inside the handler might
cause a recursion until the limit.
""")


events.doc('on_envvar_change', """
on_envvar_change(name: str, oldvalue: Any, newvalue: Any) -> None

Fires after an enviroment variable is changed.
Note: Setting envvars inside the handler might
cause a recursion until the limit.
""")


@lazyobject
def HELP_TEMPLATE():
    return ('{{INTENSE_RED}}{envvar}{{NO_COLOR}}:\n\n'
            '{{INTENSE_YELLOW}}{docstr}{{NO_COLOR}}\n\n'
            'default: {{CYAN}}{default}{{NO_COLOR}}\n'
            'configurable: {{CYAN}}{configurable}{{NO_COLOR}}')


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
    'COMPLETIONS_BRACKETS': (is_bool, to_bool, bool_to_str),
    'COMPLETIONS_CONFIRM': (is_bool, to_bool, bool_to_str),
    'COMPLETIONS_DISPLAY': (is_completions_display_value,
                            to_completions_display_value, str),
    'COMPLETIONS_MENU_ROWS': (is_int, int, str),
    'COMPLETION_QUERY_LIMIT': (is_int, int, str),
    'DYNAMIC_CWD_WIDTH': (is_dynamic_cwd_width, to_dynamic_cwd_tuple,
                          dynamic_cwd_tuple_to_str),
    'DYNAMIC_CWD_ELISION_CHAR': (is_string, ensure_string, ensure_string),
    'FORCE_POSIX_PATHS': (is_bool, to_bool, bool_to_str),
    'FOREIGN_ALIASES_OVERRIDE': (is_bool, to_bool, bool_to_str),
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
    'BOTTOM_TOOLBAR': (is_string_or_callable, ensure_string, ensure_string),
    'SUBSEQUENCE_PATH_COMPLETION': (is_bool, to_bool, bool_to_str),
    'SUPPRESS_BRANCH_TIMEOUT_MESSAGE': (is_bool, to_bool, bool_to_str),
    'UPDATE_COMPLETIONS_ON_KEYPRESS': (is_bool, to_bool, bool_to_str),
    'UPDATE_OS_ENVIRON': (is_bool, to_bool, bool_to_str),
    'UPDATE_PROMPT_ON_KEYPRESS': (is_bool, to_bool, bool_to_str),
    'VC_BRANCH_TIMEOUT': (is_float, float, str),
    'VC_HG_SHOW_BRANCH': (is_bool, to_bool, bool_to_str),
    'VI_MODE': (is_bool, to_bool, bool_to_str),
    'VIRTUAL_ENV': (is_string, ensure_string, ensure_string),
    'WIN_UNICODE_CONSOLE': (always_false, setup_win_unicode_console, bool_to_str),
    'XONSHRC': (is_env_path, str_to_env_path, env_path_to_str),
    'XONSH_AUTOPAIR': (is_bool, to_bool, bool_to_str),
    'XONSH_CACHE_SCRIPTS': (is_bool, to_bool, bool_to_str),
    'XONSH_CACHE_EVERYTHING': (is_bool, to_bool, bool_to_str),
    'XONSH_COLOR_STYLE': (is_string, ensure_string, ensure_string),
    'XONSH_DEBUG': (always_false, to_debug, bool_or_int_to_str),
    'XONSH_ENCODING': (is_string, ensure_string, ensure_string),
    'XONSH_ENCODING_ERRORS': (is_string, ensure_string, ensure_string),
    'XONSH_HISTORY_BACKEND': (is_history_backend, to_itself, ensure_string),
    'XONSH_HISTORY_FILE': (is_string, ensure_string, ensure_string),
    'XONSH_HISTORY_SIZE': (is_history_tuple, to_history_tuple, history_tuple_to_str),
    'XONSH_LOGIN': (is_bool, to_bool, bool_to_str),
    'XONSH_PROC_FREQUENCY': (is_float, float, str),
    'XONSH_SHOW_TRACEBACK': (is_bool, to_bool, bool_to_str),
    'XONSH_STDERR_PREFIX': (is_string, ensure_string, ensure_string),
    'XONSH_STDERR_POSTFIX': (is_string, ensure_string, ensure_string),
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


DEFAULT_TITLE = '{current_job:{} | }{user}@{hostname}: {cwd} | xonsh'


@default_value
def xonsh_data_dir(env):
    """Ensures and returns the $XONSH_DATA_DIR"""
    xdd = os.path.expanduser(os.path.join(env.get('XDG_DATA_HOME'), 'xonsh'))
    os.makedirs(xdd, exist_ok=True)
    return xdd


@default_value
def xonsh_config_dir(env):
    """Ensures and returns the $XONSH_CONFIG_DIR"""
    xcd = os.path.expanduser(os.path.join(env.get('XDG_CONFIG_HOME'), 'xonsh'))
    os.makedirs(xcd, exist_ok=True)
    return xcd


@default_value
def xonshconfig(env):
    """Ensures and returns the $XONSHCONFIG"""
    xcd = env.get('XONSH_CONFIG_DIR')
    xc = os.path.join(xcd, 'config.json')
    return xc


@default_value
def default_xonshrc(env):
    """Creates a new instance of the default xonshrc tuple."""
    if ON_WINDOWS:
        dxrc = (xonshconfig(env),
                os.path.join(os_environ['ALLUSERSPROFILE'],
                             'xonsh', 'xonshrc'),
                os.path.expanduser('~/.xonshrc'))
    else:
        dxrc = (xonshconfig(env), '/etc/xonshrc', os.path.expanduser('~/.xonshrc'))
    return dxrc


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
        'COMPLETIONS_BRACKETS': True,
        'COMPLETIONS_CONFIRM': False,
        'COMPLETIONS_DISPLAY': 'multi',
        'COMPLETIONS_MENU_ROWS': 5,
        'COMPLETION_QUERY_LIMIT': 100,
        'DIRSTACK_SIZE': 20,
        'DYNAMIC_CWD_WIDTH': (float('inf'), 'c'),
        'DYNAMIC_CWD_ELISION_CHAR': '',
        'EXPAND_ENV_VARS': True,
        'FORCE_POSIX_PATHS': False,
        'FOREIGN_ALIASES_OVERRIDE': False,
        'PROMPT_FIELDS': dict(prompt.PROMPT_FIELDS),
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
        'PROMPT': prompt.default_prompt(),
        'PUSHD_MINUS': False,
        'PUSHD_SILENT': False,
        'RAISE_SUBPROC_ERROR': False,
        'RIGHT_PROMPT': '',
        'BOTTOM_TOOLBAR': '',
        'SHELL_TYPE': 'best',
        'SUBSEQUENCE_PATH_COMPLETION': True,
        'SUPPRESS_BRANCH_TIMEOUT_MESSAGE': False,
        'SUGGEST_COMMANDS': True,
        'SUGGEST_MAX_NUM': 5,
        'SUGGEST_THRESHOLD': 3,
        'TITLE': DEFAULT_TITLE,
        'UPDATE_COMPLETIONS_ON_KEYPRESS': False,
        'UPDATE_OS_ENVIRON': False,
        'UPDATE_PROMPT_ON_KEYPRESS': False,
        'VC_BRANCH_TIMEOUT': 0.2 if ON_WINDOWS else 0.1,
        'VC_HG_SHOW_BRANCH': True,
        'VI_MODE': False,
        'WIN_UNICODE_CONSOLE': True,
        'XDG_CONFIG_HOME': os.path.expanduser(os.path.join('~', '.config')),
        'XDG_DATA_HOME': os.path.expanduser(os.path.join('~', '.local',
                                                         'share')),
        'XONSHCONFIG': xonshconfig,
        'XONSHRC': default_xonshrc,
        'XONSH_AUTOPAIR': False,
        'XONSH_CACHE_SCRIPTS': True,
        'XONSH_CACHE_EVERYTHING': False,
        'XONSH_COLOR_STYLE': 'default',
        'XONSH_CONFIG_DIR': xonsh_config_dir,
        'XONSH_DATA_DIR': xonsh_data_dir,
        'XONSH_DEBUG': 0,
        'XONSH_ENCODING': DEFAULT_ENCODING,
        'XONSH_ENCODING_ERRORS': 'surrogateescape',
        'XONSH_HISTORY_BACKEND': 'json',
        'XONSH_HISTORY_FILE': os.path.expanduser('~/.xonsh_history.json'),
        'XONSH_HISTORY_SIZE': (8128, 'commands'),
        'XONSH_LOGIN': False,
        'XONSH_PROC_FREQUENCY': 1e-4,
        'XONSH_SHOW_TRACEBACK': False,
        'XONSH_STDERR_PREFIX': '',
        'XONSH_STDERR_POSTFIX': '',
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
        'displayed suggestion. Only usable with ``$SHELL_TYPE=prompt_toolkit.``'),
    'BASH_COMPLETIONS': VarDocs(
        'This is a list (or tuple) of strings that specifies where the '
        '``bash_completion`` script may be found. '
        'The first valid path will be used. For better performance, '
        'bash-completion v2.x is recommended since it lazy-loads individual '
        'completion scripts. '
        'For both bash-completion v1.x and v2.x, paths of individual completion '
        'scripts (like ``.../completes/ssh``) do not need to be included here. '
        'The default values are platform '
        'dependent, but sane. To specify an alternate list, do so in the run '
        'control file.', default=(
            "Normally this is:\n\n"
            "    ``('/usr/share/bash-completion/bash_completion', )``\n\n"
            "But, on Mac it is:\n\n"
            "    ``('/usr/local/share/bash-completion/bash_completion', "
            "'/usr/local/etc/bash_completion')``\n\n"
            "Other OS-specific defaults may be added in the future.")),
    'CASE_SENSITIVE_COMPLETIONS': VarDocs(
        'Sets whether completions should be case sensitive or case '
        'insensitive.', default='True on Linux, False otherwise.'),
    'CDPATH': VarDocs(
        'A list of paths to be used as roots for a cd, breaking compatibility '
        'with Bash, xonsh always prefer an existing relative path.'),
    'COLOR_INPUT': VarDocs('Flag for syntax highlighting interactive input.'),
    'COLOR_RESULTS': VarDocs('Flag for syntax highlighting return values.'),
    'COMPLETIONS_BRACKETS': VarDocs(
        'Flag to enable/disable inclusion of square brackets and parentheses '
        'in Python attribute completions.', default='True'),
    'COMPLETIONS_DISPLAY': VarDocs(
        'Configure if and how Python completions are displayed by the '
        '``prompt_toolkit`` shell.\n\nThis option does not affect Bash '
        'completions, auto-suggestions, etc.\n\nChanging it at runtime will '
        'take immediate effect, so you can quickly disable and enable '
        'completions during shell sessions.\n\n'
        "- If ``$COMPLETIONS_DISPLAY`` is ``none`` or ``false``, do not display\n"
        "  those completions.\n"
        "- If ``$COMPLETIONS_DISPLAY`` is ``single``, display completions in a\n"
        '  single column while typing.\n'
        "- If ``$COMPLETIONS_DISPLAY`` is ``multi`` or ``true``, display completions\n"
        "  in multiple columns while typing.\n\n"
        'These option values are not case- or type-sensitive, so e.g.'
        "writing ``$COMPLETIONS_DISPLAY = None`` "
        "and ``$COMPLETIONS_DISPLAY = 'none'`` are equivalent. Only usable with "
        "``$SHELL_TYPE=prompt_toolkit``"),
    'COMPLETIONS_CONFIRM': VarDocs(
        'While tab-completions menu is displayed, press <Enter> to confirm '
        'completion instead of running command. This only affects the '
        'prompt-toolkit shell.'),
    'COMPLETIONS_MENU_ROWS': VarDocs(
        'Number of rows to reserve for tab-completions menu if '
        "``$COMPLETIONS_DISPLAY`` is ``single`` or ``multi``. This only affects the "
        'prompt-toolkit shell.'),
    'COMPLETION_QUERY_LIMIT': VarDocs(
        'The number of completions to display before the user is asked '
        'for confirmation.'),
    'DIRSTACK_SIZE': VarDocs('Maximum size of the directory stack.'),
    'DYNAMIC_CWD_WIDTH': VarDocs(
        'Maximum length in number of characters '
        'or as a percentage for the ``cwd`` prompt variable. For example, '
        '"20" is a twenty character width and "10%" is ten percent of the '
        'number of columns available.'),
    'DYNAMIC_CWD_ELISION_CHAR': VarDocs(
        'The string used to show a shortened directory in a shortened cwd, '
        'e.g. ``\'…\'``.'),
    'EXPAND_ENV_VARS': VarDocs(
        'Toggles whether environment variables are expanded inside of strings '
        'in subprocess mode.'),
    'FORCE_POSIX_PATHS': VarDocs(
        "Forces forward slashes (``/``) on Windows systems when using auto "
        'completion if set to anything truthy.', configurable=ON_WINDOWS),
    'FOREIGN_ALIASES_OVERRIDE': VarDocs(
        'Whether or not foreign aliases should override xonsh aliases '
        'with the same name. Note that setting of this must happen in the '
        'static configuration file '
        "``$XONSH_CONFIG_DIR/config.json`` in the 'env' section and not in "
        '``.xonshrc`` as loading of foreign aliases happens before'
        '``.xonshrc`` is parsed', configurable=True),
    'PROMPT_FIELDS': VarDocs(
        'Dictionary containing variables to be used when formatting $PROMPT '
        "and $TITLE. See 'Customizing the Prompt' "
        'http://xon.sh/tutorial.html#customizing-the-prompt',
        configurable=False, default='``xonsh.prompt.PROMPT_FIELDS``'),
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
        "default all commands are saved. The option ``ignoredups`` will not "
        "save the command if it matches the previous command. The option "
        "'ignoreerr' will cause any commands that fail (i.e. return non-zero "
        "exit status) to not be added to the history list.",
        store_as_str=True),
    'IGNOREEOF': VarDocs('Prevents Ctrl-D from exiting the shell.'),
    'INDENT': VarDocs('Indentation string for multiline input'),
    'INTENSIFY_COLORS_ON_WIN': VarDocs(
        'Enhance style colors for readability '
        'when using the default terminal (``cmd.exe``) on Windows. Blue colors, '
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
        "to a CSV list in string form, ie ``[True, False]`` becomes "
        "``'True,False'``.",
        configurable=False),
    'MOUSE_SUPPORT': VarDocs(
        'Enable mouse support in the ``prompt_toolkit`` shell. This allows '
        'clicking for positioning the cursor or selecting a completion. In '
        'some terminals however, this disables the ability to scroll back '
        'through the history of the terminal. Only usable with '
        '``$SHELL_TYPE=prompt_toolkit``'),
    'MULTILINE_PROMPT': VarDocs(
        'Prompt text for 2nd+ lines of input, may be str or function which '
        'returns a str.'),
    'OLDPWD': VarDocs('Used to represent a previous present working directory.',
                      configurable=False),
    'PATH': VarDocs(
        'List of strings representing where to look for executables.'),
    'PATHEXT': VarDocs('Sequence of extention strings (eg, ``.EXE``) for '
                       'filtering valid executables by. Each element must be '
                       'uppercase.'),
    'PRETTY_PRINT_RESULTS': VarDocs(
        'Flag for "pretty printing" return values.'),
    'PROMPT': VarDocs(
        'The prompt text. May contain keyword arguments which are '
        "auto-formatted, see 'Customizing the Prompt' at "
        'http://xon.sh/tutorial.html#customizing-the-prompt. '
        'This value is never inherited from parent processes.',
        default='``xonsh.environ.DEFAULT_PROMPT``'),
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
        'The error that is raised is a ``subprocess.CalledProcessError``.'),
    'RIGHT_PROMPT': VarDocs(
        'Template string for right-aligned text '
        'at the prompt. This may be parameterized in the same way as '
        'the ``$PROMPT`` variable. Currently, this is only available in the '
        'prompt-toolkit shell.'),
    'BOTTOM_TOOLBAR': VarDocs(
        'Template string for the bottom toolbar. '
        'This may be parameterized in the same way as '
        'the ``$PROMPT`` variable. Currently, this is only available in the '
        'prompt-toolkit shell.'),
    'SHELL_TYPE': VarDocs(
        'Which shell is used. Currently two base shell types are supported:\n\n'
        "    - ``readline`` that is backed by Python's readline module\n"
        "    - ``prompt_toolkit`` that uses external library of the same name\n"
        "    - ``random`` selects a random shell from the above on startup\n"
        "    - ``best`` selects the most feature-rich shell available on the\n"
        "       user's system\n\n"
        'To use the ``prompt_toolkit`` shell you need to have the '
        '`prompt_toolkit <https://github.com/jonathanslenders/python-prompt-toolkit>`_'
        ' library installed. To specify which shell should be used, do so in '
        'the run control file.', default='``best``'),
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
    'TERM': VarDocs(
        'TERM is sometimes set by the terminal emulator. This is used (when '
        "valid) to determine whether or not to set the title. Users shouldn't "
        "need to set this themselves. Note that this variable should be set as "
        "early as possible in order to ensure it is effective. Here are a few "
        "options:\n\n"
        "* Set this from the program that launches xonsh. On POSIX systems, \n"
        "  this can be performed by using env, e.g. \n"
        "  ``/usr/bin/env TERM=xterm-color xonsh`` or similar.\n"
        "* From the xonsh command line, namely ``xonsh -DTERM=xterm-color``.\n"
        "* In the config file with ``{\"env\": {\"TERM\": \"xterm-color\"}}``.\n"
        "* Lastly, in xonshrc with ``$TERM``\n\n"
        "Ideally, your terminal emulator will set this correctly but that does "
        "not always happen.", configurable=False),
    'TITLE': VarDocs(
        'The title text for the window in which xonsh is running. Formatted '
        "in the same manner as ``$PROMPT``, see 'Customizing the Prompt' "
        'http://xon.sh/tutorial.html#customizing-the-prompt.',
        default='``xonsh.environ.DEFAULT_TITLE``'),
    'UPDATE_COMPLETIONS_ON_KEYPRESS': VarDocs(
        'Completions display is evaluated and presented whenever a key is '
        'pressed. This avoids the need to press TAB, except to cycle through '
        'the possibilities. This currently only affects the prompt-toolkit shell.'
        ),
    'UPDATE_OS_ENVIRON': VarDocs(
        "If True ``os_environ`` will always be updated "
        "when the xonsh environment changes. The environment can be reset to "
        "the default value by calling ``__xonsh_env__.undo_replace_env()``"),
    'UPDATE_PROMPT_ON_KEYPRESS': VarDocs(
        'Disables caching the prompt between commands, '
        'so that it would be reevaluated on each keypress. '
        'Disabled by default because of the incurred performance penalty.'),
    'VC_BRANCH_TIMEOUT': VarDocs(
        'The timeout (in seconds) for version control '
        'branch computations. This is a timeout per subprocess call, so the '
        'total time to compute will be larger than this in many cases.'),
    'VC_HG_SHOW_BRANCH': VarDocs(
        'Whether or not to show the Mercurial branch in the prompt.'),
    'VI_MODE': VarDocs(
        "Flag to enable ``vi_mode`` in the ``prompt_toolkit`` shell."),
    'VIRTUAL_ENV': VarDocs(
        'Path to the currently active Python environment.', configurable=False),
    'WIN_UNICODE_CONSOLE': VarDocs(
        "Enables unicode support in windows terminals. Requires the external "
        "library ``win_unicode_console``.",
        configurable=ON_WINDOWS),
    'XDG_CONFIG_HOME': VarDocs(
        'Open desktop standard configuration home dir. This is the same '
        'default as used in the standard.', configurable=False,
        default="``~/.config``"),
    'XDG_DATA_HOME': VarDocs(
        'Open desktop standard data home dir. This is the same default as '
        'used in the standard.', default="``~/.local/share``"),
    'XONSHCONFIG': VarDocs(
        'The location of the static xonsh configuration file, if it exists. '
        'This is in JSON format.', configurable=False,
        default="``$XONSH_CONFIG_DIR/config.json``"),
    'XONSHRC': VarDocs(
        'A list of the locations of run control files, if they exist.  User '
        'defined run control file will supersede values set in system-wide '
        'control file if there is a naming collision.', default=(
            "On Linux & Mac OSX: ``['/etc/xonshrc', '~/.xonshrc']``\n"
            "\nOn Windows: "
            "``['%ALLUSERSPROFILE%\\\\xonsh\\\\xonshrc', '~/.xonshrc']``")),
    'XONSH_AUTOPAIR': VarDocs(
        'Whether Xonsh will auto-insert matching parentheses, brackets, and '
        'quotes. Only available under the prompt-toolkit shell.'
    ),
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
        configurable=False, default="``$XDG_CONFIG_HOME/xonsh``"),
    'XONSH_DEBUG': VarDocs(
        'Sets the xonsh debugging level. This may be an integer or a boolean. '
        'Setting this variable prior to stating xonsh to ``1`` or ``True`` '
        'will supress amalgamated imports. Setting it to ``2`` will get some '
        'basic information like input transformation, command replacement. '
        'With ``3`` or a higher number will make more debugging information '
        'presented, like PLY parsing messages.',
        configurable=False),
    'XONSH_DATA_DIR': VarDocs(
        'This is the location where xonsh data files are stored, such as '
        'history.', default="``$XDG_DATA_HOME/xonsh``"),
    'XONSH_ENCODING': VarDocs(
        'This is the encoding that xonsh should use for subprocess operations.',
        default='``sys.getdefaultencoding()``'),
    'XONSH_ENCODING_ERRORS': VarDocs(
        'The flag for how to handle encoding errors should they happen. '
        'Any string flag that has been previously registered with Python '
        "is allowed. See the 'Python codecs documentation' "
        "(https://docs.python.org/3/library/codecs.html#error-handlers) "
        'for more information and available options.',
        default="``surrogateescape``"),
    'XONSH_GITSTATUS_*': VarDocs(
        'Symbols for gitstatus prompt. Default values are: \n\n'
        '* ``XONSH_GITSTATUS_HASH``: ``:``\n'
        '* ``XONSH_GITSTATUS_BRANCH``: ``{CYAN}``\n'
        '* ``XONSH_GITSTATUS_OPERATION``: ``{CYAN}``\n'
        '* ``XONSH_GITSTATUS_STAGED``: ``{RED}●``\n'
        '* ``XONSH_GITSTATUS_CONFLICTS``: ``{RED}×``\n'
        '* ``XONSH_GITSTATUS_CHANGED``: ``{BLUE}+``\n'
        '* ``XONSH_GITSTATUS_UNTRACKED``: ``…``\n'
        '* ``XONSH_GITSTATUS_STASHED``: ``⚑``\n'
        '* ``XONSH_GITSTATUS_CLEAN``: ``{BOLD_GREEN}✓``\n'
        '* ``XONSH_GITSTATUS_AHEAD``: ``↑·``\n'
        '* ``XONSH_GITSTATUS_BEHIND``: ``↓·``\n'
    ),
    'XONSH_HISTORY_BACKEND': VarDocs(
        "Set which history backend to use. Options are: 'json', "
        "'sqlite', and 'dummy'. The default is 'json'. "
        '``XONSH_HISTORY_BACKEND`` also accepts a class type that inherits '
        'from ``xonsh.history.base.History``, or its instance.'),
    'XONSH_HISTORY_FILE': VarDocs(
        'Location of history file (deprecated).',
        configurable=False, default="``~/.xonsh_history``"),
    'XONSH_HISTORY_SIZE': VarDocs(
        'Value and units tuple that sets the size of history after garbage '
        'collection. Canonical units are:\n\n'
        "- ``commands`` for the number of past commands executed,\n"
        "- ``files`` for the number of history files to keep,\n"
        "- ``s`` for the number of seconds in the past that are allowed, and\n"
        "- ``b`` for the number of bytes that history may consume.\n\n"
        "Common abbreviations, such as '6 months' or '1 GB' are also allowed.",
        default="``(8128, 'commands')`` or ``'8128 commands'``"),
    'XONSH_INTERACTIVE': VarDocs(
        '``True`` if xonsh is running interactively, and ``False`` otherwise.',
        configurable=False),
    'XONSH_LOGIN': VarDocs(
        '``True`` if xonsh is running as a login shell, and ``False`` otherwise.',
        configurable=False),
    'XONSH_PROC_FREQUENCY': VarDocs(
        'The process frquency is the time that '
        'xonsh process threads sleep for while running command pipelines. '
        'The value has units of seconds [s].'),
    'XONSH_SHOW_TRACEBACK': VarDocs(
        'Controls if a traceback is shown if exceptions occur in the shell. '
        'Set to ``True`` to always show traceback or ``False`` to always hide. '
        'If undefined then the traceback is hidden but a notice is shown on how '
        'to enable the full traceback.'),
    'XONSH_SOURCE': VarDocs(
        "When running a xonsh script, this variable contains the absolute path "
        "to the currently executing script's file.",
        configurable=False),
    'XONSH_STDERR_PREFIX': VarDocs(
        'A format string, using the same keys and colors as ``$PROMPT``, that '
        'is prepended whenever stderr is displayed. This may be used in '
        'conjunction with ``$XONSH_STDERR_POSTFIX`` to close out the block.'
        'For example, to have stderr appear on a red background, the '
        'prefix & postfix pair would be "{BACKGROUND_RED}" & "{NO_COLOR}".'),
    'XONSH_STDERR_POSTFIX': VarDocs(
        'A format string, using the same keys and colors as ``$PROMPT``, that '
        'is appended whenever stderr is displayed. This may be used in '
        'conjunction with ``$XONSH_STDERR_PREFIX`` to start the block.'
        'For example, to have stderr appear on a red background, the '
        'prefix & postfix pair would be "{BACKGROUND_RED}" & "{NO_COLOR}".'),
    'XONSH_STORE_STDIN': VarDocs(
        'Whether or not to store the stdin that is supplied to the '
        '``!()`` and ``![]`` operators.'),
    'XONSH_STORE_STDOUT': VarDocs(
        'Whether or not to store the ``stdout`` and ``stderr`` streams in the '
        'history files.'),
    'XONSH_TRACEBACK_LOGFILE': VarDocs(
        'Specifies a file to store the traceback log to, regardless of whether '
        '``XONSH_SHOW_TRACEBACK`` has been set. Its value must be a writable file '
        'or None / the empty string if traceback logging is not desired. '
        'Logging to a file is not enabled by default.'),
    'XONSH_DATETIME_FORMAT': VarDocs(
        'The format that is used for ``datetime.strptime()`` in various places'
        'i.e the history timestamp option'),
    }


#
# actual environment
#

class Env(cabc.MutableMapping):
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
        """If no initial environment is given, os_environ is used."""
        self._d = {}
        # sentinel value for non existing envvars
        self._no_value = object()
        self._orig_env = None
        self._ensurers = {k: Ensurer(*v) for k, v in DEFAULT_ENSURERS.items()}
        self._defaults = DEFAULT_VALUES
        self._docs = DEFAULT_DOCS
        if len(args) == 0 and len(kwargs) == 0:
            args = (os_environ,)
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
        return not (callable(val) or isinstance(val, cabc.MutableMapping))

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
        """Replaces the contents of os_environ with a detyped version
        of the xonsh environement.
        """
        if self._orig_env is None:
            self._orig_env = dict(os_environ)
        os_environ.clear()
        os_environ.update(self.detype())

    def undo_replace_env(self):
        """Replaces the contents of os_environ with a detyped version
        of the xonsh environement.
        """
        if self._orig_env is not None:
            os_environ.clear()
            os_environ.update(self._orig_env)
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

    def help(self, key):
        """Get information about a specific enviroment variable."""
        vardocs = self.get_docs(key)
        width = min(79, os.get_terminal_size()[0])
        docstr = '\n'.join(textwrap.wrap(vardocs.docstr, width=width))
        template = HELP_TEMPLATE.format(envvar=key,
                                        docstr=docstr,
                                        default=vardocs.default,
                                        configurable=vardocs.configurable)
        print_color(template)

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
        # remove this block on next release
        if key == 'FORMATTER_DICT':
            print('PendingDeprecationWarning: FORMATTER_DICT is an alias of '
                  'PROMPT_FIELDS and will be removed in the next release',
                  file=sys.stderr)
            return self['PROMPT_FIELDS']
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
        if isinstance(val, (cabc.MutableSet, cabc.MutableSequence,
                            cabc.MutableMapping)):
            self._detyped = None
        return val

    def __setitem__(self, key, val):
        ensurer = self.get_ensurer(key)
        if not ensurer.validate(val):
            val = ensurer.convert(val)
        # existing envvars can have any value including None
        old_value = self._d[key] if key in self._d else self._no_value
        self._d[key] = val
        if self.detypeable(val):
            self._detyped = None
            if self.get('UPDATE_OS_ENVIRON'):
                if self._orig_env is None:
                    self.replace_env()
                else:
                    os_environ[key] = ensurer.detype(val)
        if old_value is self._no_value:
            events.on_envvar_new.fire(name=key, value=val)
        elif old_value != val:
            events.on_envvar_change.fire(name=key,
                                         oldvalue=old_value,
                                         newvalue=val)

    def __delitem__(self, key):
        val = self._d.pop(key)
        if self.detypeable(val):
            self._detyped = None
            if self.get('UPDATE_OS_ENVIRON') and key in os_environ:
                del os_environ[key]

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


BASE_ENV = LazyObject(lambda: {
    'BASH_COMPLETIONS': list(DEFAULT_VALUES['BASH_COMPLETIONS']),
    'PROMPT_FIELDS': dict(DEFAULT_VALUES['PROMPT_FIELDS']),
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
        # per se, so we have to use os_environ
        encoding = os_environ.get('XONSH_ENCODING',
                                  DEFAULT_VALUES.get('XONSH_ENCODING', 'utf8'))
        errors = os_environ.get('XONSH_ENCODING_ERRORS',
                                DEFAULT_VALUES.get('XONSH_ENCODING_ERRORS',
                                                   'surrogateescape'))
        with open(config, 'r', encoding=encoding, errors=errors) as f:
            try:
                conf = json.load(f)
                assert isinstance(conf, cabc.Mapping)
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


def xonshrc_context(rcfiles=None, execer=None, ctx=None, env=None, login=True):
    """Attempts to read in all xonshrc files and return the context."""
    loaded = env['LOADED_RC_FILES'] = []
    ctx = {} if ctx is None else ctx
    if rcfiles is None:
        return env
    env['XONSHRC'] = tuple(rcfiles)
    for rcfile in rcfiles:
        if not os.path.isfile(rcfile):
            loaded.append(False)
            continue
        _, ext = os.path.splitext(rcfile)
        if ext == '.json':
            status = static_config_run_control(rcfile, ctx, env, execer=execer,
                                               login=login)
        else:
            status = xonsh_script_run_control(rcfile, ctx, env, execer=execer,
                                              login=login)
        loaded.append(status)
    return ctx


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
        if ev in os_environ:
            ctx[ev] = os_environ[ev]
        elif ev in ctx:
            del ctx[ev]
    ctx['PWD'] = _get_cwd() or ''


def foreign_env_fixes(ctx):
    """Environment fixes for all operating systems"""
    if 'PROMPT' in ctx:
        del ctx['PROMPT']


def static_config_run_control(filename, ctx, env, execer=None, login=True):
    """Loads a static config file and applies it as a run control."""
    if not login:
        return
    conf = load_static_config(env, config=filename)
    # load foreign shells
    foreign_env = load_foreign_envs(shells=conf.get('foreign_shells', ()),
                                    issue_warning=False)
    if ON_WINDOWS:
        windows_foreign_env_fixes(foreign_env)
    foreign_env_fixes(foreign_env)
    env.update(foreign_env)
    aliases = builtins.aliases
    foreign_aliases = load_foreign_aliases(config=filename, issue_warning=True)
    for k, v in foreign_aliases.items():
        if k in aliases:
            msg = ('Skipping application of {0!r} alias from foreign shell '
                   '(loaded from {1!r}) since it shares a name with an '
                   'existing xonsh alias.')
            print(msg.format(k, filename))
        else:
            aliases[k] = v
    # load xontribs
    names = conf.get('xontribs', ())
    for name in names:
        update_context(name, ctx=ctx)
    if getattr(update_context, 'bad_imports', None):
        prompt_xontrib_install(update_context.bad_imports)
        del update_context.bad_imports
    # Do static config environment last, to allow user to override any of
    # our environment choices
    env.update(conf.get('env', ()))
    return True


def xonsh_script_run_control(filename, ctx, env, execer=None, login=True):
    """Loads a xonsh file and applies it as a run control."""
    if execer is None:
        return False
    updates = {'__file__': filename, '__name__': os.path.abspath(filename)}
    try:
        with swap_values(ctx, updates):
            run_script_with_cache(filename, execer, ctx)
        loaded = True
    except SyntaxError as err:
        msg = 'syntax error in xonsh run control file {0!r}: {1!s}'
        print_exception(msg.format(filename, err))
        loaded = False
    except Exception as err:
        msg = 'error running xonsh run control file {0!r}: {1!s}'
        print_exception(msg.format(filename, err))
        loaded = False
    return loaded


def default_env(env=None):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = dict(BASE_ENV)
    ctx.update(os_environ)
    ctx['PWD'] = _get_cwd() or ''
    # other shells' PROMPT definitions generally don't work in XONSH:
    try:
        del ctx['PROMPT']
    except KeyError:
        pass
    # finalize env
    if env is not None:
        ctx.update(env)
    return ctx
