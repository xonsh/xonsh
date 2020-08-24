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
import platform

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
    is_bool_or_none,
    to_bool_or_none,
    bool_or_none_to_str,
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


events.doc(
    "on_lscolors_change",
    """
on_lscolors_change(key: str, oldvalue: Any, newvalue: Any) -> None

Fires after a value in LS_COLORS changes, when a new key is added (oldvalue is None)
or when an existing key is deleted (newvalue is None).
LS_COLORS values must be (ANSI color) strings, None is unambiguous.
Does not fire when the whole environment variable changes (see on_envvar_change).
Does not fire for each value when LS_COLORS is first instantiated.
Normal usage is to arm the event handler, then read (not modify) all existing values.
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
    This accepts the same inputs as dict(). The special value ``target`` is
    replaced by no color, but sets a flag for cognizant application (see is_target()).
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
        "fi": ("NO_COLOR",),
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

    target_value = "target"  # special value to set for ln=target
    target_color = ("NO_COLOR",)  # repres in color space

    def __init__(self, ini_dict: dict = None):
        self._style = self._style_name = None
        self._detyped = None
        self._d = dict()
        self._targets = set()
        if ini_dict:
            for key, value in ini_dict.items():
                if value == LsColors.target_value:
                    self._targets.add(key)
                    value = LsColors.target_color
                self._d[key] = value

    def __getitem__(self, key):
        return self._d[key]

    def __setitem__(self, key, value):
        self._detyped = None
        old_value = self._d.get(key, None)
        self._targets.discard(key)
        if value == LsColors.target_value:
            value = LsColors.target_color
            self._targets.add(key)
        self._d[key] = value
        if (
            old_value != value
        ):  # bug won't fire if new value is 'target' and old value happened to be no color.
            events.on_lscolors_change.fire(key=key, oldvalue=old_value, newvalue=value)

    def __delitem__(self, key):
        self._detyped = None
        old_value = self._d.get(key, None)
        self._targets.discard(key)
        del self._d[key]
        events.on_lscolors_change.fire(key=key, oldvalue=old_value, newvalue=None)

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        yield from self._d

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return "{0}.{1}(...)".format(self.__class__.__module__, self.__class__.__name__)

    def _repr_pretty_(self, p, cycle):
        name = "{0}.{1}".format(self.__class__.__module__, self.__class__.__name__)
        with p.group(0, name + "(", ")"):
            if cycle:
                p.text("...")
            elif len(self):
                p.break_()
                p.pretty(dict(self))

    def is_target(self, key) -> bool:
        "Return True if key is 'target'"
        return key in self._targets

    def detype(self):
        """De-types the instance, allowing it to be exported to the environment."""
        style = self.style
        if self._detyped is None:
            self._detyped = ":".join(
                [
                    key
                    + "="
                    + ";".join(
                        [
                            LsColors.target_value
                            if key in self._targets
                            else ansi_color_name_to_escape_code(v, cmap=style)
                            for v in val
                        ]
                    )
                    for key, val in sorted(self._d.items())
                ]
            )
        return self._detyped

    @property
    def style_name(self):
        """Current XONSH_COLOR_STYLE value"""
        env = getattr(builtins.__xonsh__, "env", {})
        env_style_name = env.get("XONSH_COLOR_STYLE", "default")
        if self._style_name is None or self._style_name != env_style_name:
            self._style_name = env_style_name
            self._style = self._detyped = None
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
        ini_dict = dict()
        # string inputs always use default codes, so translating into
        # xonsh names should be done from defaults
        reversed_default = ansi_reverse_style(style="default")
        for item in s.split(":"):
            key, eq, esc = item.partition("=")
            if not eq:
                # not a valid item
                pass
            elif esc == LsColors.target_value:  # really only for 'ln'
                ini_dict[key] = esc
            else:
                try:
                    ini_dict[key] = ansi_color_escape_code_to_name(
                        esc, "default", reversed_style=reversed_default
                    )
                except Exception as e:
                    print("xonsh:warning:" + str(e), file=sys.stderr)
                    ini_dict[key] = ("NO_COLOR",)
        return cls(ini_dict)

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
# Ensurers
#

# we use this as a registry of common ensurers; valuable for user interface
ENSURERS = {
    "bool": (is_bool, to_bool, bool_to_str),
    "str": (is_string, ensure_string, ensure_string),
    "path": (is_env_path, str_to_env_path, env_path_to_str),
    "float": (is_float, float, str),
    "int": (is_int, int, str),
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


Var = collections.namedtuple(
    "Var",
    [
        "validate",
        "convert",
        "detype",
        "default",
        "doc",
        "doc_configurable",
        "doc_default",
        "doc_store_as_str",
    ],
)
Var.__doc__ = """Named tuples whose elements represent environment variable
validation, conversion, detyping; default values; and documentation.

Parameters
----------
validate : func
    Validator function returning a bool; checks that the variable is of the
    expected type.
convert : func
    Function to convert variable from a string representation to its type.
detype : func
    Function to convert variable from its type to a string representation.
default
    Default value for variable.
doc : str
   The environment variable docstring.
doc_configurable : bool, optional
    Flag for whether the environment variable is configurable or not.
doc_default : str, optional
    Custom docstring for the default value for complex defaults.
    Is this is DefaultNotGiven, then the default will be looked up
    from DEFAULT_VALUES and converted to a str.
doc_store_as_str : bool, optional
    Flag for whether the environment variable should be stored as a
    string. This is used when persisting a variable that is not JSON
    serializable to the config file. For example, sets, frozensets, and
    potentially other non-trivial data types. default, False.
"""

# iterates from back
Var.__new__.__defaults__ = (
    always_true,
    None,
    ensure_string,
    None,
    "",
    True,
    DefaultNotGiven,
    False,
)


# Please keep the following in alphabetic order - scopatz
@lazyobject
def DEFAULT_VARS():
    dv = {
        "ANSICON": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
            "This is used on Windows to set the title, if available.",
            doc_configurable=False,
        ),
        "AUTO_CD": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Flag to enable changing to a directory by entering the dirname or "
            "full path only (without the cd command).",
        ),
        "AUTO_PUSHD": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Flag for automatically pushing directories onto the directory stack.",
        ),
        "AUTO_SUGGEST": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Enable automatic command suggestions based on history, like in the fish "
            "shell.\n\nPressing the right arrow key inserts the currently "
            "displayed suggestion. Only usable with ``$SHELL_TYPE=prompt_toolkit.``",
        ),
        "AUTO_SUGGEST_IN_COMPLETIONS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Places the auto-suggest result as the first option in the completions. "
            "This enables you to tab complete the auto-suggestion.",
        ),
        "BASH_COMPLETIONS": Var(
            is_env_path,
            str_to_env_path,
            env_path_to_str,
            BASH_COMPLETIONS_DEFAULT,
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
            doc_default=(
                "Normally this is:\n\n"
                "    ``('/usr/share/bash-completion/bash_completion', )``\n\n"
                "But, on Mac it is:\n\n"
                "    ``('/usr/local/share/bash-completion/bash_completion', "
                "'/usr/local/etc/bash_completion')``\n\n"
                "Other OS-specific defaults may be added in the future."
            ),
        ),
        "CASE_SENSITIVE_COMPLETIONS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            ON_LINUX,
            "Sets whether completions should be case sensitive or case " "insensitive.",
            doc_default="True on Linux, False otherwise.",
        ),
        "CDPATH": Var(
            is_env_path,
            str_to_env_path,
            env_path_to_str,
            (),
            "A list of paths to be used as roots for a cd, breaking compatibility "
            "with Bash, xonsh always prefer an existing relative path.",
        ),
        "COLOR_INPUT": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Flag for syntax highlighting interactive input.",
        ),
        "COLOR_RESULTS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Flag for syntax highlighting return values.",
        ),
        "COMPLETIONS_BRACKETS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Flag to enable/disable inclusion of square brackets and parentheses "
            "in Python attribute completions.",
            doc_default="True",
        ),
        "COMPLETIONS_CONFIRM": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "While tab-completions menu is displayed, press <Enter> to confirm "
            "completion instead of running command. This only affects the "
            "prompt-toolkit shell.",
        ),
        "COMPLETIONS_DISPLAY": Var(
            is_completions_display_value,
            to_completions_display_value,
            str,
            "multi",
            "Configure if and how Python completions are displayed by the "
            "``prompt_toolkit`` shell.\n\nThis option does not affect Bash "
            "completions, auto-suggestions, etc.\n\nChanging it at runtime will "
            "take immediate effect, so you can quickly disable and enable "
            "completions during shell sessions.\n\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``none`` or ``false``, do not display"
            " those completions.\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``single``, display completions in a\n"
            "  single column while typing.\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``multi`` or ``true``, display completions"
            " in multiple columns while typing.\n\n"
            "- If ``$COMPLETIONS_DISPLAY`` is ``readline``, display completions\n"
            "  will emulate the behavior of readline.\n\n"
            "These option values are not case- or type-sensitive, so e.g. "
            "writing ``$COMPLETIONS_DISPLAY = None`` "
            "and ``$COMPLETIONS_DISPLAY = 'none'`` are equivalent. Only usable with "
            "``$SHELL_TYPE=prompt_toolkit``",
        ),
        "COMPLETIONS_MENU_ROWS": Var(
            is_int,
            int,
            str,
            5,
            "Number of rows to reserve for tab-completions menu if "
            "``$COMPLETIONS_DISPLAY`` is ``single`` or ``multi``. This only affects the "
            "prompt-toolkit shell.",
        ),
        "COMPLETION_QUERY_LIMIT": Var(
            is_int,
            int,
            str,
            100,
            "The number of completions to display before the user is asked "
            "for confirmation.",
        ),
        "COMPLETION_IN_THREAD": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "When generating the completions takes time, "
            "it’s better to do this in a background thread. "
            "When this is True, background threads is used for completion.",
        ),
        "DIRSTACK_SIZE": Var(
            is_int, int, str, 20, "Maximum size of the directory stack."
        ),
        "DOTGLOB": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            'Globbing files with "*" or "**" will also match '
            "dotfiles, or those 'hidden' files whose names "
            "begin with a literal '.'. Such files are filtered "
            "out by default.",
        ),
        "DYNAMIC_CWD_WIDTH": Var(
            is_dynamic_cwd_width,
            to_dynamic_cwd_tuple,
            dynamic_cwd_tuple_to_str,
            (float("inf"), "c"),
            "Maximum length in number of characters "
            "or as a percentage for the ``cwd`` prompt variable. For example, "
            '"20" is a twenty character width and "10%" is ten percent of the '
            "number of columns available.",
        ),
        "DYNAMIC_CWD_ELISION_CHAR": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
            "The string used to show a shortened directory in a shortened cwd, "
            "e.g. ``'…'``.",
        ),
        "EXPAND_ENV_VARS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Toggles whether environment variables are expanded inside of strings "
            "in subprocess mode.",
        ),
        "FORCE_POSIX_PATHS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Forces forward slashes (``/``) on Windows systems when using auto "
            "completion if set to anything truthy.",
            doc_configurable=ON_WINDOWS,
        ),
        "FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not foreign aliases should suppress the message "
            "that informs the user when a foreign alias has been skipped "
            "because it already exists in xonsh.",
            doc_configurable=True,
        ),
        "FOREIGN_ALIASES_OVERRIDE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not foreign aliases should override xonsh aliases "
            "with the same name. Note that setting of this must happen in the "
            "environment that xonsh was started from. "
            "It cannot be set in the ``.xonshrc`` as loading of foreign aliases happens before"
            "``.xonshrc`` is parsed",
            doc_configurable=True,
        ),
        "FUZZY_PATH_COMPLETION": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Toggles 'fuzzy' matching of paths for tab completion, which is only "
            "used as a fallback if no other completions succeed but can be used "
            "as a way to adjust for typographical errors. If ``True``, then, e.g.,"
            " ``xonhs`` will match ``xonsh``.",
        ),
        "GLOB_SORTED": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Toggles whether globbing results are manually sorted. If ``False``, "
            "the results are returned in arbitrary order.",
        ),
        "HISTCONTROL": Var(
            is_string_set,
            csv_to_set,
            set_to_csv,
            set(),
            "A set of strings (comma-separated list in string form) of options "
            "that determine what commands are saved to the history list. By "
            "default all commands are saved. The option ``ignoredups`` will not "
            "save the command if it matches the previous command. The option "
            "``ignoreerr`` will cause any commands that fail (i.e. return non-zero "
            "exit status) to not be added to the history list. The option "
            "``erasedups`` will remove all previous commands that matches and updates the frequency. "
            "Note: ``erasedups`` is supported only in sqlite backend).",
            doc_store_as_str=True,
        ),
        "HOSTNAME": Var(
            is_string,
            ensure_string,
            ensure_string,
            default_value(lambda env: platform.node()),
            "Automatically set to the name of the current host.",
        ),
        "HOSTTYPE": Var(
            is_string,
            ensure_string,
            ensure_string,
            default_value(lambda env: platform.machine()),
            "Automatically set to a string that fully describes the system type on which xonsh is executing.",
        ),
        "IGNOREEOF": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Prevents Ctrl-D from exiting the shell.",
        ),
        "INDENT": Var(
            is_string,
            ensure_string,
            ensure_string,
            "    ",
            "Indentation string for multiline input",
        ),
        "INTENSIFY_COLORS_ON_WIN": Var(
            always_false,
            intensify_colors_on_win_setter,
            bool_to_str,
            True,
            "Enhance style colors for readability "
            "when using the default terminal (``cmd.exe``) on Windows. Blue colors, "
            "which are hard to read, are replaced with cyan. Other colors are "
            "generally replaced by their bright counter parts.",
            doc_configurable=ON_WINDOWS,
        ),
        "LANG": Var(
            is_string,
            ensure_string,
            ensure_string,
            "C.UTF-8",
            "Fallback locale setting for systems where it matters",
        ),
        "LC_COLLATE": Var(
            always_false,
            locale_convert("LC_COLLATE"),
            ensure_string,
            locale.setlocale(locale.LC_COLLATE),
        ),
        "LC_CTYPE": Var(
            always_false,
            locale_convert("LC_CTYPE"),
            ensure_string,
            locale.setlocale(locale.LC_CTYPE),
        ),
        "LC_MONETARY": Var(
            always_false,
            locale_convert("LC_MONETARY"),
            ensure_string,
            locale.setlocale(locale.LC_MONETARY),
        ),
        "LC_NUMERIC": Var(
            always_false,
            locale_convert("LC_NUMERIC"),
            ensure_string,
            locale.setlocale(locale.LC_NUMERIC),
        ),
        "LC_TIME": Var(
            always_false,
            locale_convert("LC_TIME"),
            ensure_string,
            locale.setlocale(locale.LC_TIME),
        ),
        "LS_COLORS": Var(
            is_lscolors,
            LsColors.convert,
            detype,
            default_lscolors,
            "Color settings for ``ls`` command line utility and, "
            "with ``$SHELL_TYPE='prompt_toolkit'``, file arguments in subprocess mode.",
            doc_default="``*.7z=1;0;31:*.Z=1;0;31:*.aac=0;36:*.ace=1;0;31:"
            "*.alz=1;0;31:*.arc=1;0;31:*.arj=1;0;31:*.asf=1;0;35:*.au=0;36:"
            "*.avi=1;0;35:*.bmp=1;0;35:*.bz=1;0;31:*.bz2=1;0;31:*.cab=1;0;31:"
            "*.cgm=1;0;35:*.cpio=1;0;31:*.deb=1;0;31:*.dl=1;0;35:*.dwm=1;0;31:"
            "*.dz=1;0;31:*.ear=1;0;31:*.emf=1;0;35:*.esd=1;0;31:*.flac=0;36:"
            "*.flc=1;0;35:*.fli=1;0;35:*.flv=1;0;35:*.gif=1;0;35:*.gl=1;0;35:"
            "*.gz=1;0;31:*.jar=1;0;31:*.jpeg=1;0;35:*.jpg=1;0;35:*.lha=1;0;31:"
            "*.lrz=1;0;31:*.lz=1;0;31:*.lz4=1;0;31:*.lzh=1;0;31:*.lzma=1;0;31"
            ":*.lzo=1;0;31:*.m2v=1;0;35:*.m4a=0;36:*.m4v=1;0;35:*.mid=0;36:"
            "*.midi=0;36:*.mjpeg=1;0;35:*.mjpg=1;0;35:*.mka=0;36:*.mkv=1;0;35:"
            "*.mng=1;0;35:*.mov=1;0;35:*.mp3=0;36:*.mp4=1;0;35:*.mp4v=1;0;35:"
            "*.mpc=0;36:*.mpeg=1;0;35:*.mpg=1;0;35:*.nuv=1;0;35:*.oga=0;36:"
            "*.ogg=0;36:*.ogm=1;0;35:*.ogv=1;0;35:*.ogx=1;0;35:*.opus=0;36:"
            "*.pbm=1;0;35:*.pcx=1;0;35:*.pgm=1;0;35:*.png=1;0;35:*.ppm=1;0;35:"
            "*.qt=1;0;35:*.ra=0;36:*.rar=1;0;31:*.rm=1;0;35:*.rmvb=1;0;35:"
            "*.rpm=1;0;31:*.rz=1;0;31:*.sar=1;0;31:*.spx=0;36:*.svg=1;0;35:"
            "*.svgz=1;0;35:*.swm=1;0;31:*.t7z=1;0;31:*.tar=1;0;31:*.taz=1;0;31:"
            "*.tbz=1;0;31:*.tbz2=1;0;31:*.tga=1;0;35:*.tgz=1;0;31:*.tif=1;0;35:"
            "*.tiff=1;0;35:*.tlz=1;0;31:*.txz=1;0;31:*.tz=1;0;31:*.tzo=1;0;31:"
            "*.tzst=1;0;31:*.vob=1;0;35:*.war=1;0;31:*.wav=0;36:*.webm=1;0;35:"
            "*.wim=1;0;31:*.wmv=1;0;35:*.xbm=1;0;35:*.xcf=1;0;35:*.xpm=1;0;35:"
            "*.xspf=0;36:*.xwd=1;0;35:*.xz=1;0;31:*.yuv=1;0;35:*.z=1;0;31:"
            "*.zip=1;0;31:*.zoo=1;0;31:*.zst=1;0;31:bd=40;0;33:ca=0;30;41:"
            "cd=40;0;33:di=1;0;34:do=1;0;35:ex=1;0;32:ln=1;0;36:mh=0:mi=0:"
            "or=40;0;31:ow=0;34;42:pi=40;0;33:rs=0:sg=0;30;43:so=1;0;35:"
            "st=0;37;44:su=0;37;41:tw=0;30;42``",
        ),
        "LOADED_RC_FILES": Var(
            is_bool_seq,
            csv_to_bool_seq,
            bool_seq_to_csv,
            (),
            "Whether or not any of the xonsh run control files were loaded at "
            "startup. This is a sequence of bools in Python that is converted "
            "to a CSV list in string form, ie ``[True, False]`` becomes "
            "``'True,False'``.",
            doc_configurable=False,
        ),
        "MOUSE_SUPPORT": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Enable mouse support in the ``prompt_toolkit`` shell. This allows "
            "clicking for positioning the cursor or selecting a completion. In "
            "some terminals however, this disables the ability to scroll back "
            "through the history of the terminal. Only usable with "
            "``$SHELL_TYPE=prompt_toolkit``",
        ),
        "MULTILINE_PROMPT": Var(
            is_string_or_callable,
            ensure_string,
            ensure_string,
            ".",
            "Prompt text for 2nd+ lines of input, may be str or function which "
            "returns a str.",
        ),
        "OLDPWD": Var(
            is_string,
            ensure_string,
            ensure_string,
            ".",
            "Used to represent a previous present working directory.",
            doc_configurable=False,
        ),
        "PATH": Var(
            is_env_path,
            str_to_env_path,
            env_path_to_str,
            PATH_DEFAULT,
            "List of strings representing where to look for executables.",
            doc_default="On Windows: it is ``Path`` value of register's "
            "``HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment``. "
            "On Mac OSX: ``('/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin')`` "
            "On Linux & on Cygwin & on MSYS, when detected that the distro "
            "is like arch, the default PATH is "
            "``('/usr/local/sbin', '/usr/local/bin', '/usr/bin', "
            "'/usr/bin/site_perl', '/usr/bin/vendor_perl', '/usr/bin/core_perl')``"
            " and otherwise is "
            "``('~/bin', '/usr/local/sbin', '/usr/local/bin', '/usr/sbin',"
            "'/usr/bin', '/sbin', '/bin', '/usr/games', '/usr/local/games')``",
        ),
        re.compile(r"\w*PATH$"): Var(is_env_path, str_to_env_path, env_path_to_str),
        "PATHEXT": Var(
            is_nonstring_seq_of_strings,
            pathsep_to_upper_seq,
            seq_to_upper_pathsep,
            [".COM", ".EXE", ".BAT", ".CMD"] if ON_WINDOWS else [],
            "Sequence of extension strings (eg, ``.EXE``) for "
            "filtering valid executables by. Each element must be "
            "uppercase.",
        ),
        "PRETTY_PRINT_RESULTS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            'Flag for "pretty printing" return values.',
        ),
        "PROMPT": Var(
            is_string_or_callable,
            ensure_string,
            ensure_string,
            prompt.default_prompt(),
            "The prompt text. May contain keyword arguments which are "
            "auto-formatted, see 'Customizing the Prompt' at "
            "http://xon.sh/tutorial.html#customizing-the-prompt. "
            "This value is never inherited from parent processes.",
            doc_default="``xonsh.environ.DEFAULT_PROMPT``",
        ),
        "PROMPT_FIELDS": Var(
            always_true,
            None,
            None,
            prompt.PROMPT_FIELDS,
            "Dictionary containing variables to be used when formatting $PROMPT "
            "and $TITLE. See 'Customizing the Prompt' "
            "http://xon.sh/tutorial.html#customizing-the-prompt",
            doc_configurable=False,
            doc_default="``xonsh.prompt.PROMPT_FIELDS``",
        ),
        "PROMPT_REFRESH_INTERVAL": Var(
            is_float,
            float,
            str,
            0,
            "Interval (in seconds) to evaluate and update ``$PROMPT``, ``$RIGHT_PROMPT`` "
            "and ``$BOTTOM_TOOLBAR``. The default is zero (no update). "
            "NOTE: ``$UPDATE_PROMPT_ON_KEYPRESS`` must be set to ``True`` for this "
            "variable to take effect.",
        ),
        "PROMPT_TOOLKIT_COLOR_DEPTH": Var(
            always_false,
            ptk2_color_depth_setter,
            ensure_string,
            "",
            "The color depth used by prompt toolkit 2. Possible values are: "
            "``DEPTH_1_BIT``, ``DEPTH_4_BIT``, ``DEPTH_8_BIT``, ``DEPTH_24_BIT`` "
            "colors. Default is an empty string which means that prompt toolkit decide.",
        ),
        "PTK_STYLE_OVERRIDES": Var(
            is_str_str_dict,
            to_str_str_dict,
            dict_to_str,
            dict(PTK2_STYLE),
            "A dictionary containing custom prompt_toolkit style definitions.",
        ),
        "PUSHD_MINUS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Flag for directory pushing functionality. False is the normal "
            "behavior.",
        ),
        "PUSHD_SILENT": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not to suppress directory stack manipulation output.",
        ),
        "RAISE_SUBPROC_ERROR": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not to raise an error if a subprocess (captured or "
            "uncaptured) returns a non-zero exit status, which indicates failure. "
            "This is most useful in xonsh scripts or modules where failures "
            "should cause an end to execution. This is less useful at a terminal. "
            "The error that is raised is a ``subprocess.CalledProcessError``.",
        ),
        "RIGHT_PROMPT": Var(
            is_string_or_callable,
            ensure_string,
            ensure_string,
            "",
            "Template string for right-aligned text "
            "at the prompt. This may be parametrized in the same way as "
            "the ``$PROMPT`` variable. Currently, this is only available in the "
            "prompt-toolkit shell.",
        ),
        "BOTTOM_TOOLBAR": Var(
            is_string_or_callable,
            ensure_string,
            ensure_string,
            "",
            "Template string for the bottom toolbar. "
            "This may be parametrized in the same way as "
            "the ``$PROMPT`` variable. Currently, this is only available in the "
            "prompt-toolkit shell.",
        ),
        "SHELL_TYPE": Var(
            is_string,
            ensure_string,
            ensure_string,
            "best",
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
            doc_default="``best``",
        ),
        "SUBSEQUENCE_PATH_COMPLETION": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Toggles subsequence matching of paths for tab completion. "
            "If ``True``, then, e.g., ``~/u/ro`` can match ``~/lou/carcolh``.",
        ),
        "SUGGEST_COMMANDS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "When a user types an invalid command, xonsh will try to offer "
            "suggestions of similar valid commands if this is True.",
        ),
        "SUGGEST_MAX_NUM": Var(
            is_int,
            int,
            str,
            5,
            "xonsh will show at most this many suggestions in response to an "
            "invalid command. If negative, there is no limit to how many "
            "suggestions are shown.",
        ),
        "SUGGEST_THRESHOLD": Var(
            is_int,
            int,
            str,
            3,
            "An error threshold. If the Levenshtein distance between the entered "
            "command and a valid command is less than this value, the valid "
            'command will be offered as a suggestion.  Also used for "fuzzy" '
            "tab completion of paths.",
        ),
        "SUPPRESS_BRANCH_TIMEOUT_MESSAGE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not to suppress branch timeout warning messages.",
        ),
        "TERM": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
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
            doc_configurable=False,
        ),
        "THREAD_SUBPROCS": Var(
            is_bool_or_none,
            to_bool_or_none,
            bool_or_none_to_str,
            True,
            "Whether or not to try to run subrocess mode in a Python thread, "
            "when applicable. There are various trade-offs, which normally "
            "affects only interactive sessions.\n\nWhen True:\n\n"
            "* Xonsh is able capture & store the stdin, stdout, and stderr \n"
            "  of threadable subprocesses.\n"
            "* However, stopping threaded subprocs with ^Z (i.e. ``SIGTSTP``)\n"
            "  is disabled as it causes deadlocked terminals.\n"
            "  ``SIGTSTP`` may still be issued and only the physical pressing\n"
            "  of ``Ctrl+Z`` is ignored.\n"
            "* Threadable commands are run with ``PopenThread`` and threadable \n"
            "  aliases are run with ``ProcProxyThread``.\n\n"
            "When False:\n\n"
            "* Xonsh may not be able to capture stdin, stdout, and stderr streams \n"
            "  unless explicitly asked to do so.\n"
            "* Stopping the thread with ``Ctrl+Z`` yields to job control.\n"
            "* Threadable commands are run with ``Popen`` and threadable \n"
            "  alias are run with ``ProcProxy``.\n\n"
            "The desired effect is often up to the command, user, or use case.\n\n"
            "None values are for internal use only and are used to turn off "
            "threading when loading xonshrc files. This is done because Bash "
            "was automatically placing new xonsh instances in the background "
            "at startup when threadable subprocs were used. Please see "
            "https://github.com/xonsh/xonsh/pull/3705 for more information.\n",
        ),
        "TITLE": Var(
            is_string,
            ensure_string,
            ensure_string,
            DEFAULT_TITLE,
            "The title text for the window in which xonsh is running. Formatted "
            "in the same manner as ``$PROMPT``, see 'Customizing the Prompt' "
            "http://xon.sh/tutorial.html#customizing-the-prompt.",
            doc_default="``xonsh.environ.DEFAULT_TITLE``",
        ),
        "UPDATE_COMPLETIONS_ON_KEYPRESS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Completions display is evaluated and presented whenever a key is "
            "pressed. This avoids the need to press TAB, except to cycle through "
            "the possibilities. This currently only affects the prompt-toolkit shell.",
        ),
        "UPDATE_OS_ENVIRON": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "If True ``os_environ`` will always be updated "
            "when the xonsh environment changes. The environment can be reset to "
            "the default value by calling ``__xonsh__.env.undo_replace_env()``",
        ),
        "UPDATE_PROMPT_ON_KEYPRESS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Disables caching the prompt between commands, "
            "so that it would be reevaluated on each keypress. "
            "Disabled by default because of the incurred performance penalty.",
        ),
        "VC_BRANCH_TIMEOUT": Var(
            is_float,
            float,
            str,
            0.2 if ON_WINDOWS else 0.1,
            "The timeout (in seconds) for version control "
            "branch computations. This is a timeout per subprocess call, so the "
            "total time to compute will be larger than this in many cases.",
        ),
        "VC_HG_SHOW_BRANCH": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Whether or not to show the Mercurial branch in the prompt.",
        ),
        "VI_MODE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Flag to enable ``vi_mode`` in the ``prompt_toolkit`` shell.",
        ),
        "VIRTUAL_ENV": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
            "Path to the currently active Python environment.",
            doc_configurable=False,
        ),
        "XDG_CONFIG_HOME": Var(
            is_string,
            ensure_string,
            ensure_string,
            os.path.expanduser(os.path.join("~", ".config")),
            "Open desktop standard configuration home dir. This is the same "
            "default as used in the standard.",
            doc_configurable=False,
            doc_default="``~/.config``",
        ),
        "XDG_DATA_HOME": Var(
            is_string,
            ensure_string,
            ensure_string,
            os.path.expanduser(os.path.join("~", ".local", "share")),
            "Open desktop standard data home dir. This is the same default as "
            "used in the standard.",
            doc_default="``~/.local/share``",
        ),
        "XONSHRC": Var(
            is_env_path,
            str_to_env_path,
            env_path_to_str,
            default_xonshrc,
            "A list of the locations of run control files, if they exist.  User "
            "defined run control file will supersede values set in system-wide "
            "control file if there is a naming collision. $THREAD_SUBPROCS=None "
            "when reading in run control files.",
            doc_default=(
                "On Linux & Mac OSX: ``['/etc/xonshrc', '~/.config/xonsh/rc.xsh', '~/.xonshrc']``\n"
                "\nOn Windows: "
                "``['%ALLUSERSPROFILE%\\\\xonsh\\\\xonshrc', '~/.config/xonsh/rc.xsh', '~/.xonshrc']``"
            ),
        ),
        "XONSH_APPEND_NEWLINE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            xonsh_append_newline,
            "Append new line when a partial line is preserved in output.",
            doc_default="``$XONSH_INTERACTIVE``",
        ),
        "XONSH_AUTOPAIR": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether Xonsh will auto-insert matching parentheses, brackets, and "
            "quotes. Only available under the prompt-toolkit shell.",
        ),
        "XONSH_CACHE_SCRIPTS": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "Controls whether the code for scripts run from xonsh will be cached"
            " (``True``) or re-compiled each time (``False``).",
        ),
        "XONSH_CACHE_EVERYTHING": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Controls whether all code (including code entered at the interactive"
            " prompt) will be cached.",
        ),
        "XONSH_COLOR_STYLE": Var(
            is_string,
            ensure_string,
            ensure_string,
            "default",
            "Sets the color style for xonsh colors. This is a style name, not "
            "a color map. Run ``xonfig styles`` to see the available styles.",
        ),
        "XONSH_CONFIG_DIR": Var(
            is_string,
            ensure_string,
            ensure_string,
            xonsh_config_dir,
            "This is the location where xonsh configuration information is stored.",
            doc_configurable=False,
            doc_default="``$XDG_CONFIG_HOME/xonsh``",
        ),
        "XONSH_DATETIME_FORMAT": Var(
            is_string,
            ensure_string,
            ensure_string,
            "%Y-%m-%d %H:%M",
            "The format that is used for ``datetime.strptime()`` in various places, "
            "i.e the history timestamp option.",
        ),
        "XONSH_DEBUG": Var(
            always_false,
            to_debug,
            bool_or_int_to_str,
            0,
            "Sets the xonsh debugging level. This may be an integer or a boolean. "
            "Setting this variable prior to stating xonsh to ``1`` or ``True`` "
            "will suppress amalgamated imports. Setting it to ``2`` will get some "
            "basic information like input transformation, command replacement. "
            "With ``3`` or a higher number will make more debugging information "
            "presented, like PLY parsing messages.",
            doc_configurable=False,
        ),
        "XONSH_DATA_DIR": Var(
            is_string,
            ensure_string,
            ensure_string,
            xonsh_data_dir,
            "This is the location where xonsh data files are stored, such as "
            "history.",
            doc_default="``$XDG_DATA_HOME/xonsh``",
        ),
        "XONSH_ENCODING": Var(
            is_string,
            ensure_string,
            ensure_string,
            DEFAULT_ENCODING,
            "This is the encoding that xonsh should use for subprocess operations.",
            doc_default="``sys.getdefaultencoding()``",
        ),
        "XONSH_ENCODING_ERRORS": Var(
            is_string,
            ensure_string,
            ensure_string,
            "surrogateescape",
            "The flag for how to handle encoding errors should they happen. "
            "Any string flag that has been previously registered with Python "
            "is allowed. See the 'Python codecs documentation' "
            "(https://docs.python.org/3/library/codecs.html#error-handlers) "
            "for more information and available options.",
            doc_default="``surrogateescape``",
        ),
        "XONSH_GITSTATUS_*": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
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
            "* ``XONSH_GITSTATUS_BEHIND``: ``↓·``\n",
        ),
        "XONSH_HISTORY_BACKEND": Var(
            is_history_backend,
            to_itself,
            ensure_string,
            "json",
            "Set which history backend to use. Options are: 'json', "
            "'sqlite', and 'dummy'. The default is 'json'. "
            "``XONSH_HISTORY_BACKEND`` also accepts a class type that inherits "
            "from ``xonsh.history.base.History``, or its instance.",
        ),
        "XONSH_HISTORY_FILE": Var(
            is_string,
            ensure_string,
            ensure_string,
            os.path.expanduser("~/.xonsh_history.json"),
            "Location of history file (deprecated).",
            doc_configurable=False,
            doc_default="``~/.xonsh_history``",
        ),
        "XONSH_HISTORY_MATCH_ANYWHERE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "When searching history from a partial string (by pressing up arrow), "
            "match command history anywhere in a given line (not just the start)",
            doc_default="False",
        ),
        "XONSH_HISTORY_SIZE": Var(
            is_history_tuple,
            to_history_tuple,
            history_tuple_to_str,
            (8128, "commands"),
            "Value and units tuple that sets the size of history after garbage "
            "collection. Canonical units are:\n\n"
            "- ``commands`` for the number of past commands executed,\n"
            "- ``files`` for the number of history files to keep,\n"
            "- ``s`` for the number of seconds in the past that are allowed, and\n"
            "- ``b`` for the number of bytes that history may consume.\n\n"
            "Common abbreviations, such as '6 months' or '1 GB' are also allowed.",
            doc_default="``(8128, 'commands')`` or ``'8128 commands'``",
        ),
        "XONSH_INTERACTIVE": Var(
            is_bool,
            to_bool,
            bool_to_str,
            True,
            "``True`` if xonsh is running interactively, and ``False`` otherwise.",
            doc_configurable=False,
        ),
        "XONSH_LOGIN": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "``True`` if xonsh is running as a login shell, and ``False`` otherwise.",
            doc_configurable=False,
        ),
        "XONSH_PROC_FREQUENCY": Var(
            is_float,
            float,
            str,
            1e-4,
            "The process frequency is the time that "
            "xonsh process threads sleep for while running command pipelines. "
            "The value has units of seconds [s].",
        ),
        "XONSH_SHOW_TRACEBACK": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Controls if a traceback is shown if exceptions occur in the shell. "
            "Set to ``True`` to always show traceback or ``False`` to always hide. "
            "If undefined then the traceback is hidden but a notice is shown on how "
            "to enable the full traceback.",
        ),
        "XONSH_SOURCE": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
            "When running a xonsh script, this variable contains the absolute path "
            "to the currently executing script's file.",
            doc_configurable=False,
        ),
        "XONSH_STDERR_PREFIX": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
            "A format string, using the same keys and colors as ``$PROMPT``, that "
            "is prepended whenever stderr is displayed. This may be used in "
            "conjunction with ``$XONSH_STDERR_POSTFIX`` to close out the block."
            "For example, to have stderr appear on a red background, the "
            'prefix & postfix pair would be "{BACKGROUND_RED}" & "{NO_COLOR}".',
        ),
        "XONSH_STDERR_POSTFIX": Var(
            is_string,
            ensure_string,
            ensure_string,
            "",
            "A format string, using the same keys and colors as ``$PROMPT``, that "
            "is appended whenever stderr is displayed. This may be used in "
            "conjunction with ``$XONSH_STDERR_PREFIX`` to start the block."
            "For example, to have stderr appear on a red background, the "
            'prefix & postfix pair would be "{BACKGROUND_RED}" & "{NO_COLOR}".',
        ),
        "XONSH_STORE_STDIN": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not to store the stdin that is supplied to the "
            "``!()`` and ``![]`` operators.",
        ),
        "XONSH_STORE_STDOUT": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Whether or not to store the ``stdout`` and ``stderr`` streams in the "
            "history files.",
        ),
        "XONSH_TRACE_SUBPROC": Var(
            is_bool,
            to_bool,
            bool_to_str,
            False,
            "Set to ``True`` to show arguments list of every executed subprocess command.",
        ),
        "XONSH_TRACEBACK_LOGFILE": Var(
            is_logfile_opt,
            to_logfile_opt,
            logfile_opt_to_str,
            None,
            "Specifies a file to store the traceback log to, regardless of whether "
            "``XONSH_SHOW_TRACEBACK`` has been set. Its value must be a writable file "
            "or None / the empty string if traceback logging is not desired. "
            "Logging to a file is not enabled by default.",
        ),
    }

    if hasattr(locale, "LC_MESSAGES"):
        dv["LC_MESSAGES"] = Var(
            always_false,
            locale_convert("LC_MESSAGES"),
            ensure_string,
            locale.setlocale(locale.LC_MESSAGES),
        )

    return dv


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
        self._vars = {k: v for k, v in DEFAULT_VARS.items()}

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
            detyper = self.get_detyper(key)
            if detyper is None:
                # cannot be detyped
                continue
            deval = detyper(val)
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

    def _get_default_validator(self, default=None):
        if default is not None:
            return default
        else:
            default = always_true
        return default

    def _get_default_converter(self, default=None):
        if default is not None:
            return default
        else:
            default = None
        return default

    def _get_default_detyper(self, default=None):
        if default is not None:
            return default
        else:
            default = ensure_string
        return default

    def get_validator(self, key, default=None):
        """Gets a validator for the given key."""
        if key in self._vars:
            return self._vars[key].validate

        # necessary for keys that match regexes, such as `*PATH`s
        for k, var in self._vars.items():
            if isinstance(k, str):
                continue
            if k.match(key) is not None:
                validator = var.validate
                self._vars[key] = var
                break
        else:
            validator = self._get_default_validator(default=default)

        return validator

    def get_converter(self, key, default=None):
        """Gets a converter for the given key."""
        if key in self._vars:
            return self._vars[key].convert

        # necessary for keys that match regexes, such as `*PATH`s
        for k, var in self._vars.items():
            if isinstance(k, str):
                continue
            if k.match(key) is not None:
                converter = var.convert
                self._vars[key] = var
                break
        else:
            converter = self._get_default_converter(default=default)

        return converter

    def get_detyper(self, key, default=None):
        """Gets a detyper for the given key."""
        if key in self._vars:
            return self._vars[key].detype

        # necessary for keys that match regexes, such as `*PATH`s
        for k, var in self._vars.items():
            if isinstance(k, str):
                continue
            if k.match(key) is not None:
                detyper = var.detype
                self._vars[key] = var
                break
        else:
            detyper = self._get_default_detyper(default=default)

        return detyper

    def get_default(self, key, default=None):
        """Gets default for the given key."""
        if key in self._vars:
            return self._vars[key].default
        else:
            return default

    def get_docs(self, key, default=None):
        """Gets the documentation for the environment variable."""
        vd = self._vars.get(key, None)
        if vd is None:
            if default is None:
                default = Var()
            return default
        if vd.doc_default is DefaultNotGiven:
            dval = pprint.pformat(self._vars.get(key, "<default not set>").default)
            vd = vd._replace(doc_default=dval)
        return vd

    def help(self, key):
        """Get information about a specific environment variable."""
        vardocs = self.get_docs(key)
        width = min(79, os.get_terminal_size()[0])
        docstr = "\n".join(textwrap.wrap(vardocs.doc, width=width))
        template = HELP_TEMPLATE.format(
            envvar=key,
            docstr=docstr,
            default=vardocs.doc_default,
            configurable=vardocs.doc_configurable,
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
        elif key in self._vars:
            val = self.get_default(key)
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
        validator = self.get_validator(key)
        converter = self.get_converter(key)
        detyper = self.get_detyper(key)
        if not validator(val):
            val = converter(val)
        # existing envvars can have any value including None
        old_value = self._d[key] if key in self._d else self._no_value
        self._d[key] = val
        self._detyped = None
        if self.get("UPDATE_OS_ENVIRON"):
            if self._orig_env is None:
                self.replace_env()
            elif detyper is None:
                pass
            else:
                deval = detyper(val)
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
        elif key not in self._vars:
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

    def rawkeys(self):
        """An iterator that returns all environment keys in their original form.
        This include string & compiled regular expression keys.
        """
        yield from (set(self._d) | set(self._vars))

    def __iter__(self):
        for key in self.rawkeys():
            if isinstance(key, str):
                yield key

    def __contains__(self, item):
        return item in self._d or item in self._vars

    def __len__(self):
        return len(self._d)

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return "{0}.{1}(...)".format(self.__class__.__module__, self.__class__.__name__)

    def _repr_pretty_(self, p, cycle):
        name = "{0}.{1}".format(self.__class__.__module__, self.__class__.__name__)
        with p.group(0, name + "(", ")"):
            if cycle:
                p.text("...")
            elif len(self):
                p.break_()
                p.pretty(dict(self))

    def register(
        self,
        name,
        type=None,
        default=None,
        doc="",
        validate=always_true,
        convert=None,
        detype=ensure_string,
        doc_configurable=True,
        doc_default=DefaultNotGiven,
        doc_store_as_str=False,
    ):
        """Register an enviornment variable with optional type handling,
        default value, doc.

        Parameters
        ----------
        name : str
            Environment variable name to register. Typically all caps.
        type : str, optional,  {'bool', 'str', 'path', 'int', 'float'}
            Variable type. If not one of the available presets, use `validate`,
            `convert`, and `detype` to specify type behavior.
        default : optional
            Default value for variable. ``ValueError`` raised if type does not match
            that specified by `type` (or `validate`).
        doc : str, optional
            Docstring for variable.
        validate : func, optional
            Function to validate type.
        convert : func, optional
            Function to convert variable from a string representation to its type.
        detype : func, optional
            Function to convert variable from its type to a string representation.
        doc_configurable : bool, optional
            Flag for whether the environment variable is configurable or not.
        doc_default : str, optional
            Custom docstring for the default value for complex defaults.
            If this is ``DefaultNotGiven``, then the default will be looked up
            from ``DEFAULT_VALUES`` and converted to a ``str``.
        doc_store_as_str : bool, optional
            Flag for whether the environment variable should be stored as a
            string. This is used when persisting a variable that is not JSON
            serializable to the config file. For example, sets, frozensets, and
            potentially other non-trivial data types. default, False.

        """

        if (type is not None) and (type in ("bool", "str", "path", "int", "float")):
            validate, convert, detype = ENSURERS[type]

        if default is not None:
            if validate(default):
                pass
            else:
                raise ValueError(
                    "Default value does not match type specified by validate"
                )

        self._vars[name] = Var(
            validate,
            convert,
            detype,
            default,
            doc,
            doc_configurable,
            doc_default,
            doc_store_as_str,
        )

    def deregister(self, name):
        """Deregister an enviornment variable and all its type handling,
        default value, doc.

        Parameters
        ----------
        name : str
            Environment variable name to deregister. Typically all caps.
        """
        self._vars.pop(name)


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
        "BASH_COMPLETIONS": list(DEFAULT_VARS["BASH_COMPLETIONS"].default),
        "PROMPT_FIELDS": dict(DEFAULT_VARS["PROMPT_FIELDS"].default),
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
    orig_thread = env.get("THREAD_SUBPROCS")
    env["THREAD_SUBPROCS"] = None
    env["XONSHRC"] = tuple(rcfiles)
    for rcfile in rcfiles:
        if not os.path.isfile(rcfile):
            loaded.append(False)
            continue
        _, ext = os.path.splitext(rcfile)
        status = xonsh_script_run_control(rcfile, ctx, env, execer=execer, login=login)
        loaded.append(status)
    if env["THREAD_SUBPROCS"] is None:
        env["THREAD_SUBPROCS"] = orig_thread
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
