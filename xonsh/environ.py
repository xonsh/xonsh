# -*- coding: utf-8 -*-
"""Environment for the xonsh shell."""
import os
import re
import sys
import pprint
import textwrap
import locale
import builtins
import warnings
import contextlib
import collections
import collections.abc as cabc
import subprocess

from xonsh import __version__ as XONSH_VERSION
from xonsh.lazyasd import LazyObject, lazyobject
from xonsh.codecache import run_script_with_cache
from xonsh.dirstack import _get_cwd
from xonsh.events import events
from xonsh.platform import (
    BASH_COMPLETIONS_DEFAULT,
    DEFAULT_ENCODING,
    PATH_DEFAULT,
    ON_WINDOWS,
    ON_LINUX,
    os_environ,
)

from xonsh.style_tools import PTK2_STYLE

from xonsh.tools import (
    always_true,
    always_false,
    detype,
    ensure_string,
    is_env_path,
    str_to_env_path,
    env_path_to_str,
    is_bool,
    to_bool,
    bool_to_str,
    is_history_tuple,
    to_history_tuple,
    history_tuple_to_str,
    is_float,
    is_string,
    is_string_or_callable,
    is_completions_display_value,
    to_completions_display_value,
    is_string_set,
    csv_to_set,
    set_to_csv,
    is_int,
    is_bool_seq,
    to_bool_or_int,
    bool_or_int_to_str,
    csv_to_bool_seq,
    bool_seq_to_csv,
    DefaultNotGiven,
    print_exception,
    setup_win_unicode_console,
    intensify_colors_on_win_setter,
    is_dynamic_cwd_width,
    to_dynamic_cwd_tuple,
    dynamic_cwd_tuple_to_str,
    is_logfile_opt,
    to_logfile_opt,
    logfile_opt_to_str,
    executables_in,
    is_nonstring_seq_of_strings,
    pathsep_to_upper_seq,
    seq_to_upper_pathsep,
    print_color,
    is_history_backend,
    to_itself,
    swap_values,
    ptk2_color_depth_setter,
    is_str_str_dict,
    to_str_str_dict,
    dict_to_str,
)
from xonsh.ansi_colors import (
    ansi_color_escape_code_to_name,
    ansi_color_name_to_escape_code,
    ansi_reverse_style,
    ansi_style_by_name,
)
import xonsh.prompt.base as prompt


events.doc(
    "on_envvar_new",
    """
on_envvar_new(name: str, value: Any) -> None

Fires after a new environment variable is created.
Note: Setting envvars inside the handler might
cause a recursion until the limit.
""",
)


events.doc(
    "on_envvar_change",
    """
on_envvar_change(name: str, oldvalue: Any, newvalue: Any) -> None

Fires after an environment variable is changed.
Note: Setting envvars inside the handler might
cause a recursion until the limit.
""",
)


events.doc(
    "on_pre_spec_run_ls",
    """
on_pre_spec_run_ls(spec: xonsh.built_ins.SubprocSpec) -> None

Fires right before a SubprocSpec.run() is called for the ls
command.
""",
)


@lazyobject
def HELP_TEMPLATE():
    return (
        "{{INTENSE_RED}}{envvar}{{NO_COLOR}}:\n\n"
        "{{INTENSE_YELLOW}}{docstr}{{NO_COLOR}}\n\n"
        "default: {{CYAN}}{default}{{NO_COLOR}}\n"
        "configurable: {{CYAN}}{configurable}{{NO_COLOR}}"
    )


@lazyobject
def LOCALE_CATS():
    lc = {
        "LC_CTYPE": locale.LC_CTYPE,
        "LC_COLLATE": locale.LC_COLLATE,
        "LC_NUMERIC": locale.LC_NUMERIC,
        "LC_MONETARY": locale.LC_MONETARY,
        "LC_TIME": locale.LC_TIME,
    }
    if hasattr(locale, "LC_MESSAGES"):
        lc["LC_MESSAGES"] = locale.LC_MESSAGES
    return lc


def locale_convert(key):
    """Creates a converter for a locale key."""

    def lc_converter(val):
        try:
            locale.setlocale(LOCALE_CATS[key], val)
            val = locale.setlocale(LOCALE_CATS[key])
        except (locale.Error, KeyError):
            msg = "Failed to set locale {0!r} to {1!r}".format(key, val)
            warnings.warn(msg, RuntimeWarning)
        return val

    return lc_converter


def to_debug(x):
    """Converts value using to_bool_or_int() and sets this value on as the
    execer's debug level.
    """
    val = to_bool_or_int(x)
    if (
        hasattr(builtins, "__xonsh__")
        and hasattr(builtins.__xonsh__, "execer")
        and builtins.__xonsh__.execer is not None
    ):
        builtins.__xonsh__.execer.debug_level = val
    return val


#
# $LS_COLORS tools
#


class LsColors(cabc.MutableMapping):
    """Helps convert to/from $LS_COLORS format, respecting the xonsh color style.
    This accepts the same inputs as dict().
    """

    default_settings = {
        "*.7z": ("BOLD_RED",),
        "*.Z": ("BOLD_RED",),
        "*.aac": ("CYAN",),
        "*.ace": ("BOLD_RED",),
        "*.alz": ("BOLD_RED",),
        "*.arc": ("BOLD_RED",),
        "*.arj": ("BOLD_RED",),
        "*.asf": ("BOLD_PURPLE",),
        "*.au": ("CYAN",),
        "*.avi": ("BOLD_PURPLE",),
        "*.bmp": ("BOLD_PURPLE",),
        "*.bz": ("BOLD_RED",),
        "*.bz2": ("BOLD_RED",),
        "*.cab": ("BOLD_RED",),
        "*.cgm": ("BOLD_PURPLE",),
        "*.cpio": ("BOLD_RED",),
        "*.deb": ("BOLD_RED",),
        "*.dl": ("BOLD_PURPLE",),
        "*.dwm": ("BOLD_RED",),
        "*.dz": ("BOLD_RED",),
        "*.ear": ("BOLD_RED",),
        "*.emf": ("BOLD_PURPLE",),
        "*.esd": ("BOLD_RED",),
        "*.flac": ("CYAN",),
        "*.flc": ("BOLD_PURPLE",),
        "*.fli": ("BOLD_PURPLE",),
        "*.flv": ("BOLD_PURPLE",),
        "*.gif": ("BOLD_PURPLE",),
        "*.gl": ("BOLD_PURPLE",),
        "*.gz": ("BOLD_RED",),
        "*.jar": ("BOLD_RED",),
        "*.jpeg": ("BOLD_PURPLE",),
        "*.jpg": ("BOLD_PURPLE",),
        "*.lha": ("BOLD_RED",),
        "*.lrz": ("BOLD_RED",),
        "*.lz": ("BOLD_RED",),
        "*.lz4": ("BOLD_RED",),
        "*.lzh": ("BOLD_RED",),
        "*.lzma": ("BOLD_RED",),
        "*.lzo": ("BOLD_RED",),
        "*.m2v": ("BOLD_PURPLE",),
        "*.m4a": ("CYAN",),
        "*.m4v": ("BOLD_PURPLE",),
        "*.mid": ("CYAN",),
        "*.midi": ("CYAN",),
        "*.mjpeg": ("BOLD_PURPLE",),
        "*.mjpg": ("BOLD_PURPLE",),
        "*.mka": ("CYAN",),
        "*.mkv": ("BOLD_PURPLE",),
        "*.mng": ("BOLD_PURPLE",),
        "*.mov": ("BOLD_PURPLE",),
        "*.mp3": ("CYAN",),
        "*.mp4": ("BOLD_PURPLE",),
        "*.mp4v": ("BOLD_PURPLE",),
        "*.mpc": ("CYAN",),
        "*.mpeg": ("BOLD_PURPLE",),
        "*.mpg": ("BOLD_PURPLE",),
        "*.nuv": ("BOLD_PURPLE",),
        "*.oga": ("CYAN",),
        "*.ogg": ("CYAN",),
        "*.ogm": ("BOLD_PURPLE",),
        "*.ogv": ("BOLD_PURPLE",),
        "*.ogx": ("BOLD_PURPLE",),
        "*.opus": ("CYAN",),
        "*.pbm": ("BOLD_PURPLE",),
        "*.pcx": ("BOLD_PURPLE",),
        "*.pgm": ("BOLD_PURPLE",),
        "*.png": ("BOLD_PURPLE",),
        "*.ppm": ("BOLD_PURPLE",),
        "*.qt": ("BOLD_PURPLE",),
        "*.ra": ("CYAN",),
        "*.rar": ("BOLD_RED",),
        "*.rm": ("BOLD_PURPLE",),
        "*.rmvb": ("BOLD_PURPLE",),
        "*.rpm": ("BOLD_RED",),
        "*.rz": ("BOLD_RED",),
        "*.sar": ("BOLD_RED",),
        "*.spx": ("CYAN",),
        "*.svg": ("BOLD_PURPLE",),
        "*.svgz": ("BOLD_PURPLE",),
        "*.swm": ("BOLD_RED",),
        "*.t7z": ("BOLD_RED",),
        "*.tar": ("BOLD_RED",),
        "*.taz": ("BOLD_RED",),
        "*.tbz": ("BOLD_RED",),
        "*.tbz2": ("BOLD_RED",),
        "*.tga": ("BOLD_PURPLE",),
        "*.tgz": ("BOLD_RED",),
        "*.tif": ("BOLD_PURPLE",),
        "*.tiff": ("BOLD_PURPLE",),
        "*.tlz": ("BOLD_RED",),
        "*.txz": ("BOLD_RED",),
        "*.tz": ("BOLD_RED",),
        "*.tzo": ("BOLD_RED",),
        "*.tzst": ("BOLD_RED",),
        "*.vob": ("BOLD_PURPLE",),
        "*.war": ("BOLD_RED",),
        "*.wav": ("CYAN",),
        "*.webm": ("BOLD_PURPLE",),
        "*.wim": ("BOLD_RED",),
        "*.wmv": ("BOLD_PURPLE",),
        "*.xbm": ("BOLD_PURPLE",),
        "*.xcf": ("BOLD_PURPLE",),
        "*.xpm": ("BOLD_PURPLE",),
        "*.xspf": ("CYAN",),
        "*.xwd": ("BOLD_PURPLE",),
        "*.xz": ("BOLD_RED",),
        "*.yuv": ("BOLD_PURPLE",),
        "*.z": ("BOLD_RED",),
        "*.zip": ("BOLD_RED",),
        "*.zoo": ("BOLD_RED",),
        "*.zst": ("BOLD_RED",),
        "bd": ("BACKGROUND_BLACK", "YELLOW"),
        "ca": ("BLACK", "BACKGROUND_RED"),
        "cd": ("BACKGROUND_BLACK", "YELLOW"),
        "di": ("BOLD_BLUE",),
        "do": ("BOLD_PURPLE",),
        "ex": ("BOLD_GREEN",),
        "ln": ("BOLD_CYAN",),
        "mh": ("NO_COLOR",),
        "mi": ("NO_COLOR",),
        "or": ("BACKGROUND_BLACK", "RED"),
        "ow": ("BLUE", "BACKGROUND_GREEN"),
        "pi": ("BACKGROUND_BLACK", "YELLOW"),
        "rs": ("NO_COLOR",),
        "sg": ("BLACK", "BACKGROUND_YELLOW"),
        "so": ("BOLD_PURPLE",),
        "st": ("WHITE", "BACKGROUND_BLUE"),
        "su": ("WHITE", "BACKGROUND_RED"),
        "tw": ("BLACK", "BACKGROUND_GREEN"),
    }

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._style = self._style_name = None
        self._detyped = None

    def __getitem__(self, key):
        return self._d[key]

    def __setitem__(self, key, value):
        self._detyped = None
        self._d[key] = value

    def __delitem__(self, key):
        self._detyped = None
        del self._d[key]

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        yield from self._d

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return "{0}.{1}(...)".format(
            self.__class__.__module__, self.__class__.__name__, self._d
        )

    def _repr_pretty_(self, p, cycle):
        name = "{0}.{1}".format(self.__class__.__module__, self.__class__.__name__)
        with p.group(0, name + "(", ")"):
            if cycle:
                p.text("...")
            elif len(self):
                p.break_()
                p.pretty(dict(self))

    def detype(self):
        """De-types the instance, allowing it to be exported to the environment."""
        style = self.style
        if self._detyped is None:
            self._detyped = ":".join(
                [
                    key
                    + "="
                    + ";".join(
                        [ansi_color_name_to_escape_code(v, cmap=style) for v in val]
                    )
                    for key, val in sorted(self._d.items())
                ]
            )
        return self._detyped

    @property
    def style_name(self):
        """Current XONSH_COLOR_STYLE value"""
        env = builtins.__xonsh__.env
        env_style_name = env.get("XONSH_COLOR_STYLE")
        if self._style_name is None or self._style_name != env_style_name:
            self._style_name = env_style_name
            self._style = self._dtyped = None
        return self._style_name

    @property
    def style(self):
        """The ANSI color style for the current XONSH_COLOR_STYLE"""
        style_name = self.style_name
        if self._style is None:
            self._style = ansi_style_by_name(style_name)
            self._detyped = None
        return self._style

    @classmethod
    def fromstring(cls, s):
        """Creates a new instance of the LsColors class from a colon-separated
        string of dircolor-valid keys to ANSI color escape sequences.
        """
        obj = cls()
        # string inputs always use default codes, so translating into
        # xonsh names should be done from defaults
        reversed_default = ansi_reverse_style(style="default")
        data = {}
        for item in s.split(":"):
            key, eq, esc = item.partition("=")
            if not eq:
                # not a valid item
                continue
            data[key] = ansi_color_escape_code_to_name(
                esc, "default", reversed_style=reversed_default
            )
        obj._d = data
        return obj

    @classmethod
    def fromdircolors(cls, filename=None):
        """Constructs an LsColors instance by running dircolors.
        If a filename is provided, it is passed down to the dircolors command.
        """
        # assemble command
        cmd = ["dircolors", "-b"]
        if filename is not None:
            cmd.append(filename)
        # get env
        if hasattr(builtins, "__xonsh__") and hasattr(builtins.__xonsh__, "env"):
            denv = builtins.__xonsh__.env.detype()
        else:
            denv = None
        # run dircolors
        try:
            out = subprocess.check_output(
                cmd, env=denv, universal_newlines=True, stderr=subprocess.DEVNULL
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return cls(cls.default_settings)
        s = out.splitlines()[0]
        _, _, s = s.partition("'")
        s, _, _ = s.rpartition("'")
        return cls.fromstring(s)

    @classmethod
    def convert(cls, x):
        """Converts an object to LsColors, if needed."""
        if isinstance(x, cls):
            return x
        elif isinstance(x, str):
            return cls.fromstring(x)
        elif isinstance(x, bytes):
            return cls.fromstring(x.decode())
        else:
            return cls(x)


def is_lscolors(x):
    """Checks if an object is an instance of LsColors"""
    return isinstance(x, LsColors)


@events.on_pre_spec_run_ls
def ensure_ls_colors_in_env(spec=None, **kwargs):
    """This ensures that the $LS_COLORS environment variable is in the
    environment. This fires exactly once upon the first time the
    ls command is called.
    """
    env = builtins.__xonsh__.env
    if "LS_COLORS" not in env._d:
        # this adds it to the env too
        default_lscolors(env)
    events.on_pre_spec_run_ls.discard(ensure_ls_colors_in_env)


#
# Ensurerers
#

Ensurer = collections.namedtuple("Ensurer", ["validate", "convert", "detype"])
Ensurer.__doc__ = """Named tuples whose elements are functions that
represent environment variable validation, conversion, detyping.
"""


@lazyobject
def DEFAULT_ENSURERS():
    return {
        "AUTO_CD": (is_bool, to_bool, bool_to_str),
        "AUTO_PUSHD": (is_bool, to_bool, bool_to_str),
        "AUTO_SUGGEST": (is_bool, to_bool, bool_to_str),
        "AUTO_SUGGEST_IN_COMPLETIONS": (is_bool, to_bool, bool_to_str),
        "BASH_COMPLETIONS": (is_env_path, str_to_env_path, env_path_to_str),
        "CASE_SENSITIVE_COMPLETIONS": (is_bool, to_bool, bool_to_str),
        re.compile(r"\w*DIRS$"): (is_env_path, str_to_env_path, env_path_to_str),
        "COLOR_INPUT": (is_bool, to_bool, bool_to_str),
        "COLOR_RESULTS": (is_bool, to_bool, bool_to_str),
        "COMPLETIONS_BRACKETS": (is_bool, to_bool, bool_to_str),
        "COMPLETIONS_CONFIRM": (is_bool, to_bool, bool_to_str),
        "COMPLETIONS_DISPLAY": (
            is_completions_display_value,
            to_completions_display_value,
            str,
        ),
        "COMPLETIONS_MENU_ROWS": (is_int, int, str),
        "COMPLETION_QUERY_LIMIT": (is_int, int, str),
        "DIRSTACK_SIZE": (is_int, int, str),
        "DOTGLOB": (is_bool, to_bool, bool_to_str),
        "DYNAMIC_CWD_WIDTH": (
            is_dynamic_cwd_width,
            to_dynamic_cwd_tuple,
            dynamic_cwd_tuple_to_str,
        ),
        "DYNAMIC_CWD_ELISION_CHAR": (is_string, ensure_string, ensure_string),
        "EXPAND_ENV_VARS": (is_bool, to_bool, bool_to_str),
        "FORCE_POSIX_PATHS": (is_bool, to_bool, bool_to_str),
        "FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE": (is_bool, to_bool, bool_to_str),
        "FOREIGN_ALIASES_OVERRIDE": (is_bool, to_bool, bool_to_str),
        "FUZZY_PATH_COMPLETION": (is_bool, to_bool, bool_to_str),
        "GLOB_SORTED": (is_bool, to_bool, bool_to_str),
        "HISTCONTROL": (is_string_set, csv_to_set, set_to_csv),
        "IGNOREEOF": (is_bool, to_bool, bool_to_str),
        "INTENSIFY_COLORS_ON_WIN": (
            always_false,
            intensify_colors_on_win_setter,
            bool_to_str,
        ),
        "LANG": (is_string, ensure_string, ensure_string),
        "LC_COLLATE": (always_false, locale_convert("LC_COLLATE"), ensure_string),
        "LC_CTYPE": (always_false, locale_convert("LC_CTYPE"), ensure_string),
        "LC_MESSAGES": (always_false, locale_convert("LC_MESSAGES"), ensure_string),
        "LC_MONETARY": (always_false, locale_convert("LC_MONETARY"), ensure_string),
        "LC_NUMERIC": (always_false, locale_convert("LC_NUMERIC"), ensure_string),
        "LC_TIME": (always_false, locale_convert("LC_TIME"), ensure_string),
        "LS_COLORS": (is_lscolors, LsColors.convert, detype),
        "LOADED_RC_FILES": (is_bool_seq, csv_to_bool_seq, bool_seq_to_csv),
        "MOUSE_SUPPORT": (is_bool, to_bool, bool_to_str),
        "MULTILINE_PROMPT": (is_string_or_callable, ensure_string, ensure_string),
        re.compile(r"\w*PATH$"): (is_env_path, str_to_env_path, env_path_to_str),
        "PATHEXT": (
            is_nonstring_seq_of_strings,
            pathsep_to_upper_seq,
            seq_to_upper_pathsep,
        ),
        "PRETTY_PRINT_RESULTS": (is_bool, to_bool, bool_to_str),
        "PROMPT": (is_string_or_callable, ensure_string, ensure_string),
        "PROMPT_FIELDS": (always_true, None, None),
        "PROMPT_TOOLKIT_COLOR_DEPTH": (
            always_false,
            ptk2_color_depth_setter,
            ensure_string,
        ),
        "PUSHD_MINUS": (is_bool, to_bool, bool_to_str),
        "PUSHD_SILENT": (is_bool, to_bool, bool_to_str),
        "PTK_STYLE_OVERRIDES": (is_str_str_dict, to_str_str_dict, dict_to_str),
        "RAISE_SUBPROC_ERROR": (is_bool, to_bool, bool_to_str),
        "RIGHT_PROMPT": (is_string_or_callable, ensure_string, ensure_string),
        "BOTTOM_TOOLBAR": (is_string_or_callable, ensure_string, ensure_string),
        "SUBSEQUENCE_PATH_COMPLETION": (is_bool, to_bool, bool_to_str),
        "SUGGEST_COMMANDS": (is_bool, to_bool, bool_to_str),
        "SUGGEST_MAX_NUM": (is_int, int, str),
        "SUGGEST_THRESHOLD": (is_int, int, str),
        "SUPPRESS_BRANCH_TIMEOUT_MESSAGE": (is_bool, to_bool, bool_to_str),
        "UPDATE_COMPLETIONS_ON_KEYPRESS": (is_bool, to_bool, bool_to_str),
        "UPDATE_OS_ENVIRON": (is_bool, to_bool, bool_to_str),
        "UPDATE_PROMPT_ON_KEYPRESS": (is_bool, to_bool, bool_to_str),
        "VC_BRANCH_TIMEOUT": (is_float, float, str),
        "VC_HG_SHOW_BRANCH": (is_bool, to_bool, bool_to_str),
        "VI_MODE": (is_bool, to_bool, bool_to_str),
        "VIRTUAL_ENV": (is_string, ensure_string, ensure_string),
        "WIN_UNICODE_CONSOLE": (always_false, setup_win_unicode_console, bool_to_str),
        "XONSHRC": (is_env_path, str_to_env_path, env_path_to_str),
        "XONSH_APPEND_NEWLINE": (is_bool, to_bool, bool_to_str),
        "XONSH_AUTOPAIR": (is_bool, to_bool, bool_to_str),
        "XONSH_CACHE_SCRIPTS": (is_bool, to_bool, bool_to_str),
        "XONSH_CACHE_EVERYTHING": (is_bool, to_bool, bool_to_str),
        "XONSH_COLOR_STYLE": (is_string, ensure_string, ensure_string),
        "XONSH_DEBUG": (always_false, to_debug, bool_or_int_to_str),
        "XONSH_ENCODING": (is_string, ensure_string, ensure_string),
        "XONSH_ENCODING_ERRORS": (is_string, ensure_string, ensure_string),
        "XONSH_HISTORY_BACKEND": (is_history_backend, to_itself, ensure_string),
        "XONSH_HISTORY_FILE": (is_string, ensure_string, ensure_string),
        "XONSH_HISTORY_MATCH_ANYWHERE": (is_bool, to_bool, bool_to_str),
        "XONSH_HISTORY_SIZE": (
            is_history_tuple,
            to_history_tuple,
            history_tuple_to_str,
        ),
        "XONSH_LOGIN": (is_bool, to_bool, bool_to_str),
        "XONSH_PROC_FREQUENCY": (is_float, float, str),
        "XONSH_SHOW_TRACEBACK": (is_bool, to_bool, bool_to_str),
        "XONSH_STDERR_PREFIX": (is_string, ensure_string, ensure_string),
        "XONSH_STDERR_POSTFIX": (is_string, ensure_string, ensure_string),
        "XONSH_STORE_STDOUT": (is_bool, to_bool, bool_to_str),
        "XONSH_STORE_STDIN": (is_bool, to_bool, bool_to_str),
        "XONSH_TRACEBACK_LOGFILE": (is_logfile_opt, to_logfile_opt, logfile_opt_to_str),
        "XONSH_DATETIME_FORMAT": (is_string, ensure_string, ensure_string),
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
    return callable(x) and getattr(x, "_xonsh_callable_default", False)


DEFAULT_TITLE = "{current_job:{} | }{user}@{hostname}: {cwd} | xonsh"


@default_value
def xonsh_data_dir(env):
    """Ensures and returns the $XONSH_DATA_DIR"""
    xdd = os.path.expanduser(os.path.join(env.get("XDG_DATA_HOME"), "xonsh"))
    os.makedirs(xdd, exist_ok=True)
    return xdd


@default_value
def xonsh_config_dir(env):
    """Ensures and returns the $XONSH_CONFIG_DIR"""
    xcd = os.path.expanduser(os.path.join(env.get("XDG_CONFIG_HOME"), "xonsh"))
    os.makedirs(xcd, exist_ok=True)
    return xcd


def xonshconfig(env):
    """Ensures and returns the $XONSHCONFIG"""
    xcd = env.get("XONSH_CONFIG_DIR")
    xc = os.path.join(xcd, "config.json")
    return xc


@default_value
def default_xonshrc(env):
    """Creates a new instance of the default xonshrc tuple."""
    xcdrc = os.path.join(xonsh_config_dir(env), "rc.xsh")
    if ON_WINDOWS:
        dxrc = (
            os.path.join(os_environ["ALLUSERSPROFILE"], "xonsh", "xonshrc"),
            xcdrc,
            os.path.expanduser("~/.xonshrc"),
        )
    else:
        dxrc = ("/etc/xonshrc", xcdrc, os.path.expanduser("~/.xonshrc"))
    # Check if old config file exists and issue warning
    old_config_filename = xonshconfig(env)
    if os.path.isfile(old_config_filename):
        print(
            "WARNING! old style configuration ("
            + old_config_filename
            + ") is no longer supported. "
            + "Please migrate to xonshrc."
        )
    return dxrc


@default_value
def xonsh_append_newline(env):
    """Appends a newline if we are in interactive mode"""
    return env.get("XONSH_INTERACTIVE", False)


@default_value
def default_lscolors(env):
    """Gets a default instanse of LsColors"""
    inherited_lscolors = os_environ.get("LS_COLORS", None)
    if inherited_lscolors is None:
        lsc = LsColors.fromdircolors()
    else:
        lsc = LsColors.fromstring(inherited_lscolors)
    # have to place this in the env, so it is applied
    env["LS_COLORS"] = lsc
    return lsc


# Default values should generally be immutable, that way if a user wants
# to set them they have to do a copy and write them to the environment.
# try to keep this sorted.
@lazyobject
def DEFAULT_VALUES():
    dv = {
        "AUTO_CD": False,
        "AUTO_PUSHD": False,
        "AUTO_SUGGEST": True,
        "AUTO_SUGGEST_IN_COMPLETIONS": False,
        "BASH_COMPLETIONS": BASH_COMPLETIONS_DEFAULT,
        "CASE_SENSITIVE_COMPLETIONS": ON_LINUX,
        "CDPATH": (),
        "COLOR_INPUT": True,
        "COLOR_RESULTS": True,
        "COMPLETIONS_BRACKETS": True,
        "COMPLETIONS_CONFIRM": False,
        "COMPLETIONS_DISPLAY": "multi",
        "COMPLETIONS_MENU_ROWS": 5,
        "COMPLETION_QUERY_LIMIT": 100,
        "DIRSTACK_SIZE": 20,
        "DOTGLOB": False,
        "DYNAMIC_CWD_WIDTH": (float("inf"), "c"),
        "DYNAMIC_CWD_ELISION_CHAR": "",
        "EXPAND_ENV_VARS": True,
        "FORCE_POSIX_PATHS": False,
        "FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE": False,
        "FOREIGN_ALIASES_OVERRIDE": False,
        "PROMPT_FIELDS": dict(prompt.PROMPT_FIELDS),
        "FUZZY_PATH_COMPLETION": True,
        "GLOB_SORTED": True,
        "HISTCONTROL": set(),
        "IGNOREEOF": False,
        "INDENT": "    ",
        "INTENSIFY_COLORS_ON_WIN": True,
        "LANG": "C.UTF-8",
        "LC_CTYPE": locale.setlocale(locale.LC_CTYPE),
        "LC_COLLATE": locale.setlocale(locale.LC_COLLATE),
        "LC_TIME": locale.setlocale(locale.LC_TIME),
        "LC_MONETARY": locale.setlocale(locale.LC_MONETARY),
        "LC_NUMERIC": locale.setlocale(locale.LC_NUMERIC),
        "LS_COLORS": default_lscolors,
        "LOADED_RC_FILES": (),
        "MOUSE_SUPPORT": False,
        "MULTILINE_PROMPT": ".",
        "PATH": PATH_DEFAULT,
        "PATHEXT": [".COM", ".EXE", ".BAT", ".CMD"] if ON_WINDOWS else [],
        "PRETTY_PRINT_RESULTS": True,
        "PROMPT": prompt.default_prompt(),
        "PROMPT_TOOLKIT_COLOR_DEPTH": "",
        "PTK_STYLE_OVERRIDES": dict(PTK2_STYLE),
        "PUSHD_MINUS": False,
        "PUSHD_SILENT": False,
        "RAISE_SUBPROC_ERROR": False,
        "RIGHT_PROMPT": "",
        "BOTTOM_TOOLBAR": "",
        "SHELL_TYPE": "best",
        "SUBSEQUENCE_PATH_COMPLETION": True,
        "SUPPRESS_BRANCH_TIMEOUT_MESSAGE": False,
        "SUGGEST_COMMANDS": True,
        "SUGGEST_MAX_NUM": 5,
        "SUGGEST_THRESHOLD": 3,
        "TITLE": DEFAULT_TITLE,
        "UPDATE_COMPLETIONS_ON_KEYPRESS": False,
        "UPDATE_OS_ENVIRON": False,
        "UPDATE_PROMPT_ON_KEYPRESS": False,
        "VC_BRANCH_TIMEOUT": 0.2 if ON_WINDOWS else 0.1,
        "VC_HG_SHOW_BRANCH": True,
        "VI_MODE": False,
        "WIN_UNICODE_CONSOLE": True,
        "XDG_CONFIG_HOME": os.path.expanduser(os.path.join("~", ".config")),
        "XDG_DATA_HOME": os.path.expanduser(os.path.join("~", ".local", "share")),
        "XONSHRC": default_xonshrc,
        "XONSH_APPEND_NEWLINE": xonsh_append_newline,
        "XONSH_AUTOPAIR": False,
        "XONSH_CACHE_SCRIPTS": True,
        "XONSH_CACHE_EVERYTHING": False,
        "XONSH_COLOR_STYLE": "default",
        "XONSH_CONFIG_DIR": xonsh_config_dir,
        "XONSH_DATA_DIR": xonsh_data_dir,
        "XONSH_DEBUG": 0,
        "XONSH_ENCODING": DEFAULT_ENCODING,
        "XONSH_ENCODING_ERRORS": "surrogateescape",
        "XONSH_HISTORY_BACKEND": "json",
        "XONSH_HISTORY_FILE": os.path.expanduser("~/.xonsh_history.json"),
        "XONSH_HISTORY_MATCH_ANYWHERE": False,
        "XONSH_HISTORY_SIZE": (8128, "commands"),
        "XONSH_LOGIN": False,
        "XONSH_PROC_FREQUENCY": 1e-4,
        "XONSH_SHOW_TRACEBACK": False,
        "XONSH_STDERR_PREFIX": "",
        "XONSH_STDERR_POSTFIX": "",
        "XONSH_STORE_STDIN": False,
        "XONSH_STORE_STDOUT": False,
        "XONSH_TRACEBACK_LOGFILE": None,
        "XONSH_DATETIME_FORMAT": "%Y-%m-%d %H:%M",
    }
    if hasattr(locale, "LC_MESSAGES"):
        dv["LC_MESSAGES"] = locale.setlocale(locale.LC_MESSAGES)
    return dv


VarDocs = collections.namedtuple(
    "VarDocs", ["docstr", "configurable", "default", "store_as_str"]
)
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
        "ANSICON": VarDocs(
            "This is used on Windows to set the title, " "if available.",
            configurable=False,
        ),
        "AUTO_CD": VarDocs(
            "Flag to enable changing to a directory by entering the dirname or "
            "full path only (without the cd command)."
        ),
        "AUTO_PUSHD": VarDocs(
            "Flag for automatically pushing directories onto the directory stack."
        ),
        "AUTO_SUGGEST": VarDocs(
            "Enable automatic command suggestions based on history, like in the fish "
            "shell.\n\nPressing the right arrow key inserts the currently "
            "displayed suggestion. Only usable with ``$SHELL_TYPE=prompt_toolkit.``"
        ),
        "AUTO_SUGGEST_IN_COMPLETIONS": VarDocs(
            "Places the auto-suggest result as the first option in the completions. "
            "This enables you to tab complete the auto-suggestion."
        ),
        "BASH_COMPLETIONS": VarDocs(
            "This is a list (or tuple) of strings that specifies where the "
            "``bash_completion`` script may be found. "
            "The first valid path will be used. For better performance, "
            "bash-completion v2.x is recommended since it lazy-loads individual "
            "completion scripts. "
            "For both bash-completion v1.x and v2.x, paths of individual completion "
            "scripts (like ``.../completes/ssh``) do not need to be included here. "
            "The default values are platform "
            "dependent, but sane. To specify an alternate list, do so in the run "
            "control file.",
            default=(
                "Normally this is:\n\n"
                "    ``('/usr/share/bash-completion/bash_completion', )``\n\n"
                "But, on Mac it is:\n\n"
                "    ``('/usr/local/share/bash-completion/bash_completion', "
                "'/usr/local/etc/bash_completion')``\n\n"
                "Other OS-specific defaults may be added in the future."
            ),
        ),
        "CASE_SENSITIVE_COMPLETIONS": VarDocs(
            "Sets whether completions should be case sensitive or case " "insensitive.",
            default="True on Linux, False otherwise.",
        ),
        "CDPATH": VarDocs(
            "A list of paths to be used as roots for a cd, breaking compatibility "
            "with Bash, xonsh always prefer an existing relative path."
        ),
        "COLOR_INPUT": VarDocs("Flag for syntax highlighting interactive input."),
        "COLOR_RESULTS": VarDocs("Flag for syntax highlighting return values."),
        "COMPLETIONS_BRACKETS": VarDocs(
            "Flag to enable/disable inclusion of square brackets and parentheses "
            "in Python attribute completions.",
            default="True",
        ),
        "COMPLETIONS_DISPLAY": VarDocs(
            "Configure if and how Python completions are displayed by the "
            "``prompt_toolkit`` shell.\n\nThis option does not affect Bash "
            "completions, auto-suggestions, etc.\n\nChanging it at runtime will "
            "take immediate effect, so you can quickly disable and enable "
            "completions during shell sessions.\n\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``none`` or ``false``, do not display\n"
            "  those completions.\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``single``, display completions in a\n"
            "  single column while typing.\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``multi`` or ``true``, display completions\n"
            "  in multiple columns while typing.\n\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``readline``, display completions\n"
            "  will emulate the behavior of readline.\n\n"
            "These option values are not case- or type-sensitive, so e.g."
            "writing ``$COMPLETIONS_DISPLAY = None`` "
            "and ``$COMPLETIONS_DISPLAY = 'none'`` are equivalent. Only usable with "
            "``$SHELL_TYPE=prompt_toolkit``"
        ),
        "COMPLETIONS_CONFIRM": VarDocs(
            "While tab-completions menu is displayed, press <Enter> to confirm "
            "completion instead of running command. This only affects the "
            "prompt-toolkit shell."
        ),
        "COMPLETIONS_MENU_ROWS": VarDocs(
            "Number of rows to reserve for tab-completions menu if "
            "``$COMPLETIONS_DISPLAY`` is ``single`` or ``multi``. This only affects the "
            "prompt-toolkit shell."
        ),
        "COMPLETION_QUERY_LIMIT": VarDocs(
            "The number of completions to display before the user is asked "
            "for confirmation."
        ),
        "DIRSTACK_SIZE": VarDocs("Maximum size of the directory stack."),
        "DOTGLOB": VarDocs(
            'Globbing files with "*" or "**" will also match '
            "dotfiles, or those 'hidden' files whose names "
            "begin with a literal '.'. Such files are filtered "
            "out by default."
        ),
        "DYNAMIC_CWD_WIDTH": VarDocs(
            "Maximum length in number of characters "
            "or as a percentage for the ``cwd`` prompt variable. For example, "
            '"20" is a twenty character width and "10%" is ten percent of the '
            "number of columns available."
        ),
        "DYNAMIC_CWD_ELISION_CHAR": VarDocs(
            "The string used to show a shortened directory in a shortened cwd, "
            "e.g. ``'…'``."
        ),
        "EXPAND_ENV_VARS": VarDocs(
            "Toggles whether environment variables are expanded inside of strings "
            "in subprocess mode."
        ),
        "FORCE_POSIX_PATHS": VarDocs(
            "Forces forward slashes (``/``) on Windows systems when using auto "
            "completion if set to anything truthy.",
            configurable=ON_WINDOWS,
        ),
        "FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE": VarDocs(
            "Whether or not foreign aliases should suppress the message "
            "that informs the user when a foreign alias has been skipped "
            "because it already exists in xonsh.",
            configurable=True,
        ),
        "FOREIGN_ALIASES_OVERRIDE": VarDocs(
            "Whether or not foreign aliases should override xonsh aliases "
            "with the same name. Note that setting of this must happen in the "
            "environment that xonsh was started from. "
            "It cannot be set in the ``.xonshrc`` as loading of foreign aliases happens before"
            "``.xonshrc`` is parsed",
            configurable=True,
        ),
        "PROMPT_FIELDS": VarDocs(
            "Dictionary containing variables to be used when formatting $PROMPT "
            "and $TITLE. See 'Customizing the Prompt' "
            "http://xon.sh/tutorial.html#customizing-the-prompt",
            configurable=False,
            default="``xonsh.prompt.PROMPT_FIELDS``",
        ),
        "FUZZY_PATH_COMPLETION": VarDocs(
            "Toggles 'fuzzy' matching of paths for tab completion, which is only "
            "used as a fallback if no other completions succeed but can be used "
            "as a way to adjust for typographical errors. If ``True``, then, e.g.,"
            " ``xonhs`` will match ``xonsh``."
        ),
        "GLOB_SORTED": VarDocs(
            "Toggles whether globbing results are manually sorted. If ``False``, "
            "the results are returned in arbitrary order."
        ),
        "HISTCONTROL": VarDocs(
            "A set of strings (comma-separated list in string form) of options "
            "that determine what commands are saved to the history list. By "
            "default all commands are saved. The option ``ignoredups`` will not "
            "save the command if it matches the previous command. The option "
            "'ignoreerr' will cause any commands that fail (i.e. return non-zero "
            "exit status) to not be added to the history list.",
            store_as_str=True,
        ),
        "IGNOREEOF": VarDocs("Prevents Ctrl-D from exiting the shell."),
        "INDENT": VarDocs("Indentation string for multiline input"),
        "INTENSIFY_COLORS_ON_WIN": VarDocs(
            "Enhance style colors for readability "
            "when using the default terminal (``cmd.exe``) on Windows. Blue colors, "
            "which are hard to read, are replaced with cyan. Other colors are "
            "generally replaced by their bright counter parts.",
            configurable=ON_WINDOWS,
        ),
        "LANG": VarDocs("Fallback locale setting for systems where it matters"),
        "LS_COLORS": VarDocs("Color settings for ``ls`` command line utility"),
        "LOADED_RC_FILES": VarDocs(
            "Whether or not any of the xonsh run control files were loaded at "
            "startup. This is a sequence of bools in Python that is converted "
            "to a CSV list in string form, ie ``[True, False]`` becomes "
            "``'True,False'``.",
            configurable=False,
        ),
        "MOUSE_SUPPORT": VarDocs(
            "Enable mouse support in the ``prompt_toolkit`` shell. This allows "
            "clicking for positioning the cursor or selecting a completion. In "
            "some terminals however, this disables the ability to scroll back "
            "through the history of the terminal. Only usable with "
            "``$SHELL_TYPE=prompt_toolkit``"
        ),
        "MULTILINE_PROMPT": VarDocs(
            "Prompt text for 2nd+ lines of input, may be str or function which "
            "returns a str."
        ),
        "OLDPWD": VarDocs(
            "Used to represent a previous present working directory.",
            configurable=False,
        ),
        "PATH": VarDocs("List of strings representing where to look for executables."),
        "PATHEXT": VarDocs(
            "Sequence of extension strings (eg, ``.EXE``) for "
            "filtering valid executables by. Each element must be "
            "uppercase."
        ),
        "PRETTY_PRINT_RESULTS": VarDocs('Flag for "pretty printing" return values.'),
        "PROMPT": VarDocs(
            "The prompt text. May contain keyword arguments which are "
            "auto-formatted, see 'Customizing the Prompt' at "
            "http://xon.sh/tutorial.html#customizing-the-prompt. "
            "This value is never inherited from parent processes.",
            default="``xonsh.environ.DEFAULT_PROMPT``",
        ),
        "PROMPT_TOOLKIT_COLOR_DEPTH": VarDocs(
            "The color depth used by prompt toolkit 2. Possible values are: "
            "``DEPTH_1_BIT``, ``DEPTH_4_BIT``, ``DEPTH_8_BIT``, ``DEPTH_24_BIT`` "
            "colors. Default is an empty string which means that prompt toolkit decide."
        ),
        "PTK_STYLE_OVERRIDES": VarDocs(
            "A dictionary containing custom prompt_toolkit style definitions."
        ),
        "PUSHD_MINUS": VarDocs(
            "Flag for directory pushing functionality. False is the normal " "behavior."
        ),
        "PUSHD_SILENT": VarDocs(
            "Whether or not to suppress directory stack manipulation output."
        ),
        "RAISE_SUBPROC_ERROR": VarDocs(
            "Whether or not to raise an error if a subprocess (captured or "
            "uncaptured) returns a non-zero exit status, which indicates failure. "
            "This is most useful in xonsh scripts or modules where failures "
            "should cause an end to execution. This is less useful at a terminal. "
            "The error that is raised is a ``subprocess.CalledProcessError``."
        ),
        "RIGHT_PROMPT": VarDocs(
            "Template string for right-aligned text "
            "at the prompt. This may be parametrized in the same way as "
            "the ``$PROMPT`` variable. Currently, this is only available in the "
            "prompt-toolkit shell."
        ),
        "BOTTOM_TOOLBAR": VarDocs(
            "Template string for the bottom toolbar. "
            "This may be parametrized in the same way as "
            "the ``$PROMPT`` variable. Currently, this is only available in the "
            "prompt-toolkit shell."
        ),
        "SHELL_TYPE": VarDocs(
            "Which shell is used. Currently two base shell types are supported:\n\n"
            "    - ``readline`` that is backed by Python's readline module\n"
            "    - ``prompt_toolkit`` that uses external library of the same name\n"
            "    - ``random`` selects a random shell from the above on startup\n"
            "    - ``best`` selects the most feature-rich shell available on the\n"
            "       user's system\n\n"
            "To use the ``prompt_toolkit`` shell you need to have the "
            "`prompt_toolkit <https://github.com/jonathanslenders/python-prompt-toolkit>`_"
            " library installed. To specify which shell should be used, do so in "
            "the run control file.",
            default="``best``",
        ),
        "SUBSEQUENCE_PATH_COMPLETION": VarDocs(
            "Toggles subsequence matching of paths for tab completion. "
            "If ``True``, then, e.g., ``~/u/ro`` can match ``~/lou/carcolh``."
        ),
        "SUGGEST_COMMANDS": VarDocs(
            "When a user types an invalid command, xonsh will try to offer "
            "suggestions of similar valid commands if this is True."
        ),
        "SUGGEST_MAX_NUM": VarDocs(
            "xonsh will show at most this many suggestions in response to an "
            "invalid command. If negative, there is no limit to how many "
            "suggestions are shown."
        ),
        "SUGGEST_THRESHOLD": VarDocs(
            "An error threshold. If the Levenshtein distance between the entered "
            "command and a valid command is less than this value, the valid "
            'command will be offered as a suggestion.  Also used for "fuzzy" '
            "tab completion of paths."
        ),
        "SUPPRESS_BRANCH_TIMEOUT_MESSAGE": VarDocs(
            "Whether or not to suppress branch timeout warning messages."
        ),
        "TERM": VarDocs(
            "TERM is sometimes set by the terminal emulator. This is used (when "
            "valid) to determine whether or not to set the title. Users shouldn't "
            "need to set this themselves. Note that this variable should be set as "
            "early as possible in order to ensure it is effective. Here are a few "
            "options:\n\n"
            "* Set this from the program that launches xonsh. On POSIX systems, \n"
            "  this can be performed by using env, e.g. \n"
            "  ``/usr/bin/env TERM=xterm-color xonsh`` or similar.\n"
            "* From the xonsh command line, namely ``xonsh -DTERM=xterm-color``.\n"
            '* In the config file with ``{"env": {"TERM": "xterm-color"}}``.\n'
            "* Lastly, in xonshrc with ``$TERM``\n\n"
            "Ideally, your terminal emulator will set this correctly but that does "
            "not always happen.",
            configurable=False,
        ),
        "TITLE": VarDocs(
            "The title text for the window in which xonsh is running. Formatted "
            "in the same manner as ``$PROMPT``, see 'Customizing the Prompt' "
            "http://xon.sh/tutorial.html#customizing-the-prompt.",
            default="``xonsh.environ.DEFAULT_TITLE``",
        ),
        "UPDATE_COMPLETIONS_ON_KEYPRESS": VarDocs(
            "Completions display is evaluated and presented whenever a key is "
            "pressed. This avoids the need to press TAB, except to cycle through "
            "the possibilities. This currently only affects the prompt-toolkit shell."
        ),
        "UPDATE_OS_ENVIRON": VarDocs(
            "If True ``os_environ`` will always be updated "
            "when the xonsh environment changes. The environment can be reset to "
            "the default value by calling ``__xonsh__.env.undo_replace_env()``"
        ),
        "UPDATE_PROMPT_ON_KEYPRESS": VarDocs(
            "Disables caching the prompt between commands, "
            "so that it would be reevaluated on each keypress. "
            "Disabled by default because of the incurred performance penalty."
        ),
        "VC_BRANCH_TIMEOUT": VarDocs(
            "The timeout (in seconds) for version control "
            "branch computations. This is a timeout per subprocess call, so the "
            "total time to compute will be larger than this in many cases."
        ),
        "VC_HG_SHOW_BRANCH": VarDocs(
            "Whether or not to show the Mercurial branch in the prompt."
        ),
        "VI_MODE": VarDocs(
            "Flag to enable ``vi_mode`` in the ``prompt_toolkit`` shell."
        ),
        "VIRTUAL_ENV": VarDocs(
            "Path to the currently active Python environment.", configurable=False
        ),
        "WIN_UNICODE_CONSOLE": VarDocs(
            "Enables unicode support in windows terminals. Requires the external "
            "library ``win_unicode_console``.",
            configurable=ON_WINDOWS,
        ),
        "XDG_CONFIG_HOME": VarDocs(
            "Open desktop standard configuration home dir. This is the same "
            "default as used in the standard.",
            configurable=False,
            default="``~/.config``",
        ),
        "XDG_DATA_HOME": VarDocs(
            "Open desktop standard data home dir. This is the same default as "
            "used in the standard.",
            default="``~/.local/share``",
        ),
        "XONSHRC": VarDocs(
            "A list of the locations of run control files, if they exist.  User "
            "defined run control file will supersede values set in system-wide "
            "control file if there is a naming collision.",
            default=(
                "On Linux & Mac OSX: ``['/etc/xonshrc', '~/.config/xonsh/rc.xsh', '~/.xonshrc']``\n"
                "\nOn Windows: "
                "``['%ALLUSERSPROFILE%\\\\xonsh\\\\xonshrc', '~/.config/xonsh/rc.xsh', '~/.xonshrc']``"
            ),
        ),
        "XONSH_APPEND_NEWLINE": VarDocs(
            "Append new line when a partial line is preserved in output."
        ),
        "XONSH_AUTOPAIR": VarDocs(
            "Whether Xonsh will auto-insert matching parentheses, brackets, and "
            "quotes. Only available under the prompt-toolkit shell."
        ),
        "XONSH_CACHE_SCRIPTS": VarDocs(
            "Controls whether the code for scripts run from xonsh will be cached"
            " (``True``) or re-compiled each time (``False``)."
        ),
        "XONSH_CACHE_EVERYTHING": VarDocs(
            "Controls whether all code (including code entered at the interactive"
            " prompt) will be cached."
        ),
        "XONSH_COLOR_STYLE": VarDocs(
            "Sets the color style for xonsh colors. This is a style name, not "
            "a color map. Run ``xonfig styles`` to see the available styles."
        ),
        "XONSH_CONFIG_DIR": VarDocs(
            "This is the location where xonsh configuration information is stored.",
            configurable=False,
            default="``$XDG_CONFIG_HOME/xonsh``",
        ),
        "XONSH_DEBUG": VarDocs(
            "Sets the xonsh debugging level. This may be an integer or a boolean. "
            "Setting this variable prior to stating xonsh to ``1`` or ``True`` "
            "will suppress amalgamated imports. Setting it to ``2`` will get some "
            "basic information like input transformation, command replacement. "
            "With ``3`` or a higher number will make more debugging information "
            "presented, like PLY parsing messages.",
            configurable=False,
        ),
        "XONSH_DATA_DIR": VarDocs(
            "This is the location where xonsh data files are stored, such as "
            "history.",
            default="``$XDG_DATA_HOME/xonsh``",
        ),
        "XONSH_ENCODING": VarDocs(
            "This is the encoding that xonsh should use for subprocess operations.",
            default="``sys.getdefaultencoding()``",
        ),
        "XONSH_ENCODING_ERRORS": VarDocs(
            "The flag for how to handle encoding errors should they happen. "
            "Any string flag that has been previously registered with Python "
            "is allowed. See the 'Python codecs documentation' "
            "(https://docs.python.org/3/library/codecs.html#error-handlers) "
            "for more information and available options.",
            default="``surrogateescape``",
        ),
        "XONSH_GITSTATUS_*": VarDocs(
            "Symbols for gitstatus prompt. Default values are: \n\n"
            "* ``XONSH_GITSTATUS_HASH``: ``:``\n"
            "* ``XONSH_GITSTATUS_BRANCH``: ``{CYAN}``\n"
            "* ``XONSH_GITSTATUS_OPERATION``: ``{CYAN}``\n"
            "* ``XONSH_GITSTATUS_STAGED``: ``{RED}●``\n"
            "* ``XONSH_GITSTATUS_CONFLICTS``: ``{RED}×``\n"
            "* ``XONSH_GITSTATUS_CHANGED``: ``{BLUE}+``\n"
            "* ``XONSH_GITSTATUS_UNTRACKED``: ``…``\n"
            "* ``XONSH_GITSTATUS_STASHED``: ``⚑``\n"
            "* ``XONSH_GITSTATUS_CLEAN``: ``{BOLD_GREEN}✓``\n"
            "* ``XONSH_GITSTATUS_AHEAD``: ``↑·``\n"
            "* ``XONSH_GITSTATUS_BEHIND``: ``↓·``\n"
        ),
        "XONSH_HISTORY_BACKEND": VarDocs(
            "Set which history backend to use. Options are: 'json', "
            "'sqlite', and 'dummy'. The default is 'json'. "
            "``XONSH_HISTORY_BACKEND`` also accepts a class type that inherits "
            "from ``xonsh.history.base.History``, or its instance."
        ),
        "XONSH_HISTORY_FILE": VarDocs(
            "Location of history file (deprecated).",
            configurable=False,
            default="``~/.xonsh_history``",
        ),
        "XONSH_HISTORY_MATCH_ANYWHERE": VarDocs(
            "When searching history from a partial string (by pressing up arrow), "
            "match command history anywhere in a given line (not just the start)",
            default="False",
        ),
        "XONSH_HISTORY_SIZE": VarDocs(
            "Value and units tuple that sets the size of history after garbage "
            "collection. Canonical units are:\n\n"
            "- ``commands`` for the number of past commands executed,\n"
            "- ``files`` for the number of history files to keep,\n"
            "- ``s`` for the number of seconds in the past that are allowed, and\n"
            "- ``b`` for the number of bytes that history may consume.\n\n"
            "Common abbreviations, such as '6 months' or '1 GB' are also allowed.",
            default="``(8128, 'commands')`` or ``'8128 commands'``",
        ),
        "XONSH_INTERACTIVE": VarDocs(
            "``True`` if xonsh is running interactively, and ``False`` otherwise.",
            configurable=False,
        ),
        "XONSH_LOGIN": VarDocs(
            "``True`` if xonsh is running as a login shell, and ``False`` otherwise.",
            configurable=False,
        ),
        "XONSH_PROC_FREQUENCY": VarDocs(
            "The process frequency is the time that "
            "xonsh process threads sleep for while running command pipelines. "
            "The value has units of seconds [s]."
        ),
        "XONSH_SHOW_TRACEBACK": VarDocs(
            "Controls if a traceback is shown if exceptions occur in the shell. "
            "Set to ``True`` to always show traceback or ``False`` to always hide. "
            "If undefined then the traceback is hidden but a notice is shown on how "
            "to enable the full traceback."
        ),
        "XONSH_SOURCE": VarDocs(
            "When running a xonsh script, this variable contains the absolute path "
            "to the currently executing script's file.",
            configurable=False,
        ),
        "XONSH_STDERR_PREFIX": VarDocs(
            "A format string, using the same keys and colors as ``$PROMPT``, that "
            "is prepended whenever stderr is displayed. This may be used in "
            "conjunction with ``$XONSH_STDERR_POSTFIX`` to close out the block."
            "For example, to have stderr appear on a red background, the "
            'prefix & postfix pair would be "{BACKGROUND_RED}" & "{NO_COLOR}".'
        ),
        "XONSH_STDERR_POSTFIX": VarDocs(
            "A format string, using the same keys and colors as ``$PROMPT``, that "
            "is appended whenever stderr is displayed. This may be used in "
            "conjunction with ``$XONSH_STDERR_PREFIX`` to start the block."
            "For example, to have stderr appear on a red background, the "
            'prefix & postfix pair would be "{BACKGROUND_RED}" & "{NO_COLOR}".'
        ),
        "XONSH_STORE_STDIN": VarDocs(
            "Whether or not to store the stdin that is supplied to the "
            "``!()`` and ``![]`` operators."
        ),
        "XONSH_STORE_STDOUT": VarDocs(
            "Whether or not to store the ``stdout`` and ``stderr`` streams in the "
            "history files."
        ),
        "XONSH_TRACEBACK_LOGFILE": VarDocs(
            "Specifies a file to store the traceback log to, regardless of whether "
            "``XONSH_SHOW_TRACEBACK`` has been set. Its value must be a writable file "
            "or None / the empty string if traceback logging is not desired. "
            "Logging to a file is not enabled by default."
        ),
        "XONSH_DATETIME_FORMAT": VarDocs(
            "The format that is used for ``datetime.strptime()`` in various places"
            "i.e the history timestamp option"
        ),
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
    * LC_* (locale categories): locale category names get/set the Python
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
        if ON_WINDOWS:
            path_key = next((k for k in self._d if k.upper() == "PATH"), None)
            if path_key:
                self["PATH"] = self._d.pop(path_key)
        if "PATH" not in self._d:
            # this is here so the PATH is accessible to subprocs and so that
            # it can be modified in-place in the xonshrc file
            self._d["PATH"] = list(PATH_DEFAULT)
        self._detyped = None

    def detype(self):
        if self._detyped is not None:
            return self._detyped
        ctx = {}
        for key, val in self._d.items():
            if not isinstance(key, str):
                key = str(key)
            ensurer = self.get_ensurer(key)
            if ensurer.detype is None:
                # cannot be detyped
                continue
            deval = ensurer.detype(val)
            if deval is None:
                # cannot be detyped
                continue
            ctx[key] = deval
        self._detyped = ctx
        return ctx

    def replace_env(self):
        """Replaces the contents of os_environ with a detyped version
        of the xonsh environment.
        """
        if self._orig_env is None:
            self._orig_env = dict(os_environ)
        os_environ.clear()
        os_environ.update(self.detype())

    def undo_replace_env(self):
        """Replaces the contents of os_environ with a detyped version
        of the xonsh environment.
        """
        if self._orig_env is not None:
            os_environ.clear()
            os_environ.update(self._orig_env)
            self._orig_env = None

    def _get_default_ensurer(self, default=None):
        if default is not None:
            return default
        else:
            default = Ensurer(always_true, None, ensure_string)
        return default

    def get_ensurer(self, key, default=None):
        """Gets an ensurer for the given key."""
        if key in self._ensurers:
            return self._ensurers[key]
        for k, ensurer in self._ensurers.items():
            if isinstance(k, str):
                continue
            if k.match(key) is not None:
                break
        else:
            ensurer = self._get_default_ensurer(default=default)
        self._ensurers[key] = ensurer
        return ensurer

    def set_ensurer(self, key, value):
        """Sets an ensurer."""
        self._detyped = None
        self._ensurers[key] = value

    def get_docs(self, key, default=VarDocs("<no documentation>")):
        """Gets the documentation for the environment variable."""
        vd = self._docs.get(key, None)
        if vd is None:
            return default
        if vd.default is DefaultNotGiven:
            dval = pprint.pformat(self._defaults.get(key, "<default not set>"))
            vd = vd._replace(default=dval)
            self._docs[key] = vd
        return vd

    def help(self, key):
        """Get information about a specific environment variable."""
        vardocs = self.get_docs(key)
        width = min(79, os.get_terminal_size()[0])
        docstr = "\n".join(textwrap.wrap(vardocs.docstr, width=width))
        template = HELP_TEMPLATE.format(
            envvar=key,
            docstr=docstr,
            default=vardocs.default,
            configurable=vardocs.configurable,
        )
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

        exception = None
        try:
            yield self
        except Exception as e:
            exception = e
        finally:
            # restore the values
            for k, v in old.items():
                if v is NotImplemented:
                    del self[k]
                else:
                    self[k] = v
            if exception is not None:
                raise exception from None

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        # remove this block on next release
        if key is Ellipsis:
            return self
        elif key in self._d:
            val = self._d[key]
        elif key in self._defaults:
            val = self._defaults[key]
            if is_callable_default(val):
                val = val(self)
        else:
            e = "Unknown environment variable: ${}"
            raise KeyError(e.format(key))
        if isinstance(
            val, (cabc.MutableSet, cabc.MutableSequence, cabc.MutableMapping)
        ):
            self._detyped = None
        return val

    def __setitem__(self, key, val):
        ensurer = self.get_ensurer(key)
        if not ensurer.validate(val):
            val = ensurer.convert(val)
        # existing envvars can have any value including None
        old_value = self._d[key] if key in self._d else self._no_value
        self._d[key] = val
        self._detyped = None
        if self.get("UPDATE_OS_ENVIRON"):
            if self._orig_env is None:
                self.replace_env()
            elif ensurer.detype is None:
                pass
            else:
                deval = ensurer.detype(val)
                if deval is not None:
                    os_environ[key] = deval
        if old_value is self._no_value:
            events.on_envvar_new.fire(name=key, value=val)
        elif old_value != val:
            events.on_envvar_change.fire(name=key, oldvalue=old_value, newvalue=val)

    def __delitem__(self, key):
        if key in self._d:
            del self._d[key]
            self._detyped = None
            if self.get("UPDATE_OS_ENVIRON") and key in os_environ:
                del os_environ[key]
        elif key not in self._defaults:
            e = "Unknown environment variable: ${}"
            raise KeyError(e.format(key))

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
        return "{0}.{1}(...)".format(
            self.__class__.__module__, self.__class__.__name__, self._d
        )

    def _repr_pretty_(self, p, cycle):
        name = "{0}.{1}".format(self.__class__.__module__, self.__class__.__name__)
        with p.group(0, name + "(", ")"):
            if cycle:
                p.text("...")
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
    return builtins.__xonsh__.commands_cache.locate_binary(name)


BASE_ENV = LazyObject(
    lambda: {
        "BASH_COMPLETIONS": list(DEFAULT_VALUES["BASH_COMPLETIONS"]),
        "PROMPT_FIELDS": dict(DEFAULT_VALUES["PROMPT_FIELDS"]),
        "XONSH_VERSION": XONSH_VERSION,
    },
    globals(),
    "BASE_ENV",
)


def xonshrc_context(rcfiles=None, execer=None, ctx=None, env=None, login=True):
    """Attempts to read in all xonshrc files and return the context."""
    loaded = env["LOADED_RC_FILES"] = []
    ctx = {} if ctx is None else ctx
    if rcfiles is None:
        return env
    env["XONSHRC"] = tuple(rcfiles)
    for rcfile in rcfiles:
        if not os.path.isfile(rcfile):
            loaded.append(False)
            continue
        _, ext = os.path.splitext(rcfile)
        status = xonsh_script_run_control(rcfile, ctx, env, execer=execer, login=login)
        loaded.append(status)
    return ctx


def windows_foreign_env_fixes(ctx):
    """Environment fixes for Windows. Operates in-place."""
    # remove these bash variables which only cause problems.
    for ev in ["HOME", "OLDPWD"]:
        if ev in ctx:
            del ctx[ev]
    # Override path-related bash variables; on Windows bash uses
    # /c/Windows/System32 syntax instead of C:\\Windows\\System32
    # which messes up these environment variables for xonsh.
    for ev in ["PATH", "TEMP", "TMP"]:
        if ev in os_environ:
            ctx[ev] = os_environ[ev]
        elif ev in ctx:
            del ctx[ev]
    ctx["PWD"] = _get_cwd() or ""


def foreign_env_fixes(ctx):
    """Environment fixes for all operating systems"""
    if "PROMPT" in ctx:
        del ctx["PROMPT"]


def xonsh_script_run_control(filename, ctx, env, execer=None, login=True):
    """Loads a xonsh file and applies it as a run control."""
    if execer is None:
        return False
    updates = {"__file__": filename, "__name__": os.path.abspath(filename)}
    try:
        with swap_values(ctx, updates):
            run_script_with_cache(filename, execer, ctx)
        loaded = True
    except SyntaxError as err:
        msg = "syntax error in xonsh run control file {0!r}: {1!s}"
        print_exception(msg.format(filename, err))
        loaded = False
    except Exception as err:
        msg = "error running xonsh run control file {0!r}: {1!s}"
        print_exception(msg.format(filename, err))
        loaded = False
    return loaded


def default_env(env=None):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = dict(BASE_ENV)
    ctx.update(os_environ)
    ctx["PWD"] = _get_cwd() or ""
    # These can cause problems for programs (#2543)
    ctx.pop("LINES", None)
    ctx.pop("COLUMNS", None)
    # other shells' PROMPT definitions generally don't work in XONSH:
    try:
        del ctx["PROMPT"]
    except KeyError:
        pass
    # finalize env
    if env is not None:
        ctx.update(env)
    return ctx


def make_args_env(args=None):
    """Makes a dictionary containing the $ARGS and $ARG<N> environment
    variables. If the supplied ARGS is None, then sys.argv is used.
    """
    if args is None:
        args = sys.argv
    env = {"ARG" + str(i): arg for i, arg in enumerate(args)}
    env["ARGS"] = list(args)  # make a copy so we don't interfere with original variable
    return env
