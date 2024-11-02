"""Environment for the xonsh shell."""

import collections.abc as cabc
import contextlib
import inspect
import locale
import os
import platform
import pprint
import re
import subprocess
import sys
import textwrap
import threading
import typing as tp
import warnings
from collections import ChainMap
from pathlib import Path

import xonsh.prompt.base as prompt
from xonsh import __version__ as XONSH_VERSION
from xonsh.ansi_colors import (
    ansi_color_escape_code_to_name,
    ansi_color_name_to_escape_code,
    ansi_reverse_style,
    ansi_style_by_name,
)
from xonsh.built_ins import XSH
from xonsh.codecache import run_script_with_cache
from xonsh.dirstack import _get_cwd
from xonsh.events import events
from xonsh.lib.lazyasd import LazyBool, lazyobject
from xonsh.platform import (
    BASH_COMPLETIONS_DEFAULT,
    DEFAULT_ENCODING,
    ON_CYGWIN,
    ON_LINUX,
    ON_WINDOWS,
    PATH_DEFAULT,
    os_environ,
)
from xonsh.tools import (
    DefaultNotGiven,
    DefaultNotGivenType,
    adjust_shlvl,
    always_false,
    always_true,
    bool_or_int_to_str,
    bool_or_none_to_str,
    bool_to_str,
    csv_to_set,
    detype,
    dict_to_str,
    dynamic_cwd_tuple_to_str,
    ensure_string,
    env_path_to_str,
    history_tuple_to_str,
    intensify_colors_on_win_setter,
    is_bool,
    is_bool_or_int,
    is_bool_or_none,
    is_completion_mode,
    is_completions_display_value,
    is_dynamic_cwd_width,
    is_env_path,
    is_float,
    is_history_backend,
    is_history_tuple,
    is_int,
    is_logfile_opt,
    is_nonstring_seq_of_strings,
    is_path,
    is_regex,
    is_string,
    is_string_or_callable,
    is_string_set,
    is_tok_color_dict,
    is_valid_shlvl,
    logfile_opt_to_str,
    path_to_str,
    pathsep_to_upper_seq,
    print_color,
    print_exception,
    print_warning,
    ptk2_color_depth_setter,
    seq_to_upper_pathsep,
    set_to_csv,
    str_to_env_path,
    str_to_path,
    swap_values,
    to_bool,
    to_bool_or_int,
    to_bool_or_none,
    to_completion_mode,
    to_completions_display_value,
    to_dynamic_cwd_tuple,
    to_history_tuple,
    to_int_or_none,
    to_itself,
    to_logfile_opt,
    to_repr_pretty_,
    to_shlvl,
    to_tok_color_dict,
)

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
        "{{INTENSE_RED}}{envvar}{{RESET}}:\n\n"
        "{{INTENSE_YELLOW}}{docstr}{{RESET}}\n\n"
        "default: {{CYAN}}{default}{{RESET}}\n"
        "configurable: {{CYAN}}{configurable}{{RESET}}"
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
            msg = f"Failed to set locale {key!r} to {val!r}"
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return val

    return lc_converter


def to_debug(x):
    """Converts value using to_bool_or_int() and sets this value on as the
    execer's debug level.
    """
    val = to_bool_or_int(x)
    if XSH.execer is not None:
        XSH.execer.debug_level = val
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
        "fi": ("RESET",),
        "ln": ("BOLD_CYAN",),
        "mh": ("RESET",),
        "mi": ("RESET",),
        "or": ("BACKGROUND_BLACK", "RED"),
        "ow": ("BLUE", "BACKGROUND_GREEN"),
        "pi": ("BACKGROUND_BLACK", "YELLOW"),
        "rs": ("RESET",),
        "sg": ("BLACK", "BACKGROUND_YELLOW"),
        "so": ("BOLD_PURPLE",),
        "st": ("WHITE", "BACKGROUND_BLUE"),
        "su": ("WHITE", "BACKGROUND_RED"),
        "tw": ("BLACK", "BACKGROUND_GREEN"),
    }

    target_value = "target"  # special value to set for ln=target
    target_color = ("RESET",)  # repres in color space

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
        return f"{self.__class__.__module__}.{self.__class__.__name__}(...)"

    _repr_pretty_ = to_repr_pretty_

    def is_target(self, key) -> bool:
        """Return True if key is 'target'"""
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
                            (
                                LsColors.target_value
                                if key in self._targets
                                else ansi_color_name_to_escape_code(v, cmap=style)
                            )
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
        env = getattr(XSH, "env", {}) or {}
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
                    ini_dict[key] = ("RESET",)
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
        if XSH.env:
            denv = XSH.env.detype()
        else:
            denv = None
        # run dircolors
        try:
            out = subprocess.check_output(
                cmd, env=denv, text=True, stderr=subprocess.DEVNULL
            )
        except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
            return cls(cls.default_settings)
        except OSError as e:
            # necessary to catch OSError: [WinError 740] The requested operation requires elevation
            if not ON_WINDOWS:
                print_warning(f"dircolors: {e}")
            return cls(cls.default_settings)
        if not out:
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
    env = XSH.env
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
    "path": (is_path, str_to_path, path_to_str),
    "env_path": (is_env_path, str_to_env_path, env_path_to_str),
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
def xonsh_cache_dir(env):
    """Ensures and returns the $XONSH_CACHE_DIR"""
    xdd = os.path.expanduser(os.path.join(env.get("XDG_CACHE_HOME"), "xonsh"))
    os.makedirs(xdd, exist_ok=True)
    return xdd


@default_value
def xonsh_config_dir(env):
    """``$XDG_CONFIG_HOME/xonsh``"""
    xcd = os.path.expanduser(os.path.join(env.get("XDG_CONFIG_HOME"), "xonsh"))
    os.makedirs(xcd, exist_ok=True)
    return xcd


@default_value
def xdg_data_dirs(env):
    r"""
    On Windows: ``[%ProgramData%]`` (normally C:\ProgramData)
        - More Info: https://docs.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/microsoft-windows-shell-setup-folderlocations-programdata

    On Linux and Unix based systemd it is the same as in open-desktop standard: ``['/usr/share', '/usr/local/share']``
    """
    if ON_WINDOWS:
        return [os_environ["ProgramData"]]
    return [
        os.path.join("/usr", "share"),
        os.path.join("/usr", "local", "share"),
    ]


@default_value
def xonsh_sys_config_dir(env):
    """
    On Linux & Mac OSX: ``'/etc/xonsh'``
    On Windows: ``'%ALLUSERSPROFILE%\\\\xonsh'``
    """
    if ON_WINDOWS:
        etc_path = os_environ["ALLUSERSPROFILE"]
    else:
        etc_path = "/etc"
    return os.path.join(etc_path, "xonsh")


def xonshconfig(env):
    """Ensures and returns the $XONSHCONFIG"""
    xcd = env.get("XONSH_CONFIG_DIR")
    xc = os.path.join(xcd, "config.json")
    return xc


def get_home_xonshrc_path():
    """Cross-platform implementation of getting ``~/.xonshrc`` path."""
    return str((Path("~") / ".xonshrc").expanduser())


@default_value
def default_xonshrc(env) -> "tuple[str, ...]":
    """
    ``['$XONSH_SYS_CONFIG_DIR/xonshrc', '$XONSH_CONFIG_DIR/xonsh/rc.xsh', '~/.xonshrc']``
    """

    dxrc = (
        os.path.join(xonsh_sys_config_dir(env), "xonshrc"),
        os.path.join(xonsh_config_dir(env), "rc.xsh"),
        get_home_xonshrc_path(),
    )
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


def get_config_paths(env: "Env", name: str):
    return (
        os.path.join(xonsh_sys_config_dir(env), name),
        os.path.join(xonsh_config_dir(env), name),
    )


@default_value
def default_xonshrcdir(env):
    """``['$XONSH_SYS_CONFIG_DIR/rc.d', '$XONSH_CONFIG_DIR/rc.d']``\n"""
    return get_config_paths(env, "rc.d")


@default_value
def default_completer_dirs(env):
    """By default, the following paths are searched.
    1. ``$XONSH_CONFIG_DIR/completions`` - user level completions
    2. ``$XONSH_SYS_CONFIG_DIR/completions`` - system level completions
    3. ``$XONSH_DATA_DIR/generated_completions`` - auto generated completers from man pages
    4. ``$XDG_DATA_DIRS/xonsh/vendor_completions`` - completers from other programs can be placed here.

    Other than this, Python package namespace ``xompletions`` can be used to put completer modules as well.
    """
    # inspired from - https://fishshell.com/docs/current/completions.html#where-to-put-completions
    return [
        os.path.join(env["XONSH_CONFIG_DIR"], "completions"),
        os.path.join(env["XONSH_SYS_CONFIG_DIR"], "completions"),
        os.path.join(env["XONSH_DATA_DIR"], "generated_completions"),
    ] + [
        os.path.join(parent, "xonsh", "vendor_completions")
        for parent in env["XDG_DATA_DIRS"]
    ]


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


@default_value
def default_prompt_fields(env):
    """``xonsh.prompt.PROMPT_FIELDS``"""
    # todo: generate document for all default fields
    return prompt.PromptFields(XSH)


VarKeyType = tp.Union[str, tp.Pattern]


class Var(tp.NamedTuple):
    """Named tuples whose elements represent environment variable
    validation, conversion, detyping; default values; and documentation.

    Attributes
    ----------
    validate : func
        Validator function returning a bool; checks that the variable is of the
        expected type.
    convert : func
        Function to convert variable from a string representation to its type.
    detype : func
        Function to convert variable from its type to a string representation.
    default
        Default value for variable. If set to DefaultNotGiven, raise KeyError
        instead of returning this default value.  Used for env vars defined
        outside of Xonsh.
    doc : str, optional
       The environment variable docstring.
    doc_default : str, optional
        Custom docstring for the default value for complex defaults.
    is_configurable : bool, optional
        Flag for whether the environment variable is configurable or not.
    can_store_as_str : bool, optional
        Flag for whether the environment variable should be stored as a
        string. This is used when persisting a variable that is not JSON
        serializable to the config file. For example, sets, frozensets, and
        potentially other non-trivial data types. default, False.
    pattern
        a regex pattern to match for the given variable
    """

    validate: tp.Optional[tp.Callable] = always_true
    convert: tp.Optional[tp.Callable] = None
    detype: tp.Optional[tp.Callable] = ensure_string
    default: tp.Any = DefaultNotGiven
    doc: str = ""
    is_configurable: tp.Union[bool, LazyBool] = True
    doc_default: tp.Union[str, DefaultNotGivenType] = DefaultNotGiven
    can_store_as_str: bool = False
    pattern: tp.Optional[VarKeyType] = None

    @classmethod
    def with_default(
        cls,
        default: object,
        doc: str = "",
        doc_default: tp.Union[str, DefaultNotGivenType] = DefaultNotGiven,
        type_str: str = "",
        **kwargs,
    ):
        """fill arguments from the value of default"""
        if not type_str:
            cls_name = type(default).__name__
            type_str = {"LazyBool": "bool"}.get(cls_name, cls_name)

        if type_str in ENSURERS and "validate" not in kwargs:
            validator, convertor, detyper = ENSURERS[type_str]
            kwargs.update(
                {"validate": validator, "convert": convertor, "detype": detyper}
            )

        if doc_default == DefaultNotGiven and is_callable_default(default):
            doc_default = inspect.getdoc(default) or DefaultNotGiven
        return Var(default=default, doc=doc, doc_default=doc_default, **kwargs)

    @classmethod
    def no_default(cls, type_str: str, doc: str = "", **kwargs):
        return cls.with_default(
            default=DefaultNotGiven, doc=doc, type_str=type_str, **kwargs
        )

    @classmethod
    def for_locale(cls, lcle: str):
        return cls(
            validate=always_false,
            convert=locale_convert(lcle),
            detype=ensure_string,
            default=locale.setlocale(getattr(locale, lcle)),
        )

    def get_key(self, var_name: str) -> VarKeyType:
        return self.pattern or var_name


class Xettings:
    """Parent class - All setting classes will be inheriting from this.
    The first line of those class's docstring will become the group's title.
    Rest of the docstring will become the description of that Group of settings.
    """

    @classmethod
    def get_settings(cls) -> tp.Iterator[tuple[VarKeyType, Var]]:
        for var_name, var in vars(cls).items():
            if not var_name.startswith("__") and var_name.isupper():
                yield var.get_key(var_name), var

    @staticmethod
    def _get_groups(
        cls, _seen: tp.Optional[set["Xettings"]] = None, *bases: "Xettings"
    ):
        if _seen is None:
            _seen = set()
        subs = cls.__subclasses__()

        for sub in subs:
            if sub not in _seen:
                _seen.add(sub)
                yield (*bases, sub), tuple(sub.get_settings())
                yield from Xettings._get_groups(sub, _seen, *bases, sub)

    @classmethod
    def get_groups(
        cls,
    ) -> tp.Iterator[tuple[tuple["Xettings", ...], tuple[tuple[VarKeyType, Var], ...]]]:
        yield from Xettings._get_groups(cls)

    @classmethod
    def get_doc(cls):
        import inspect

        return inspect.getdoc(cls)

    @classmethod
    def get_group_title(cls) -> str:
        doc = cls.get_doc()
        if doc:
            return doc.splitlines()[0]
        return cls.__name__

    @classmethod
    def get_group_description(cls) -> str:
        doc = cls.get_doc()
        if doc:
            lines = doc.splitlines()
            if len(lines) > 1:
                return "\n".join(lines[1:])
        return ""


class GeneralSetting(Xettings):
    """General"""

    HOSTNAME = Var.with_default(
        default=default_value(lambda env: platform.node()),
        doc="Automatically set to the name of the current host.",
        type_str="str",
    )
    HOSTTYPE = Var.with_default(
        default=default_value(lambda env: platform.machine()),
        doc="Automatically set to a string that fully describes the system type on which xonsh is executing.",
        type_str="str",
    )

    PWD = Var.with_default(
        _get_cwd() or ".",
        "Current working directory.",
        "os.getcwd()",
        is_configurable=False,
    )
    OLDPWD = Var.with_default(
        ".",
        "Used to represent a previous present working directory.",
        is_configurable=False,
    )
    PATH = Var.with_default(
        PATH_DEFAULT,
        "List of strings representing where to look for executables.",
        type_str="env_path",
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
    )
    PATHEXT = Var(
        is_nonstring_seq_of_strings,
        pathsep_to_upper_seq,
        seq_to_upper_pathsep,
        [".COM", ".EXE", ".BAT", ".CMD"] if ON_WINDOWS else [],
        "Sequence of extension strings (eg, ``.EXE``) for "
        "filtering valid executables by. Each element must be "
        "uppercase.",
    )

    SHLVL = Var(
        is_valid_shlvl,
        to_shlvl,
        str,
        0,
        "Shell nesting level typed as integer, mirrors bash's $SHLVL.",
        is_configurable=False,
    )

    TERM = Var.no_default(
        "str",
        "TERM is sometimes set by the terminal emulator. This is used (when "
        "valid) to determine whether the terminal emulator can support "
        "the selected shell, or whether or not to set the title. Users shouldn't "
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
        is_configurable=False,
    )

    UPDATE_OS_ENVIRON = Var.with_default(
        False,
        "If True ``os_environ`` will always be updated "
        "when the xonsh environment changes. The environment can be reset to "
        "the default value by calling ``__xonsh__.env.undo_replace_env()``",
    )
    XDG_CONFIG_HOME = Var.with_default(
        os.path.expanduser(os.path.join("~", ".config")),
        "Open desktop standard configuration home dir. This is the same "
        "default as used in the standard.",
        is_configurable=False,
        doc_default="``~/.config``",
        type_str="str",
    )
    XDG_DATA_HOME = Var.with_default(
        os.path.expanduser(os.path.join("~", ".local", "share")),
        "Open desktop standard data home dir. This is the same default as "
        "used in the standard.",
        doc_default="``~/.local/share``",
        type_str="str",
    )
    XDG_CACHE_HOME = Var.with_default(
        os.path.expanduser(os.path.join("~", ".cache")),
        "The base directory relative to which user-specific non-essential data files should be stored.",
        doc_default="``~/.cache``",
        type_str="str",
    )
    XDG_DATA_DIRS = Var.with_default(
        xdg_data_dirs,
        "A list of directories where system level data files are stored.",
        type_str="env_path",
    )
    XONSHRC = Var.with_default(
        default_xonshrc,
        "A list of the locations of run control files, if they exist.  User "
        "defined run control file will supersede values set in system-wide "
        "control file if there is a naming collision. $THREAD_SUBPROCS=None "
        "when reading in run control files.",
        type_str="env_path",
    )
    XONSHRC_DIR = Var.with_default(
        default_xonshrcdir,
        "A list of directories, from which all .xsh|.py files will be loaded "
        "at startup, sorted in lexographic order. Files in these directories "
        "are loaded after any files in XONSHRC.",
        type_str="env_path",
    )

    XONSH_CONFIG_DIR = Var.with_default(
        xonsh_config_dir,
        "This is the location where xonsh user-level configuration information is stored.",
        is_configurable=False,
        type_str="str",
    )
    XONSH_SYS_CONFIG_DIR = Var.with_default(
        xonsh_sys_config_dir,
        "This is the location where xonsh system-level configuration information is stored.",
        is_configurable=False,
        type_str="str",
    )
    XONSH_COLOR_STYLE = Var.with_default(
        "default",
        "Sets the color style for xonsh colors. This is a style name, not "
        "a color map. Run ``xonfig styles`` to see the available styles.",
        type_str="str",
    )

    XONSH_DEBUG = Var(
        always_false,
        to_debug,
        bool_or_int_to_str,
        0,
        "Sets the xonsh debugging level. This may be an integer or a boolean. "
        "Setting it to ``1`` will get some basic information like input transformation, command replacement. "
        "With ``2`` or a higher number will make more debugging information "
        "presented, like PLY parsing messages.",
        is_configurable=False,
    )
    XONSH_DATA_DIR = Var.with_default(
        xonsh_data_dir,
        "This is the location where xonsh data files are stored, such as history, generated completers ...",
        doc_default="``$XDG_DATA_HOME/xonsh``",
        type_str="str",
    )

    XONSH_ENCODING = Var.with_default(
        DEFAULT_ENCODING,
        "This is the encoding that xonsh should use for subprocess operations.",
        doc_default="``sys.getdefaultencoding()``",
        type_str="str",
    )
    XONSH_ENCODING_ERRORS = Var.with_default(
        "surrogateescape",
        "The flag for how to handle encoding errors should they happen. "
        "Any string flag that has been previously registered with Python "
        "is allowed. See the 'Python codecs documentation' "
        "(https://docs.python.org/3/library/codecs.html#error-handlers) "
        "for more information and available options.",
        doc_default="``surrogateescape``",
        type_str="str",
    )
    XONSH_INTERACTIVE = Var.with_default(
        True,
        "``True`` if xonsh is running interactively, and ``False`` otherwise. "
        "It's highly recommended to use this variable in your ``xonshrc`` files "
        "to split the code execution for interactive and non-interactive modes.",
        is_configurable=False,
    )
    XONSH_LOGIN = Var.with_default(
        False,
        "``True`` if xonsh is running as a login shell, and ``False`` otherwise.",
        is_configurable=False,
    )

    XONSH_MODE = Var.with_default(
        default="interactive",  # In sync with ``main.py``.
        doc="A string value representing the current xonsh execution mode: "
        "``interactive``, ``script_from_file``, ``source``, ``single_command``, ``script_from_stdin``."
        "Note! This variable reflects the mode at start time  (e.g. ``script_from_file``) "
        "or code execution (e.g. ``source``).  If you need to gate behavior in an RC file that "
        "you plan to ``source``, use ``$XONSH_INTERACTIVE`` as the flag instead.",
        type_str="str",
    )

    XONSH_SOURCE = Var.with_default(
        "",
        "When running a xonsh script, this variable contains the absolute path "
        "to the currently executing script's file.",
        is_configurable=False,
    )
    XONSH_STORE_STDIN = Var.with_default(
        False,
        "Whether or not to store the stdin that is supplied to the "
        "``!()`` and ``![]`` operators.",
    )
    XONSH_STYLE_OVERRIDES = Var(
        is_tok_color_dict,
        to_tok_color_dict,
        dict_to_str,
        {},
        "A dictionary containing custom prompt_toolkit/pygments style definitions.\n"
        "The following style definitions are supported:\n\n"
        "    - ``pygments.token.Token`` - ``$XONSH_STYLE_OVERRIDES[Token.Keyword] = '#ff0000'``\n"
        "    - pygments token name (string) - ``$XONSH_STYLE_OVERRIDES['Token.Keyword'] = '#ff0000'``\n"
        "    - ptk style name (string) - ``$XONSH_STYLE_OVERRIDES['pygments.keyword'] = '#ff0000'``\n\n"
        "(The rules above are all have the same effect.)",
    )

    STAR_PATH = Var.no_default("env_path", pattern=re.compile(r"\w*PATH$"))
    STAR_DIRS = Var.no_default("env_path", pattern=re.compile(r"\w*DIRS$"))


class SubprocessSetting(Xettings):
    """Subprocess Settings"""

    RAISE_SUBPROC_ERROR = Var.with_default(
        False,
        "Whether or not to raise an error if a subprocess (captured or "
        "uncaptured) returns a non-zero exit status, which indicates failure. "
        "This is most useful in xonsh scripts or modules where failures "
        "should cause an end to execution. This is less useful at a terminal. "
        "The error that is raised is a ``subprocess.CalledProcessError``.",
    )
    LAST_RETURN_CODE = Var.with_default(
        0,
        "Integer return code of the last command. Only updated during interactive use, i.e. not during execution of scripts.",
    )
    XONSH_SUBPROC_CAPTURED_PRINT_STDERR = Var.with_default(
        False,
        "If ``True`` the stderr from captured subproc will be printed automatically.",
    )
    XONSH_SUBPROC_OUTPUT_FORMAT = Var.with_default(
        "stream_lines",
        "Set output format for subprocess e.g. ``du $(ls)``. "
        "By default (``stream_lines``) subprocess operator returns text output. "
        "Set ``list_lines`` to have list of lines.",
    )

    XONSH_CAPTURE_ALWAYS = Var.with_default(
        False,
        "Try to capture output of commands run without explicit capturing.\n"
        "If True, xonsh will capture the output of commands run directly or in ``![]``"
        "to the session history.\n"
        "Setting to True has the following disadvantages:\n"
        "* Some interactive commands won't work properly (like when ``git`` invokes an interactive editor).\n"
        "  For more information see discussion at https://github.com/xonsh/xonsh/issues/3672.\n"
        "* Stopping these commands with ^Z (i.e. ``SIGTSTP``)\n"
        "  is disabled as it causes deadlocked terminals.\n"
        "  ``SIGTSTP`` may still be issued and only the physical pressing\n"
        "  of ``Ctrl+Z`` is ignored.\n\n"
        "Regardless of this value, commands run in ``$()``, ``!()`` or with an IO redirection (``>`` or ``|``) "
        "will always be captured.\n"
        "Setting this to True depends on ``$THREAD_SUBPROCS`` being True.",
    )
    THREAD_SUBPROCS = Var(
        is_bool_or_none,
        to_bool_or_none,
        bool_or_none_to_str,
        not ON_CYGWIN,
        "Note: The ``$XONSH_CAPTURE_ALWAYS`` variable introduces finer control "
        "and you should probably use that instead.\n\n"
        "Whether or not to try to run subrocess mode in a Python thread, "
        "when trying to capture its output. There are various trade-offs.\n\n"
        "If True, xonsh is able capture & store the stdin, stdout, and stderr"
        " of threadable subprocesses.\n"
        "The disadvantages are listed in ``$XONSH_CAPTURE_ALWAYS``.\n"
        "The desired effect is often up to the command, user, or use case.\n\n"
        "None values are for internal use only and are used to turn off "
        "threading when loading xonshrc files. This is done because Bash "
        "was automatically placing new xonsh instances in the background "
        "at startup when threadable subprocs were used. Please see "
        "https://github.com/xonsh/xonsh/pull/3705 for more information.\n",
    )
    XONSH_APPEND_NEWLINE = Var.with_default(
        xonsh_append_newline,
        "Append new line when a partial line is preserved in output.",
        doc_default="``$XONSH_INTERACTIVE``",
        type_str="bool",
    )
    XONSH_PROC_FREQUENCY = Var.with_default(
        1e-4,
        "The process frequency is the time that "
        "xonsh process threads sleep for while running command pipelines. "
        "The value has units of seconds [s].",
    )
    XONSH_TRACE_SUBPROC = Var(
        default=False,
        validate=is_bool_or_int,
        convert=to_bool_or_int,
        doc="Set to ``True`` or ``1`` to show arguments list of every executed subprocess command. "
        "Use ``2`` to have a specification. Use ``3`` to have full specification.",
    )
    XONSH_TRACE_SUBPROC_FUNC = Var.with_default(
        None,
        doc=(
            "A callback function used to format the trace output shown when $XONSH_TRACE_SUBPROC=True."
        ),
        doc_default="""\
    By default it just prints ``cmds`` like below.

    .. code-block:: python

        def tracer(cmds: list, captured: Union[bool, str]):
            print(f"TRACE SUBPROC: {cmds}, captured={captured}", file=sys.stderr)
    """,
    )


class ErrorHandlingSetting(Xettings):
    """Error Handling Settings"""

    XONSH_SHOW_TRACEBACK = Var.with_default(
        False,
        "Controls if a traceback is shown if exceptions occur in the shell. "
        "Set to ``True`` to always show traceback or ``False`` to always hide. "
        "If undefined then the traceback is hidden but a notice is shown on how "
        "to enable the full traceback.",
    )
    XONSH_TRACEBACK_LOGFILE = Var(
        is_logfile_opt,
        to_logfile_opt,
        logfile_opt_to_str,
        None,
        "Specifies a file to store the traceback log to, regardless of whether "
        "``XONSH_SHOW_TRACEBACK`` has been set. Its value must be a writable file "
        "or None / the empty string if traceback logging is not desired. "
        "Logging to a file is not enabled by default.",
    )


class JobsSetting(Xettings):
    """Jobs Settings"""

    AUTO_CONTINUE = Var.with_default(
        False,
        "If ``True``, automatically resume stopped jobs when they are disowned. "
        "When stopped jobs are disowned and this option is ``False``, a warning "
        "will print information about how to continue the stopped process.",
    )


class LangSetting(Xettings):
    """Language and locale settings."""

    LANG = Var.with_default(
        default="C.UTF-8",
        doc="Fallback locale setting for systems where it matters",
        type_str="str",
    )
    LC_COLLATE = Var.for_locale("LC_COLLATE")
    LC_CTYPE = Var.for_locale("LC_CTYPE")
    LC_MONETARY = Var.for_locale("LC_MONETARY")
    LC_NUMERIC = Var.for_locale("LC_NUMERIC")
    LC_TIME = Var.for_locale("LC_TIME")
    if hasattr(locale, "LC_MESSAGES"):
        LC_MESSAGES = Var.for_locale("LC_MESSAGES")

    XONSH_DATETIME_FORMAT = Var.with_default(
        "%Y-%m-%d %H:%M",
        "The format that is used for ``datetime.strptime()`` in various places, "
        "i.e the history timestamp option.",
        type_str="str",
    )


class CacheSetting(Xettings):
    """Cache Settings"""

    XONSH_CACHE_SCRIPTS = Var.with_default(
        True,
        "Controls whether the code for scripts run from xonsh will be cached"
        " (``True``) or re-compiled each time (``False``).",
    )

    XONSH_CACHE_EVERYTHING = Var.with_default(
        False,
        "Controls whether all code (including code entered at the interactive"
        " prompt) will be cached.",
    )

    XONSH_CACHE_DIR = Var.with_default(
        xonsh_cache_dir,
        "This is the location where cache files used by xonsh are stored, such as commands-cache...",
        doc_default="``$XDG_CACHE_HOME/xonsh``",
        type_str="str",
    )

    ENABLE_COMMANDS_CACHE = Var(
        default=True,
        doc="command names in a directory are cached when enabled. "
        "On some platforms it may not be accurate enough"
        "(e.g. Windows, Linux save mtime in seconds). "
        "Setting it to False would disable the caching mechanism "
        "and may slow down the shell",
        doc_default="True",
    )

    COMMANDS_CACHE_SAVE_INTERMEDIATE = Var.with_default(
        False,
        "If enabled, the CommandsCache is saved between runs and can reduce the startup time.",
    )


class ChangeDirSetting(Xettings):
    """``cd`` Behavior"""

    AUTO_CD = Var.with_default(
        False,
        doc="Flag to enable changing to a directory by entering the dirname or "
        "full path only (without the cd command).",
    )
    AUTO_PUSHD = Var.with_default(
        False,
        doc="Flag for automatically pushing directories onto the directory stack.",
    )
    CDPATH = Var.with_default(
        (),
        "A list of paths to be used as roots for a cd, breaking compatibility "
        "with Bash, xonsh always prefer an existing relative path.",
        type_str="env_path",
    )
    DIRSTACK_SIZE = Var.with_default(
        20,
        "Maximum size of the directory stack.",
    )
    PUSHD_MINUS = Var.with_default(
        False,
        "Flag for directory pushing functionality. False is the normal behavior.",
    )
    PUSHD_SILENT = Var.with_default(
        False,
        "Whether or not to suppress directory stack manipulation output.",
    )
    COMPLETE_DOTS = Var.with_default(
        "matching",
        doc="Flag to specify how current and previous directories should be "
        "tab completed  ('./', '../'):\n"
        "    - ``always`` Always complete paths with ./ and ../\n"
        "    - ``never`` Never complete paths with ./ and ../\n"
        "    - ``matching`` Complete if path starts with . or ..",
    )


class InterpreterSetting(Xettings):
    """Interpreter Behavior"""

    DOTGLOB = Var.with_default(
        False,
        'Globbing files with "*" or "**" will also match '
        "dotfiles, or those 'hidden' files whose names "
        "begin with a literal '.'. Such files are filtered "
        "out by default.",
    )
    EXPAND_ENV_VARS = Var.with_default(
        True,
        "Toggles whether environment variables are expanded inside of strings "
        "in subprocess mode.",
    )
    FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE = Var.with_default(
        False,
        "Whether or not foreign aliases should suppress the message "
        "that informs the user when a foreign alias has been skipped "
        "because it already exists in xonsh.",
        is_configurable=True,
    )
    FOREIGN_ALIASES_OVERRIDE = Var.with_default(
        False,
        "Whether or not foreign aliases should override xonsh aliases "
        "with the same name. Note that setting of this must happen in the "
        "environment that xonsh was started from. "
        "It cannot be set in the ``.xonshrc`` as loading of foreign aliases happens before"
        "``.xonshrc`` is parsed",
        is_configurable=True,
    )
    GLOB_SORTED = Var.with_default(
        True,
        "Toggles whether globbing results are manually sorted. If ``False``, "
        "the results are returned in arbitrary order.",
    )


class XontribSetting(Xettings):
    """Xontrib Settings"""

    XONTRIBS_AUTOLOAD_DISABLED = Var.with_default(
        default=False,
        type_str="bool",
        doc="""\
    Controls auto-loading behaviour of xontrib packages at the startup.
    * Set this to ``True`` to disable autoloading completely.
    * Setting this to a list of xontrib names will block loading those specifically.
    """,
        doc_default="""\
    Xontribs with ``xonsh.xontrib`` entrypoint will be loaded automatically by default.
    """,
    )


class PromptSetting(Xettings):
    """Interactive Prompt"""

    COLOR_INPUT = Var.with_default(
        True,
        "Flag for syntax highlighting interactive input.",
    )
    COLOR_RESULTS = Var.with_default(
        True,
        "Flag for syntax highlighting return values.",
    )
    DYNAMIC_CWD_WIDTH = Var(
        is_dynamic_cwd_width,
        to_dynamic_cwd_tuple,
        dynamic_cwd_tuple_to_str,
        (float("inf"), "c"),
        "Maximum length in number of characters "
        "or as a percentage for the ``cwd`` prompt variable. For example, "
        '"20" is a twenty character width and "10%" is ten percent of the '
        "number of columns available.",
    )
    DYNAMIC_CWD_ELISION_CHAR = Var.with_default(
        "",
        "The string used to show a shortened directory in a shortened cwd, "
        "e.g. ``'…'``.",
    )
    IGNOREEOF = Var.with_default(
        False,
        "Prevents Ctrl-D from exiting the shell.",
    )
    INDENT = Var.with_default(
        "    ",
        "Indentation string for multiline input",
    )
    LS_COLORS = Var(
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
    )
    MULTILINE_PROMPT = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        " ",
        "Prompt text for 2nd+ lines of input, may be str or function which "
        "returns a str.",
    )
    MULTILINE_PROMPT_PRE = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        DefaultNotGiven,
        "Indicator inserted before the line continuation marks set "
        "in ``$MULTILINE_PROMPT``. Can be used to mark the start of "
        "a semantic continuation prompt "
        "(see `Semantic Prompts <https://gitlab.freedesktop.org/Per_Bothner/specifications/blob/master/proposals/semantic-prompts.md>`_ "
        "or `WezTerm <https://wezfurlong.org/wezterm/shell-integration.html>`_ "
        "for more details). May be str or function which returns a str.",
    )
    MULTILINE_PROMPT_POS = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        DefaultNotGiven,
        "Indicator inserted after the line continuation marks set "
        "in ``$MULTILINE_PROMPT``. Can be used to mark the end of "
        "a semantic continuation prompt and the beginning of user input "
        "(see `Semantic Prompts <https://gitlab.freedesktop.org/Per_Bothner/specifications/blob/master/proposals/semantic-prompts.md>`_ "
        "or `WezTerm <https://wezfurlong.org/wezterm/shell-integration.html>`_ "
        "for more details). May be str or function which returns a str.",
    )
    PRETTY_PRINT_RESULTS = Var.with_default(
        True,
        'Flag for "pretty printing" return values.',
    )
    PROMPT = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        prompt.default_prompt(),
        "The prompt text. May contain keyword arguments which are "
        "auto-formatted, see 'Customizing the Prompt' at "
        "http://xon.sh/tutorial.html#customizing-the-prompt. "
        "This value is never inherited from parent processes.",
        doc_default="``xonsh.environ.DEFAULT_PROMPT``",
    )
    PROMPT_FIELDS = Var.with_default(
        default_prompt_fields,
        validate=always_true,
        convert=None,
        detype=None,
        doc="Dictionary containing variables to be used when formatting $PROMPT "
        "and $TITLE. See 'Customizing the Prompt' "
        "http://xon.sh/tutorial.html#customizing-the-prompt",
        is_configurable=False,
    )
    PROMPT_REFRESH_INTERVAL = Var.with_default(
        0.0,  # keep as float
        "Interval (in seconds) to evaluate and update ``$PROMPT``, ``$RIGHT_PROMPT`` "
        "and ``$BOTTOM_TOOLBAR``. The default is zero (no update). "
        "NOTE: ``$UPDATE_PROMPT_ON_KEYPRESS`` must be set to ``True`` for this "
        "variable to take effect.",
    )
    PROMPT_TOKENS_FORMATTER = Var(
        validate=callable,
        convert=None,
        detype=None,
        default=prompt.prompt_tokens_formatter_default,
        doc="Final processor that receives all tokens in the prompt template. "
        "It gives option to format the prompt with different prefix based on other tokens values. "
        "Highly useful for implementing something like powerline theme.",
        doc_default="``xonsh.prompt.base.prompt_tokens_formatter_default``",
    )
    RIGHT_PROMPT = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        "",
        "Template string for right-aligned text "
        "at the prompt. This may be parametrized in the same way as "
        "the ``$PROMPT`` variable. Currently, this is only available in the "
        "prompt-toolkit shell.",
    )
    BOTTOM_TOOLBAR = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        "",
        "Template string for the bottom toolbar. "
        "This may be parametrized in the same way as "
        "the ``$PROMPT`` variable. Currently, this is only available in the "
        "prompt-toolkit shell.",
    )
    SHELL_TYPE = Var.with_default(
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
        "the run control file. "
        "It also accepts a class type that inherits from ``xonsh.shells.base_shell.BaseShell``",
        doc_default="``best``",
    )
    SUGGEST_COMMANDS = Var.with_default(
        True,
        "When a user types an invalid command, xonsh will try to offer "
        "suggestions of similar valid commands if this is True.",
    )
    SUGGEST_MAX_NUM = Var.with_default(
        5,
        "xonsh will show at most this many suggestions in response to an "
        "invalid command. If negative, there is no limit to how many "
        "suggestions are shown.",
    )
    SUGGEST_THRESHOLD = Var.with_default(
        3,
        "An error threshold. If the Levenshtein distance between the entered "
        "command and a valid command is less than this value, the valid "
        'command will be offered as a suggestion.  Also used for "fuzzy" '
        "tab completion of paths.",
    )
    SUPPRESS_BRANCH_TIMEOUT_MESSAGE = Var.with_default(
        False,
        "Whether or not to suppress branch timeout warning messages when getting {gitstatus} PROMPT_FIELD.",
    )
    TITLE = Var(
        is_string_or_callable,
        ensure_string,
        ensure_string,
        DEFAULT_TITLE,
        "The title text for the window in which xonsh is running. Formatted "
        "in the same manner as ``$PROMPT``, see 'Customizing the Prompt' "
        "http://xon.sh/tutorial.html#customizing-the-prompt.",
        doc_default="``xonsh.environ.DEFAULT_TITLE``",
    )
    UPDATE_PROMPT_ON_KEYPRESS = Var.with_default(
        False,
        "Disables caching the prompt between commands, "
        "so that it would be reevaluated on each keypress. "
        "Disabled by default because of the incurred performance penalty.",
    )
    VC_BRANCH_TIMEOUT = Var.with_default(
        0.2 if ON_WINDOWS else 0.1,
        "The timeout (in seconds) for version control "
        "branch computations. This is a timeout per subprocess call, so the "
        "total time to compute will be larger than this in many cases.",
    )
    VC_GIT_INCLUDE_UNTRACKED = Var.with_default(
        False,
        "Whether or not untracked file changes should count as 'dirty' in git.",
    )
    VC_HG_SHOW_BRANCH = Var.with_default(
        True,
        "Whether or not to show the Mercurial branch in the prompt.",
    )
    VIRTUAL_ENV = Var.no_default(
        "str",
        "Path to the currently active Python environment.",
        is_configurable=False,
    )
    XONSH_HISTORY_MATCH_ANYWHERE = Var.with_default(
        False,
        "When searching history from a partial string (by pressing up arrow), "
        "match command history anywhere in a given line (not just the start)",
        doc_default="False",
    )
    XONSH_STDERR_PREFIX = Var.with_default(
        "",
        "A format string, using the same keys and colors as ``$PROMPT``, that "
        "is prepended whenever stderr is displayed. This may be used in "
        "conjunction with ``$XONSH_STDERR_POSTFIX`` to close out the block."
        "For example, to have stderr appear on a red background, the "
        'prefix & postfix pair would be "{BACKGROUND_RED}" & "{RESET}".',
    )
    XONSH_STDERR_POSTFIX = Var.with_default(
        "",
        "A format string, using the same keys and colors as ``$PROMPT``, that "
        "is appended whenever stderr is displayed. This may be used in "
        "conjunction with ``$XONSH_STDERR_PREFIX`` to start the block."
        "For example, to have stderr appear on a red background, the "
        'prefix & postfix pair would be "{BACKGROUND_RED}" & "{RESET}".',
    )
    XONSH_SUPPRESS_WELCOME = Var.with_default(
        False,
        "Suppresses the welcome message.",
    )


class PromptHistorySetting(Xettings):
    """Interactive Prompt History"""

    XONSH_HISTORY_BACKEND = Var(
        is_history_backend,
        to_itself,
        ensure_string,
        "json",
        "Set which history backend to use. Options are: 'json', "
        "'sqlite', and 'dummy'. The default is 'json'. "
        "``XONSH_HISTORY_BACKEND`` also accepts a class type that inherits "
        "from ``xonsh.history.base.History``, or its instance.",
    )
    XONSH_HISTORY_FILE = Var.with_default(
        None,
        "Location of history file set by history backend (default) or set by the user.",
        is_configurable=False,
        doc_default="None",
        type_str="path",
    )
    HISTCONTROL = Var(
        is_string_set,
        csv_to_set,
        set_to_csv,
        set(),
        "A set of strings (comma-separated list in string form) of options "
        "that determine what commands are saved to the history list. By "
        "default all commands are saved. Options are as follows:\n\n"
        "- ``ignoredups`` will not save the command if it matches the previous command\n"
        "- ``ignoreerr`` will cause any commands that fail (i.e. return non-zero "
        "exit status) to not be added to the history list\n"
        "- ``ignorespace`` will not save the command if it begins with a space\n"
        "- ``erasedups`` will remove all previous commands that matches and updates the frequency "
        "(Note: only supported in sqlite backend)",
        can_store_as_str=True,
    )
    XONSH_HISTORY_SIZE = Var(
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
    )
    XONSH_STORE_STDOUT = Var.with_default(
        False,
        "Store the ``stdout`` and ``stderr`` streams to the history. "
        "Requires that XONSH_CAPTURE_ALWAYS is True.",
    )
    XONSH_HISTORY_SAVE_CWD = Var.with_default(
        True,
        "Save current working directory to the history.",
        doc_default="True",
    )
    XONSH_HISTORY_IGNORE_REGEX = Var(
        is_regex,
        to_itself,
        ensure_string,
        None,
        "Set a filter criteria for history items using a regular expression. "
        "Any matching items will not be retained in the history. "
        "Example: ``$XONSH_HISTORY_IGNORE_REGEX = '(^echo|^.*\\#\\#\\#\\s*|.*\\#\\#\\#\\s*$)'``"
        " - skip commands that start from ``echo`` or ``###``, or end from ``###``.",
    )
    XONSH_HISTORY_SIGINT_FLUSH = Var.with_default(
        True,
        "Save history after getting SIGINT (Ctrl+C).",
        doc_default="True",
    )


class PTKSetting(PromptSetting):  # sub-classing -> sub-group
    """Prompt Toolkit shell
    Only usable with ``$SHELL_TYPE=prompt_toolkit.``
    """

    AUTO_SUGGEST = Var.with_default(
        True,
        "Enable automatic command suggestions based on history."
        "\n\nPressing the right arrow key inserts the currently "
        "displayed suggestion. ",
    )
    AUTO_SUGGEST_IN_COMPLETIONS = Var.with_default(
        False,
        "Places the auto-suggest result as the first option in the completions. "
        "This enables you to tab complete the auto-suggestion.",
    )
    MOUSE_SUPPORT = Var.with_default(
        False,
        "Enable mouse support in the ``prompt_toolkit`` shell. This allows "
        "clicking for positioning the cursor or selecting a completion. In "
        "some terminals however, this disables the ability to scroll back "
        "through the history of the terminal. Only usable with "
        "``$SHELL_TYPE=prompt_toolkit``",
    )
    PROMPT_TOOLKIT_COLOR_DEPTH = Var(
        always_false,
        ptk2_color_depth_setter,
        ensure_string,
        "",
        "The color depth used by prompt toolkit 2. Possible values are: "
        "``DEPTH_1_BIT``, ``DEPTH_4_BIT``, ``DEPTH_8_BIT``, ``DEPTH_24_BIT`` "
        "colors. Default is an empty string which means that prompt toolkit decide.",
    )
    PTK_STYLE_OVERRIDES = Var(
        is_tok_color_dict,
        to_tok_color_dict,
        dict_to_str,
        {},
        "A dictionary containing custom prompt_toolkit style definitions. (deprecated)",
    )
    VI_MODE = Var.with_default(
        False,
        "Flag to enable ``vi_mode`` in the ``prompt_toolkit`` shell.",
    )
    XONSH_AUTOPAIR = Var.with_default(
        False,
        "Whether Xonsh will auto-insert matching parentheses, brackets, and "
        "quotes. Only available under the prompt-toolkit shell.",
    )
    XONSH_COPY_ON_DELETE = Var.with_default(
        False,
        "Whether to copy words/lines to clipboard on deletion (must be set in the run control file)."
        "Does not have any effect in ``vi_mode``."
        "Only available under the prompt-toolkit shell.",
    )
    XONSH_USE_SYSTEM_CLIPBOARD = Var.with_default(
        True,
        "Whether to let the shell use the system clipboard (must be set in the run control file)."
        "The main use-case is to fully disable clipboard integration in ``vi_mode``."
        "Only available under the prompt-toolkit shell.",
    )
    XONSH_CTRL_BKSP_DELETION = Var.with_default(
        False,
        "Delete a word on CTRL-Backspace (like ALT-Backspace). "
        r"This will only work when your terminal emulator sends ``\x7f`` on backspace and "
        r"``\x08`` on CTRL-Backspace (which is configurable on most terminal emulators). "
        r"On windows, the keys are reversed.",
    )


class AsyncPromptSetting(PTKSetting):
    """Asynchronous Prompt
    Load $PROMPT in background without blocking read-eval loop.
    """

    ASYNC_INVALIDATE_INTERVAL = Var.with_default(
        0.05,
        "When ENABLE_ASYNC_PROMPT is True, it may call the redraw frequently. "
        "This is to group such calls into one that happens within that timeframe. "
        "The number is set in seconds.",
    )
    ASYNC_PROMPT_THREAD_WORKERS = Var(
        is_int,
        to_int_or_none,
        str,
        None,
        "Define the number of workers used by the ASYNC_PROMPT's pool. "
        "By default it is the same as defined by Python's concurrent.futures.ThreadPoolExecutor class.",
    )
    ENABLE_ASYNC_PROMPT = Var.with_default(
        False,
        "When enabled the prompt is rendered using threads. "
        "$PROMPT_FIELD that take long will be updated in the background and will not affect prompt speed. ",
    )


class AutoCompletionSetting(Xettings):
    """Tab-completion behavior."""

    ALIAS_COMPLETIONS_OPTIONS_BY_DEFAULT = Var.with_default(
        doc="""\
If True, :py:class:`xonsh.completers.argparser.ArgparseCompleter` based completions
will show options (e.g. -h, ...) without requesting explicitly with option prefix (e.g. '-').""",
        default=False,
    )
    ALIAS_COMPLETIONS_OPTIONS_LONGEST = Var.with_default(
        doc="""\
Whether to show all options or just the longest for
the :py:class:`xonsh.completers.argparser.ArgparseCompleter` based completions.
For example, with ``-h``, ``--help`` both denoting ``help`` action.
If True, then only ``--help`` is shown.
This is to reduce the noise in generated completions.""",
        default=False,
    )
    CMD_COMPLETIONS_SHOW_DESC = Var.with_default(
        doc="If True, command completions will show description part with path to the binary and alias in case of "
        "xonsh functions.",
        default=False,
        type_str="bool",
    )
    BASH_COMPLETIONS = Var.with_default(
        doc="This is a list (or tuple) of strings that specifies where the "
        "``bash_completion`` script may be found. "
        "The first valid path will be used. For better performance, "
        "bash-completion v2.x is recommended since it lazy-loads individual "
        "completion scripts. "
        "For both bash-completion v1.x and v2.x, paths of individual completion "
        "scripts (like ``.../completes/ssh``) do not need to be included here. "
        "The default values are platform "
        "dependent, but reasonable. To specify an alternate list, do so in the run "
        "control file.",
        default=BASH_COMPLETIONS_DEFAULT,
        doc_default=(
            "Normally this is:\n\n"
            "    ``('/usr/share/bash-completion/bash_completion', )``\n\n"
            "But, on Mac it is:\n\n"
            "    ``('/usr/local/share/bash-completion/bash_completion', "
            "'/usr/local/etc/bash_completion', "
            "'/opt/homebrew/share/bash-completion/bash_completion'),``\n\n"
            "Other OS-specific defaults may be added in the future."
        ),
        type_str="env_path",
    )
    CASE_SENSITIVE_COMPLETIONS = Var.with_default(
        ON_LINUX,
        "Sets whether completions should be case sensitive or case " "insensitive.",
        doc_default="True on Linux, False otherwise.",
    )
    COMPLETIONS_BRACKETS = Var.with_default(
        True,
        "Flag to enable/disable inclusion of square brackets and parentheses "
        "in Python attribute completions.",
        doc_default="True",
    )
    COMPLETION_QUERY_LIMIT = Var.with_default(
        100,
        "The number of completions to display before the user is asked "
        "for confirmation.",
    )
    FUZZY_PATH_COMPLETION = Var.with_default(
        True,
        "Toggles 'fuzzy' matching of paths for tab completion, which is only "
        "used as a fallback if no other completions succeed but can be used "
        "as a way to adjust for typographical errors. If ``True``, then, e.g.,"
        " ``xonhs`` will match ``xonsh``.",
    )
    SUBSEQUENCE_PATH_COMPLETION = Var.with_default(
        True,
        "Toggles subsequence matching of paths for tab completion. "
        "If ``True``, then, e.g., ``~/u/ro`` can match ``~/lou/carcolh``.",
    )
    XONSH_BASH_PATH_OVERRIDE = Var.with_default(
        None,
        doc="Override the path used to call bash externally. This allows "
        "a user to choose which bash executable to call for ``source-bash`` "
        "and any bash completions that are configured. "
        "This variable overrides the default settings in "
        "``xonsh.platform.bash_command``.",
        doc_default="None",
    )
    XONSH_COMPLETER_DIRS = Var.with_default(
        default_completer_dirs,
        """\
A list of paths where Xonsh searches for command completions.
Any completions defined are lazy loaded when needed.
The name of the completer file should match that of the completing command.
The file should contain a function with the signature
``xonsh_complete(ctx: CommandContext) -> Iterator[RichCompletion|str]``.
""",
        type_str="env_path",
    )
    XONSH_TRACE_COMPLETIONS = Var.with_default(
        False,
        "Set to ``True`` to show completers invoked and their return values.",
    )


class PTKCompletionSetting(AutoCompletionSetting):
    """Prompt Toolkit tab-completion"""

    COMPLETIONS_CONFIRM = Var.with_default(
        True,
        "While tab-completions menu is displayed, press <Enter> to confirm "
        "completion instead of running command. This only affects the "
        "prompt-toolkit shell.",
    )

    COMPLETIONS_DISPLAY = Var(
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
    )
    COMPLETIONS_MENU_ROWS = Var.with_default(
        5,
        "Number of rows to reserve for tab-completions menu if "
        "``$COMPLETIONS_DISPLAY`` is ``single`` or ``multi``. This only affects the "
        "prompt-toolkit shell.",
    )
    COMPLETION_MODE = Var(
        is_completion_mode,
        to_completion_mode,
        str,
        "default",
        "Mode of tab completion in prompt-toolkit shell (only).\n\n"
        "'default', the default, selects the common prefix of completions on first TAB,\n"
        "then cycles through all completions.\n"
        "'menu-complete' selects the first whole completion on the first TAB, \n"
        "then cycles through the remaining completions, then the common prefix.",
    )
    COMPLETION_IN_THREAD = Var.with_default(
        False,
        "When generating the completions takes time, "
        "it’s better to do this in a background thread. "
        "When this is True, background threads is used for completion.",
    )
    UPDATE_COMPLETIONS_ON_KEYPRESS = Var.with_default(
        False,
        "Completions display is evaluated and presented whenever a key is "
        "pressed. This avoids the need to press TAB, except to cycle through "
        "the possibilities. This currently only affects the prompt-toolkit shell.",
    )


class WindowsSetting(GeneralSetting):
    """Windows OS
    Windows OS specific settings
    """

    ANSICON = Var.no_default(
        "str",
        "This is used on Windows to set the title, if available.",
        is_configurable=False,
    )
    FORCE_POSIX_PATHS = Var.with_default(
        False,
        "Forces forward slashes (``/``) on Windows systems when using auto "
        "completion if set to anything truthy.",
        is_configurable=ON_WINDOWS,
    )
    INTENSIFY_COLORS_ON_WIN = Var(
        always_false,
        intensify_colors_on_win_setter,
        bool_to_str,
        True,
        "Enhance style colors for readability "
        "when using the default terminal (``cmd.exe``) on Windows. Blue colors, "
        "which are hard to read, are replaced with cyan. Other colors are "
        "generally replaced by their bright counter parts.",
        is_configurable=ON_WINDOWS,
    )


# Please keep the following in alphabetic order - scopatz
@lazyobject
def DEFAULT_VARS():
    dv = {}
    for _, vars in Xettings.get_groups():
        for key, var in vars:
            dv[key] = var
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

    def __init__(self, *args, **kwargs):
        """If no initial environment is given, os_environ is used."""
        self._d = InternalEnvironDict()
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
            if path_key is not None:
                self["PATH"] = self._d.pop(path_key)
        if "PATH" not in self._d:
            # this is here so the PATH is accessible to subprocs and so that
            # it can be modified in-place in the xonshrc file
            self._d["PATH"] = list(PATH_DEFAULT)
        self._detyped = None

    def get_detyped(self, key: str):
        detyped = self.detype()
        return detyped.get(key)

    def detype(self):
        """
        Returns a dict of detyped variables.
        Note! If env variable wasn't explicitly set (e.g. the value has default value in ``Xettings``)
        it will be not in this list.
        """
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

    def detype_all(self):  # __getitem__
        """Returns a dict of all available detyped env variables."""
        if self._detyped is not None:
            return self._detyped
        ctx = {}
        for key in self.rawkeys():
            if not isinstance(key, str):
                key = str(key)
            val = self.__getitem__(key)
            detyper = self.get_detyper(key)
            if detyper is not None:
                val = detyper(val)
            if not isinstance(val, str):
                continue
            ctx[key] = val
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
        if key in self._vars and self._vars[key].default is not DefaultNotGiven:
            return self._vars[key].default
        else:
            return default

    def get_docs(self, key, default=None):
        """Gets the documentation for the environment variable."""
        vd = self._vars.get(key, default)
        if vd is None:
            vd = Var(default="", doc_default="")
        if vd.doc_default is DefaultNotGiven:
            var_default = self._vars.get(key, "<default not set>").default
            dval = (
                "not defined"
                if var_default is DefaultNotGiven
                else pprint.pformat(var_default)
            )
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
            configurable=vardocs.is_configurable,
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
        The changes are only applied to the current thread, so that they don't leak between threads.
        To get the thread-local overrides use `get_swapped_values` and `set_swapped_values`.
        """
        old = {}
        # single positional argument should be a dict-like object
        if other is not None:
            for k, v in other.items():
                old[k] = self.get(k, NotImplemented)
                self._set_item(k, v, thread_local=True)
        # kwargs could also have been sent in
        for k, v in kwargs.items():
            old[k] = self.get(k, NotImplemented)
            self._set_item(k, v, thread_local=True)

        exception = None
        try:
            yield self
        except Exception as e:
            exception = e
        finally:
            # restore the values
            for k, v in old.items():
                if v is NotImplemented:
                    self._del_item(k, thread_local=True)
                else:
                    self._set_item(k, v, thread_local=True)
            if exception is not None:
                raise exception from None

    def get_swapped_values(self):
        return self._d.get_local_overrides()

    def set_swapped_values(self, swapped_values):
        self._d.set_local_overrides(swapped_values)

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        if key is Ellipsis:
            return self
        elif key in self._d:
            val = self._d[key]
        elif key in self._vars and self._vars[key].default is not DefaultNotGiven:
            val = self.get_default(key)
            if is_callable_default(val):
                val = self._d[key] = val(self)
        else:
            e = "Unknown environment variable: ${}"
            raise KeyError(e.format(key))
        if isinstance(
            val, (cabc.MutableSet, cabc.MutableSequence, cabc.MutableMapping)
        ):
            self._detyped = None
        return val

    def __setitem__(self, key, val):
        self._set_item(key, val)

    def _set_item(self, key, val, thread_local=False):
        validator = self.get_validator(key)
        converter = self.get_converter(key)
        detyper = self.get_detyper(key)
        if not validator(val):
            val = converter(val)
        # existing envvars can have any value including None
        old_value = self._d[key] if key in self._d else self._no_value
        if thread_local:
            self._d.set_locally(key, val)
        else:
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
        self._del_item(key)

    def _del_item(self, key, thread_local=False):
        if key in self._d:
            if thread_local:
                self._d.del_locally(key)
            else:
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
        if key in self._d or (
            key in self._vars and self._vars[key].default is not DefaultNotGiven
        ):
            return self[key]
        else:
            return default

    def get_stringified(self, key, default=None):
        value = self.get(key, default)
        detyper = self.get_detyper(key)
        return detyper(value)

    def rawkeys(self):
        """An iterator that returns all environment keys in their original form.
        This include string & compiled regular expression keys.
        """
        yield from (
            set(self._d)
            | {
                k
                for k in self._vars.keys()
                if self._vars[k].default is not DefaultNotGiven
            }
        )

    def __iter__(self):
        for key in self.rawkeys():
            if isinstance(key, str):
                yield key

    def __contains__(self, item):
        return item in self._d or (
            item in self._vars and self._vars[item].default is not DefaultNotGiven
        )

    def __len__(self):
        return len(self._d)

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}(...)"

    def __hash__(self) -> int:
        return hash(str(self._d))

    def _repr_pretty_(self, p, cycle):
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        with p.group(1, name + "(", ")"):
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
        is_configurable=True,
        doc_default=DefaultNotGiven,
        can_store_as_str=False,
    ):
        """Register an enviornment variable with optional type handling,
        default value, doc.

        Parameters
        ----------
        name : str
            Environment variable name to register. Typically all caps.
        type : str, optional,  {'bool', 'str', 'path', 'env_path', 'int', 'float'}
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
        is_configurable : bool, optional
            Flag for whether the environment variable is configurable or not.
        doc_default : str, optional
            Custom docstring for the default value for complex defaults.
        can_store_as_str : bool, optional
            Flag for whether the environment variable should be stored as a
            string. This is used when persisting a variable that is not JSON
            serializable to the config file. For example, sets, frozensets, and
            potentially other non-trivial data types. default, False.
        """

        if (type is not None) and (
            type in ("bool", "str", "path", "env_path", "int", "float")
        ):
            validate, convert, detype = ENSURERS[type]

        if default is not None:
            if is_callable_default(default) or validate(default):
                pass
            else:
                raise ValueError(
                    f"Default value for {name} does not match type specified "
                    "by validate and is not a callable default."
                )

        self._vars[name] = Var(
            validate,
            convert,
            detype,
            default,
            doc,
            is_configurable,
            doc_default,
            can_store_as_str,
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

    def is_configurable(self, name):
        if name not in self._vars:
            return False
        return self._vars[name].is_configurable


class InternalEnvironDict(ChainMap):
    """A dictionary which supports thread-local overrides.
    There are two reasons we can't use ChainMap directly:
    1. To use thread-local storage, we need to access the local().__dict__ directly each time to get the correct dict.
    2. We want to set items to the local storage only if they were explicitly set there.
    """

    def __init__(self):
        self._global = {}
        self._thread_local = threading.local()
        super().__init__()

    @property
    def _local(self):
        # As per local's documentation, accessing its `__dict__` works fine (but must be done inside the thread).
        return self._thread_local.__dict__

    @property  # type: ignore
    def maps(self):
        # The 'maps' array needs to contain the thread-local dictionary every time we use it.
        # We prefer getting from the local scope if possible.
        return [self._local, self._global]

    @maps.setter
    def maps(self, _v):
        # This is here for ChainMap.__init__.
        pass

    def __setitem__(self, key, value):
        # If the value is overridden locally, set it locally.
        local = self._local
        if key in local:
            local[key] = value
        else:
            self._global[key] = value

    def __delitem__(self, key):
        # If the value is overridden locally, delete it locally.
        try:
            del self._local[key]
        except KeyError:
            del self._global[key]

    def pop(self, key, *args):
        # If the value is overridden locally, pop it locally.
        try:
            return self._local.pop(key)
        except KeyError:
            return self._global.pop(key, *args)

    def popitem(self):
        # Fallback to the global dictionary if nothing is overridden locally.
        try:
            return self._local.popitem()
        except KeyError:
            return self._global.popitem()

    def set_locally(self, key, value):
        self._local[key] = value

    def del_locally(self, key):
        try:
            del self._local[key]
        except KeyError:
            pass

    def get_local_overrides(self):
        return self._local.copy()

    def set_local_overrides(self, new_local):
        local = self._local
        local.clear()
        local.update(new_local)


def locate_binary(name):
    """Locates an executable on the file system.

    NOT RECOMMENDED because ``commands_cache.locate_binary`` contains ``update_cache``
    with scanning all files in ``$PATH``. First of all take a look into ``xonsh.specs.executables``
    for more fast implementation the locate operation.
    """
    return XSH.commands_cache.locate_binary(name)


def scan_dir_for_source_files(path: str):
    if not os.path.isdir(path):
        return
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file() and (entry.name.endswith((".py", ".xsh"))):
                yield os.path.join(path, entry.name), entry


def xonshrc_context(
    rcfiles=None, rcdirs=None, execer=None, ctx=None, env=None, login=True
):
    """
    Attempts to read in all xonshrc files (and search xonshrc directories),
    and returns the list of rc file paths successfully loaded, in the order
    of loading.
    """
    loaded = []
    ctx = {} if ctx is None else ctx
    orig_thread = env.get("THREAD_SUBPROCS")
    env["THREAD_SUBPROCS"] = None
    if rcfiles is not None:
        for rcfile in rcfiles:
            if os.path.isfile(rcfile):
                status = xonsh_script_run_control(
                    rcfile, ctx, env, execer=execer, login=login
                )
                if status:
                    loaded.append(rcfile)

    if rcdirs is not None:
        for rcdir in rcdirs:
            for rcfile in sorted(dict(scan_dir_for_source_files(rcdir))):
                status = xonsh_script_run_control(
                    rcfile, ctx, env, execer=execer, login=login
                )
                if status:
                    loaded.append(rcfile)
    if env["THREAD_SUBPROCS"] is None:
        env["THREAD_SUBPROCS"] = orig_thread
    return loaded


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


class _RcPath(str):
    """A class used exclusively to know which entry was added temporarily to
    sys.path while loading rc files.
    """

    pass


def xonsh_script_run_control(filename, ctx, env, execer=None, login=True):
    """Loads a xonsh file and applies it as a run control.
    Any exceptions are logged here, returns boolean indicating success.
    """
    if execer is None:
        return False
    updates = {"__file__": filename, "__name__": os.path.abspath(filename)}
    rc_dir = _RcPath(os.path.dirname(filename))
    sys.path.append(rc_dir)
    with swap_values(ctx, updates):
        try:
            exc_info = run_script_with_cache(filename, execer, ctx)
        except SyntaxError:
            exc_info = sys.exc_info()
        if exc_info != (None, None, None):
            err_type, err, _ = exc_info
            loaded = False
            if err_type is SyntaxError:
                msg = "syntax error in xonsh run control file {0!r}: {1!s}"
            else:
                msg = "error running xonsh run control file {0!r}: {1!s}"
            print_exception(msg.format(filename, err), exc_info=exc_info)
        else:
            loaded = True
    sys.path = list(filter(lambda p: p is not rc_dir, sys.path))
    return loaded


def default_env(env=None):
    """Constructs a default xonsh environment."""
    # in order of increasing precedence
    ctx = {
        "BASH_COMPLETIONS": list(DEFAULT_VARS["BASH_COMPLETIONS"].default),
        "PROMPT_FIELDS": DEFAULT_VARS["PROMPT_FIELDS"].default(env),
        "XONSH_VERSION": XONSH_VERSION,
    }
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
    # increment $SHLVL
    old_shlvl = to_shlvl(ctx.get("SHLVL", None))
    ctx["SHLVL"] = adjust_shlvl(old_shlvl, 1)
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
