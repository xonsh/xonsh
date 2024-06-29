"""The xonsh configuration (xonfig) utility."""

import ast
import collections
import contextlib
import itertools
import json
import os
import pprint
import random
import re
import shutil
import textwrap
import typing as tp

import xonsh.wizard as wiz
from xonsh import __version__ as XONSH_VERSION
from xonsh.built_ins import XSH
from xonsh.cli_utils import Arg, ArgParserAlias
from xonsh.events import events
from xonsh.foreign_shells import CANON_SHELL_NAMES
from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers import ply
from xonsh.platform import (
    DEFAULT_ENCODING,
    ON_CYGWIN,
    ON_DARWIN,
    ON_LINUX,
    ON_MSYS,
    ON_POSIX,
    ON_WINDOWS,
    ON_WSL,
    ON_WSL1,
    PYTHON_VERSION_INFO,
    githash,
    is_readline_available,
    linux_distro,
    ptk_version,
    pygments_version,
)
from xonsh.prompt.base import is_template_string
from xonsh.tools import (
    color_style,
    color_style_names,
    is_string,
    is_superuser,
    print_color,
    print_exception,
    to_bool,
)
from xonsh.xontribs import Xontrib, find_xontrib, get_xontribs, xontribs_loaded

HR = "'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'"
WIZARD_HEAD = f"""
          {{BOLD_WHITE}}Welcome to the xonsh configuration wizard!{{RESET}}
          {{YELLOW}}------------------------------------------{{RESET}}
This will present a guided tour through setting up the xonsh static
config file. Xonsh will automatically ask you if you want to run this
wizard if the configuration file does not exist. However, you can
always rerun this wizard with the xonfig command:

    $ xonfig wizard

This wizard will load an existing configuration, if it is available.
Also never fear when this wizard saves its results! It will create
a backup of any existing configuration automatically.

This wizard has two main phases: foreign shell setup and environment
variable setup. Each phase may be skipped in its entirety.

For the configuration to take effect, you will need to restart xonsh.

{HR}
"""

WIZARD_FS = f"""
{HR}

                      {{BOLD_WHITE}}Foreign Shell Setup{{RESET}}
                      {{YELLOW}}-------------------{{RESET}}
The xonsh shell has the ability to interface with Bash or zsh
via the foreign shell interface.

For configuration, this means that xonsh can load the environment,
aliases, and functions specified in the config files of these shells.
Naturally, these shells must be available on the system to work.
Being able to share configuration (and source) from foreign shells
makes it easier to transition to and from xonsh.
"""

WIZARD_ENV = f"""
{HR}

                  {{BOLD_WHITE}}Environment Variable Setup{{RESET}}
                  {{YELLOW}}--------------------------{{RESET}}
The xonsh shell also allows you to setup environment variables from
the static configuration file. Any variables set in this way are
superseded by the definitions in the xonshrc or on the command line.
Still, setting environment variables in this way can help define
options that are global to the system or user.

The following lists the environment variable name, its documentation,
the default value, and the current value. The default and current
values are presented as pretty repr strings of their Python types.

{{BOLD_GREEN}}Note:{{RESET}} Simply hitting enter for any environment variable
will accept the default value for that entry.
"""

WIZARD_ENV_QUESTION = "Would you like to set env vars now, " + wiz.YN

WIZARD_XONTRIB = f"""
{HR}

                           {{BOLD_WHITE}}Xontribs{{RESET}}
                           {{YELLOW}}--------{{RESET}}
No shell is complete without extensions, and xonsh is no exception. Xonsh
extensions are called {{BOLD_GREEN}}xontribs{{RESET}}, or xonsh contributions.
Xontribs are dynamically loadable, either by importing them directly or by
using the 'xontrib' command. However, you can also configure xonsh to load
xontribs automatically on startup prior to loading the run control files.
This allows the xontrib to be used immediately in your xonshrc files.

The following describes all xontribs that have been registered with xonsh.
These come from users, 3rd party developers, or xonsh itself!
"""

WIZARD_XONTRIB_QUESTION = "Would you like to enable xontribs now, " + wiz.YN

WIZARD_TAIL = """
Thanks for using the xonsh configuration wizard!"""


_XONFIG_SOURCE_FOREIGN_SHELL_COMMAND: dict[str, str] = collections.defaultdict(
    lambda: "source-foreign", bash="source-bash", cmd="source-cmd", zsh="source-zsh"
)


events.doc(
    "on_xonfig_info_requested",
    """
on_xonfig_info_requested() -> list[tuple[str, str]]

Register a callable that will return extra info when ``xonfig info`` is called.
""",
)


def _dump_xonfig_foreign_shell(path, value):
    shell = value["shell"]
    shell = CANON_SHELL_NAMES.get(shell, shell)
    cmd = [_XONFIG_SOURCE_FOREIGN_SHELL_COMMAND[shell]]
    interactive = value.get("interactive", None)
    if interactive is not None:
        cmd.extend(["--interactive", str(interactive)])
    login = value.get("login", None)
    if login is not None:
        cmd.extend(["--login", str(login)])
    envcmd = value.get("envcmd", None)
    if envcmd is not None:
        cmd.extend(["--envcmd", envcmd])
    aliascmd = value.get("aliasmd", None)
    if aliascmd is not None:
        cmd.extend(["--aliascmd", aliascmd])
    extra_args = value.get("extra_args", None)
    if extra_args:
        cmd.extend(["--extra-args", repr(" ".join(extra_args))])
    safe = value.get("safe", None)
    if safe is not None:
        cmd.extend(["--safe", str(safe)])
    prevcmd = value.get("prevcmd", "")
    if prevcmd:
        cmd.extend(["--prevcmd", repr(prevcmd)])
    postcmd = value.get("postcmd", "")
    if postcmd:
        cmd.extend(["--postcmd", repr(postcmd)])
    funcscmd = value.get("funcscmd", None)
    if funcscmd:
        cmd.extend(["--funcscmd", repr(funcscmd)])
    sourcer = value.get("sourcer", None)
    if sourcer:
        cmd.extend(["--sourcer", sourcer])
    if cmd[0] == "source-foreign":
        cmd.append(shell)
    cmd.append('"echo loading xonsh foreign shell"')
    return " ".join(cmd)


def _dump_xonfig_env(path, value):
    name = os.path.basename(path.rstrip("/"))
    detyper = XSH.env.get_detyper(name)
    dval = str(value) if detyper is None else detyper(value)
    dval = str(value) if dval is None else dval
    return f"${name} = {dval!r}"


def _dump_xonfig_xontribs(path, value):
    return "xontrib load {}".format(" ".join(value))


@lazyobject
def XONFIG_DUMP_RULES():
    return {
        "/": None,
        "/env/": None,
        "/foreign_shells/*/": _dump_xonfig_foreign_shell,
        "/env/*": _dump_xonfig_env,
        "/env/*/[0-9]*": None,
        "/xontribs/": _dump_xonfig_xontribs,
    }


def make_fs_wiz():
    """Makes the foreign shell part of the wizard."""
    cond = wiz.create_truefalse_cond(prompt="Add a new foreign shell, " + wiz.YN)
    fs = wiz.While(
        cond=cond,
        body=[
            wiz.Input("shell name (e.g. bash): ", path="/foreign_shells/{idx}/shell"),
            wiz.StoreNonEmpty(
                "interactive shell [bool, default=True]: ",
                converter=to_bool,
                show_conversion=True,
                path="/foreign_shells/{idx}/interactive",
            ),
            wiz.StoreNonEmpty(
                "login shell [bool, default=False]: ",
                converter=to_bool,
                show_conversion=True,
                path="/foreign_shells/{idx}/login",
            ),
            wiz.StoreNonEmpty(
                "env command [str, default='env']: ",
                path="/foreign_shells/{idx}/envcmd",
            ),
            wiz.StoreNonEmpty(
                "alias command [str, default='alias']: ",
                path="/foreign_shells/{idx}/aliascmd",
            ),
            wiz.StoreNonEmpty(
                ("extra command line arguments [list of str, " "default=[]]: "),
                converter=ast.literal_eval,
                show_conversion=True,
                path="/foreign_shells/{idx}/extra_args",
            ),
            wiz.StoreNonEmpty(
                "safely handle exceptions [bool, default=True]: ",
                converter=to_bool,
                show_conversion=True,
                path="/foreign_shells/{idx}/safe",
            ),
            wiz.StoreNonEmpty(
                "pre-command [str, default='']: ", path="/foreign_shells/{idx}/prevcmd"
            ),
            wiz.StoreNonEmpty(
                "post-command [str, default='']: ", path="/foreign_shells/{idx}/postcmd"
            ),
            wiz.StoreNonEmpty(
                "foreign function command [str, default=None]: ",
                path="/foreign_shells/{idx}/funcscmd",
            ),
            wiz.StoreNonEmpty(
                "source command [str, default=None]: ",
                path="/foreign_shells/{idx}/sourcer",
            ),
            wiz.Message(message="Foreign shell added.\n"),
        ],
    )
    return fs


def _wrap_paragraphs(text, width=70, **kwargs):
    """Wraps paragraphs instead."""
    pars = text.split("\n")
    pars = ["\n".join(textwrap.wrap(p, width=width, **kwargs)) for p in pars]
    s = "\n".join(pars)
    return s


ENVVAR_MESSAGE = """
{{BOLD_CYAN}}${name}{{RESET}}
{docstr}
{{RED}}default value:{{RESET}} {default}
{{RED}}current value:{{RESET}} {current}"""

ENVVAR_PROMPT = "{BOLD_GREEN}>>>{RESET} "


def make_exit_message():
    """Creates a message for how to exit the wizard."""
    shell_type = XSH.shell.shell_type
    keyseq = "Ctrl-D" if shell_type == "readline" else "Ctrl-C"
    msg = "To exit the wizard at any time, press {BOLD_UNDERLINE_CYAN}"
    msg += keyseq + "{RESET}.\n"
    m = wiz.Message(message=msg)
    return m


def make_envvar(name):
    """Makes a StoreNonEmpty node for an environment variable."""
    env = XSH.env
    vd = env.get_docs(name)
    if not vd.is_configurable:
        return
    default = vd.doc_default
    if "\n" in default:
        default = "\n" + _wrap_paragraphs(default, width=69)
    curr = env.get(name)
    if is_string(curr) and is_template_string(curr):
        curr = curr.replace("{", "{{").replace("}", "}}")
    curr = pprint.pformat(curr, width=69)
    if "\n" in curr:
        curr = "\n" + curr
    msg = ENVVAR_MESSAGE.format(
        name=name,
        default=default,
        current=curr,
        docstr=_wrap_paragraphs(vd.doc, width=69),
    )
    mnode = wiz.Message(message=msg)
    converter = env.get_converter(name)
    path = "/env/" + name
    pnode = wiz.StoreNonEmpty(
        ENVVAR_PROMPT,
        converter=converter,
        show_conversion=True,
        path=path,
        retry=True,
        store_raw=vd.can_store_as_str,
    )
    return mnode, pnode


def _make_flat_wiz(kidfunc, *args):
    kids = map(kidfunc, *args)
    flatkids = []
    for k in kids:
        if k is None:
            continue
        flatkids.extend(k)
    wizard = wiz.Wizard(children=flatkids)
    return wizard


def make_env_wiz():
    """Makes an environment variable wizard."""
    w = _make_flat_wiz(make_envvar, sorted(XSH.env.keys()))
    return w


XONTRIB_PROMPT = "{BOLD_GREEN}Add this xontrib{RESET}, " + wiz.YN


def _xontrib_path(visitor=None, node=None, val=None):
    # need this to append only based on user-selected size
    return ("xontribs", len(visitor.state.get("xontribs", ())))


def make_xontrib(xon_item: tuple[str, Xontrib]):
    """Makes a message and StoreNonEmpty node for a xontrib."""
    name, xontrib = xon_item
    name = name or "<unknown-xontrib-name>"
    msg = "\n{BOLD_CYAN}" + name + "{RESET}\n"

    if xontrib.url:
        msg += "{RED}url:{RESET} " + xontrib.url + "\n"
    if xontrib.distribution:
        msg += "{RED}package:{RESET} " + xontrib.distribution.name + "\n"
        if xontrib.license:
            msg += "{RED}license:{RESET} " + xontrib.license + "\n"
    msg += "{PURPLE}installed?{RESET} "
    msg += ("no" if find_xontrib(name) is None else "yes") + "\n"
    msg += _wrap_paragraphs(xontrib.get_description(), width=69)
    if msg.endswith("\n"):
        msg = msg[:-1]
    mnode = wiz.Message(message=msg)
    convert = lambda x: name if to_bool(x) else wiz.Unstorable
    pnode = wiz.StoreNonEmpty(XONTRIB_PROMPT, converter=convert, path=_xontrib_path)
    return mnode, pnode


def make_xontribs_wiz():
    """Makes a xontrib wizard."""
    return _make_flat_wiz(make_xontrib, get_xontribs().items())


def make_xonfig_wizard(default_file=None, confirm=False, no_wizard_file=None):
    """Makes a configuration wizard for xonsh config file.

    Parameters
    ----------
    default_file : str, optional
        Default filename to save and load to. User will still be prompted.
    confirm : bool, optional
        Confirm that the main part of the wizard should be run.
    no_wizard_file : str, optional
        Filename for that will flag to future runs that the wizard should not be
        run again. If None (default), this defaults to default_file.
    """
    w = wiz.Wizard(
        children=[
            wiz.Message(message=WIZARD_HEAD),
            make_exit_message(),
            wiz.Message(message=WIZARD_FS),
            make_fs_wiz(),
            wiz.Message(message=WIZARD_ENV),
            wiz.YesNo(question=WIZARD_ENV_QUESTION, yes=make_env_wiz(), no=wiz.Pass()),
            wiz.Message(message=WIZARD_XONTRIB),
            wiz.YesNo(
                question=WIZARD_XONTRIB_QUESTION, yes=make_xontribs_wiz(), no=wiz.Pass()
            ),
            wiz.Message(message="\n" + HR + "\n"),
            wiz.FileInserter(
                prefix="# XONSH WIZARD START",
                suffix="# XONSH WIZARD END",
                dump_rules=XONFIG_DUMP_RULES,
                default_file=default_file,
                check=True,
            ),
            wiz.Message(message=WIZARD_TAIL),
        ]
    )
    if confirm:
        q = (
            "Would you like to run the xonsh configuration wizard now?\n\n"
            "1. Yes (You can abort at any time)\n"
            "2. No, but ask me next time.\n"
            "3. No, and don't ask me again.\n\n"
            "1, 2, or 3 [default: 2]? "
        )
        no_wizard_file = default_file if no_wizard_file is None else no_wizard_file
        passer = wiz.Pass()
        saver = wiz.SaveJSON(
            check=False, ask_filename=False, default_file=no_wizard_file
        )
        w = wiz.Question(
            q, {1: w, 2: passer, 3: saver}, converter=lambda x: int(x) if x != "" else 2
        )
    return w


def _wizard(
    rcfile=None,
    confirm=False,
):
    """Launch configurator in terminal

    Parameters
    -------
    rcfile : -f, --file
        config file location, default=$XONSHRC
    confirm : -c, --confirm
        confirm that the wizard should be run.
    """
    env = XSH.env
    shell = XSH.shell.shell
    xonshrcs = env.get("XONSHRC", [])
    fname = xonshrcs[-1] if xonshrcs and rcfile is None else rcfile
    no_wiz = os.path.join(env.get("XONSH_CONFIG_DIR"), "no-wizard")
    w = make_xonfig_wizard(default_file=fname, confirm=confirm, no_wizard_file=no_wiz)
    tempenv = {"PROMPT": "", "XONSH_STORE_STDOUT": False}
    pv = wiz.PromptVisitor(w, store_in_history=False, multiline=False)

    @contextlib.contextmanager
    def force_hide():
        if env.get("XONSH_STORE_STDOUT") and hasattr(shell, "_force_hide"):
            orig, shell._force_hide = shell._force_hide, False
            yield
            shell._force_hide = orig
        else:
            yield

    with force_hide(), env.swap(tempenv):
        try:
            pv.visit()
        except (KeyboardInterrupt, Exception):
            print()
            print_exception()


def _xonfig_format_human(data):
    wcol1 = wcol2 = 0
    for key, val in data:
        wcol1 = max(wcol1, len(key))
        if isinstance(val, list):
            for subval in val:
                wcol2 = max(wcol2, len(str(subval)))
        else:
            wcol2 = max(wcol2, len(str(val)))
    hr = "+" + ("-" * (wcol1 + 2)) + "+" + ("-" * (wcol2 + 2)) + "+\n"
    row = "| {key!s:<{wcol1}} | {val!s:<{wcol2}} |\n"
    s = hr
    for key, val in data:
        if isinstance(val, list) and val:
            for i, subval in enumerate(val):
                s += row.format(
                    key=f"{key} {i+1}", wcol1=wcol1, val=subval, wcol2=wcol2
                )
        else:
            s += row.format(key=key, wcol1=wcol1, val=val, wcol2=wcol2)
    s += hr
    return s


def _xonfig_format_json(data):
    data = {k.replace(" ", "_"): v for k, v in data}
    s = json.dumps(data, sort_keys=True, indent=1) + "\n"
    return s


def _info(
    to_json=False,
) -> str:
    """Displays configuration information

    Parameters
    ----------
    to_json : -j, --json
        reports results as json
    """
    env = XSH.env
    data: list[tp.Any] = [("xonsh", XONSH_VERSION)]
    hash_, date_ = githash()
    if hash_:
        data.append(("Git SHA", hash_))
        data.append(("Commit Date", date_))
    data.extend(
        [
            ("Python", "{}.{}.{}".format(*PYTHON_VERSION_INFO)),
            ("PLY", ply.__version__),
            ("have readline", is_readline_available()),
            ("prompt toolkit", ptk_version() or None),
            ("shell type", env.get("SHELL_TYPE")),
            ("history backend", env.get("XONSH_HISTORY_BACKEND")),
            ("pygments", pygments_version()),
            ("on posix", bool(ON_POSIX)),
            ("on linux", bool(ON_LINUX)),
        ]
    )
    if ON_LINUX:
        data.append(("distro", linux_distro()))
        data.append(("on wsl", bool(ON_WSL)))
        if ON_WSL:
            data.append(("wsl version", 1 if ON_WSL1 else 2))
    data.extend(
        [
            ("on darwin", bool(ON_DARWIN)),
            ("on windows", bool(ON_WINDOWS)),
            ("on cygwin", bool(ON_CYGWIN)),
            ("on msys2", bool(ON_MSYS)),
            ("is superuser", is_superuser()),
            ("default encoding", DEFAULT_ENCODING),
            ("xonsh encoding", env.get("XONSH_ENCODING")),
            ("encoding errors", env.get("XONSH_ENCODING_ERRORS")),
        ]
    )
    for p in XSH.builtins.events.on_xonfig_info_requested.fire():
        if p is not None:
            data.extend(p)

    data.extend([("xontrib", xontribs_loaded())])
    data.extend([("RC file", XSH.rc_files)])

    # Show sensitive env variables that could affect the shell behavior.
    envs = {
        "UPDATE_OS_ENVIRON": None,
        "XONSH_CAPTURE_ALWAYS": None,
        "XONSH_SUBPROC_OUTPUT_FORMAT": None,
        "THREAD_SUBPROCS": None,
        "ENABLE_ASYNC_PROMPT": True,
        "ENABLE_COMMANDS_CACHE": False,
        "XONSH_CACHE_EVERYTHING": True,
        "XONSH_CACHE_SCRIPTS": None,
    }
    for e, show_if in envs.items():
        if (val := XSH.env.get(e)) is not None and (show_if is None or val == show_if):
            data.extend([(e, val)])

    formatter = _xonfig_format_json if to_json else _xonfig_format_human
    s = formatter(data)
    return s


def _styles(to_json=False, _stdout=None):
    """Prints available xonsh color styles

    Parameters
    ----------
    to_json: -j, --json
        reports results as json
    """
    env = XSH.env
    curr = env.get("XONSH_COLOR_STYLE")
    styles = sorted(color_style_names())
    if to_json:
        s = json.dumps(styles, sort_keys=True, indent=1)
        print(s)
        return
    lines = []
    for style in styles:
        if style == curr:
            lines.append("* {GREEN}" + style + "{RESET}")
        else:
            lines.append("  " + style)
    s = "\n".join(lines)
    print_color(s, file=_stdout)


def _str_colors(cmap, cols):
    color_names = sorted(cmap.keys(), key=(lambda s: (len(s), s)))
    grper = lambda s: min(cols // (len(s) + 1), 8)
    lines = []
    for n, group in itertools.groupby(color_names, key=grper):
        width = cols // n
        line = ""
        for i, name in enumerate(group):
            buf = " " * (width - len(name))
            line += "{" + name + "}" + name + "{RESET}" + buf
            if (i + 1) % n == 0:
                lines.append(line)
                line = ""
        if len(line) != 0:
            lines.append(line)
    return "\n".join(lines)


def _tok_colors(cmap, cols):
    from xonsh.style_tools import Color

    nc = Color.RESET
    names_toks = {}
    for t in cmap.keys():
        name = str(t)
        if name.startswith("Token.Color."):
            _, _, name = name.rpartition(".")
        names_toks[name] = t
    color_names = sorted(names_toks.keys(), key=(lambda s: (len(s), s)))
    grper = lambda s: min(cols // (len(s) + 1), 8)
    toks = []
    for n, group in itertools.groupby(color_names, key=grper):
        width = cols // n
        for i, name in enumerate(group):
            toks.append((names_toks[name], name))
            buf = " " * (width - len(name))
            if (i + 1) % n == 0:
                buf += "\n"
            toks.append((nc, buf))
        if not toks[-1][1].endswith("\n"):
            toks[-1] = (nc, toks[-1][1] + "\n")
    return toks


def xonfig_color_completer(*_, **__):
    yield from color_style_names()


def _colors(
    style: tp.Annotated[str, Arg(nargs="?", completer=xonfig_color_completer)] = None,
):
    """Preview color style

    Parameters
    ----------
    style
        name of the style to preview. If not given, current style name is used.
    """
    columns, _ = shutil.get_terminal_size()
    columns -= int(bool(ON_WINDOWS))
    style_stash = XSH.env["XONSH_COLOR_STYLE"]

    if style is not None:
        if style not in color_style_names():
            print(f"Invalid style: {style}")
            return
        XSH.env["XONSH_COLOR_STYLE"] = style

    color_map = color_style()
    if not color_map:
        print("Empty color map - using non-interactive shell?")
        return
    akey = next(iter(color_map))
    if isinstance(akey, str):
        s = _str_colors(color_map, columns)
    else:
        s = _tok_colors(color_map, columns)
    print_color(s)
    XSH.env["XONSH_COLOR_STYLE"] = style_stash


def _tutorial():
    """Launch tutorial in browser."""
    import webbrowser

    webbrowser.open("http://xon.sh/tutorial.html")


def _web(
    _args,
    browser=True,
):
    """Launch configurator in browser.

    Parameters
    ----------
    browser : --nb, --no-browser, -n
        don't open browser
    """

    from xonsh.webconfig import main

    main.serve(browser)


class XonfigAlias(ArgParserAlias):
    """Manage xonsh configuration."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.extra_commands = []

    def add_command(self, fn):
        self.extra_commands.append(fn)

    def build(self):
        parser = self.create_parser(prog="xonfig")
        # register as default action
        parser.add_command(_info, default=True)
        parser.add_command(_web)
        parser.add_command(_wizard)
        parser.add_command(_styles)
        parser.add_command(_colors)
        parser.add_command(_tutorial)
        for fn in self.extra_commands:
            parser.add_command(fn)

        return parser


xonfig_main = XonfigAlias(threadable=False)


@lazyobject
def STRIP_COLOR_RE():
    return re.compile("{.*?}")


def _align_string(string, align="<", fill=" ", width=80):
    """Align and pad a color formatted string"""
    linelen = len(STRIP_COLOR_RE.sub("", string))
    padlen = max(width - linelen, 0)
    if align == "^":
        return fill * (padlen // 2) + string + fill * (padlen // 2 + padlen % 2)
    elif align == ">":
        return fill * padlen + string
    elif align == "<":
        return string + fill * padlen
    else:
        return string


@lazyobject
def TAGLINES():
    return [
        "Exofrills in the shell",
        "No frills in the shell",
        "Become the Lord of the Files",
        "Break out of your shell",
        "The only shell that is also a shell",
        "All that is and all that shell be",
        "It cannot be that hard",
        "Pass the xonsh, Piggy",
        "Piggy glanced nervously into hell and cradled the xonsh",
        "The xonsh is a symbol",
        "It is pronounced conch",
        "Snailed it",
        "Starfish loves you",
        "Come snail away",
        "This is Major Tom to Ground Xonshtrol",
        "Sally sells csh and keeps xonsh to herself",
        "Nice indeed. Everything's accounted for, except your old shell.",
        "I wanna thank you for putting me back in my snail shell",
        "Crustaceanly Yours",
        "With great shell comes great reproducibility",
        "None shell pass",
        "You shell not pass!",
        "The x-on shell",
        "Ever wonder why there isn't a Taco Shell? Because it is a corny idea.",
        "The carcolh will catch you!",
        "People xonshtantly mispronounce these things",
        "WHAT...is your favorite shell?",
        "Conches for the xonsh god!",
        "Python-powered, cross-platform, Unix-gazing shell",
        "Tab completion in Alderaan places",
        "This fix was trickier than expected",
    ]


# list of strings or tuples (string, align, fill)
WELCOME_MSG = [
    "",
    ("Welcome to the xonsh shell {version}", "^", " "),
    "",
    ("{{INTENSE_RED}}~{{RESET}} {tagline} {{INTENSE_RED}}~{{RESET}}", "^", " "),
    "",
    ("{{INTENSE_BLACK}}", "<", "-"),
    "",
    (
        "{{INTENSE_BLACK}}Create ~/.xonshrc file manually or use xonfig to suppress the welcome message",
        "^",
        " ",
    ),
    "",
    "{{INTENSE_BLACK}}Start from commands:",
    "  {{GREEN}}xonfig{{RESET}} web         {{INTENSE_BLACK}}# Run the configuration tool in the browser to create ~/.xonshrc {{RESET}}",
    "  {{GREEN}}xonfig{{RESET}} tutorial    {{INTENSE_BLACK}}# Open the xonsh tutorial in the browser{{RESET}}",
    "[SHELL_TYPE_WARNING]",
    "",
    ("{{INTENSE_BLACK}}", "<", "-"),
    "",
]


def print_welcome_screen():
    shell_type = XSH.env.get("SHELL_TYPE")
    subst = dict(tagline=random.choice(list(TAGLINES)), version=XONSH_VERSION)
    for elem in WELCOME_MSG:
        if elem == "[SHELL_TYPE_WARNING]":
            if shell_type != "prompt_toolkit":
                print_color(
                    f"\n{{INTENSE_BLACK}}You are currently using the {shell_type} backend. "
                    f"For interactive tab-completion, on-the-fly syntax highlighting, and more, install prompt_toolkit by running:\n\n"
                    f"  {{GREEN}}xpip{{RESET}} install -U 'xonsh[full]'"
                )
            continue
        if isinstance(elem, str):
            elem = (elem, "", "")
        line = elem[0].format(**subst)
        termwidth = os.get_terminal_size().columns
        line = _align_string(line, elem[1], elem[2], width=termwidth)
        print_color(line)
    print_color("{RESET}", end="")
