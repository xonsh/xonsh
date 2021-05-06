"""The xonsh configuration (xonfig) utility."""
import os
import re
import ast
import sys
import json
import shutil
import random
import pprint
import tempfile
import textwrap
import builtins
import argparse
import functools
import itertools
import contextlib
import collections
import typing as tp

from xonsh.ply import ply

import xonsh.wizard as wiz
from xonsh import __version__ as XONSH_VERSION
from xonsh.prompt.base import is_template_string
from xonsh.platform import (
    is_readline_available,
    ptk_version,
    PYTHON_VERSION_INFO,
    pygments_version,
    ON_POSIX,
    ON_LINUX,
    linux_distro,
    ON_DARWIN,
    ON_WINDOWS,
    ON_CYGWIN,
    DEFAULT_ENCODING,
    ON_MSYS,
    githash,
)
from xonsh.tools import (
    to_bool,
    is_string,
    print_exception,
    is_superuser,
    color_style_names,
    print_color,
    color_style,
)
from xonsh.foreign_shells import CANON_SHELL_NAMES
from xonsh.xontribs import find_xontrib, xontribs_loaded
from xonsh.xontribs_meta import get_xontribs, Xontrib
from xonsh.lazyasd import lazyobject

HR = "'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'"
WIZARD_HEAD = """
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

{hr}
""".format(
    hr=HR
)

WIZARD_FS = """
{hr}

                      {{BOLD_WHITE}}Foreign Shell Setup{{RESET}}
                      {{YELLOW}}-------------------{{RESET}}
The xonsh shell has the ability to interface with Bash or zsh
via the foreign shell interface.

For configuration, this means that xonsh can load the environment,
aliases, and functions specified in the config files of these shells.
Naturally, these shells must be available on the system to work.
Being able to share configuration (and source) from foreign shells
makes it easier to transition to and from xonsh.
""".format(
    hr=HR
)

WIZARD_ENV = """
{hr}

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
""".format(
    hr=HR
)

WIZARD_ENV_QUESTION = "Would you like to set env vars now, " + wiz.YN

WIZARD_XONTRIB = """
{hr}

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
""".format(
    hr=HR
)

WIZARD_XONTRIB_QUESTION = "Would you like to enable xontribs now, " + wiz.YN

WIZARD_TAIL = """
Thanks for using the xonsh configuration wizard!"""


_XONFIG_SOURCE_FOREIGN_SHELL_COMMAND: tp.Dict[str, str] = collections.defaultdict(
    lambda: "source-foreign", bash="source-bash", cmd="source-cmd", zsh="source-zsh"
)

XONSH_JUPYTER_KERNEL = "xonsh"


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
    detyper = builtins.__xonsh__.env.get_detyper(name)
    dval = str(value) if detyper is None else detyper(value)
    dval = str(value) if dval is None else dval
    return "${name} = {val!r}".format(name=name, val=dval)


def _dump_xonfig_xontribs(path, value):
    return "xontrib load {0}".format(" ".join(value))


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
    shell_type = builtins.__xonsh__.shell.shell_type
    keyseq = "Ctrl-D" if shell_type == "readline" else "Ctrl-C"
    msg = "To exit the wizard at any time, press {BOLD_UNDERLINE_CYAN}"
    msg += keyseq + "{RESET}.\n"
    m = wiz.Message(message=msg)
    return m


def make_envvar(name):
    """Makes a StoreNonEmpty node for an environment variable."""
    env = builtins.__xonsh__.env
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
    w = _make_flat_wiz(make_envvar, sorted(builtins.__xonsh__.env.keys()))
    return w


XONTRIB_PROMPT = "{BOLD_GREEN}Add this xontrib{RESET}, " + wiz.YN


def _xontrib_path(visitor=None, node=None, val=None):
    # need this to append only based on user-selected size
    return ("xontribs", len(visitor.state.get("xontribs", ())))


def make_xontrib(xon_item: tp.Tuple[str, Xontrib]):
    """Makes a message and StoreNonEmpty node for a xontrib."""
    name, xontrib = xon_item
    name = name or "<unknown-xontrib-name>"
    msg = "\n{BOLD_CYAN}" + name + "{RESET}\n"
    if xontrib.url:
        msg += "{RED}url:{RESET} " + xontrib.url + "\n"
    if xontrib.package:
        pkg = xontrib.package
        msg += "{RED}package:{RESET} " + pkg.name + "\n"
        if pkg.url:
            if xontrib.url and pkg.url != xontrib.url:
                msg += "{RED}package-url:{RESET} " + pkg.url + "\n"
        if pkg.license:
            msg += "{RED}license:{RESET} " + pkg.license + "\n"
    msg += "{PURPLE}installed?{RESET} "
    msg += ("no" if find_xontrib(name) is None else "yes") + "\n"
    msg += _wrap_paragraphs(xontrib.description, width=69)
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


def _wizard(ns):
    env = builtins.__xonsh__.env
    shell = builtins.__xonsh__.shell.shell
    xonshrcs = env.get("XONSHRC", [])
    fname = xonshrcs[-1] if xonshrcs and ns.file is None else ns.file
    no_wiz = os.path.join(env.get("XONSH_CONFIG_DIR"), "no-wizard")
    w = make_xonfig_wizard(
        default_file=fname, confirm=ns.confirm, no_wizard_file=no_wiz
    )
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


def _info(ns):
    env = builtins.__xonsh__.env
    data = [("xonsh", XONSH_VERSION)]
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
            ("pygments", pygments_version()),
            ("on posix", bool(ON_POSIX)),
            ("on linux", bool(ON_LINUX)),
        ]
    )
    if ON_LINUX:
        data.append(("distro", linux_distro()))
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
    jup_ksm = jup_kernel = None
    try:
        from jupyter_client.kernelspec import KernelSpecManager

        jup_ksm = KernelSpecManager()
        jup_kernel = jup_ksm.find_kernel_specs().get(XONSH_JUPYTER_KERNEL)
    except Exception:
        pass
    data.extend([("on jupyter", jup_ksm is not None), ("jupyter kernel", jup_kernel)])

    data.extend([("xontrib", xontribs_loaded())])

    formatter = _xonfig_format_json if ns.json else _xonfig_format_human
    s = formatter(data)
    return s


def _styles(ns):
    env = builtins.__xonsh__.env
    curr = env.get("XONSH_COLOR_STYLE")
    styles = sorted(color_style_names())
    if ns.json:
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
    print_color(s)


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


def _colors(args):
    columns, _ = shutil.get_terminal_size()
    columns -= int(ON_WINDOWS)
    style_stash = builtins.__xonsh__.env["XONSH_COLOR_STYLE"]

    if args.style is not None:
        if args.style not in color_style_names():
            print("Invalid style: {}".format(args.style))
            return
        builtins.__xonsh__.env["XONSH_COLOR_STYLE"] = args.style

    color_map = color_style()
    akey = next(iter(color_map))
    if isinstance(akey, str):
        s = _str_colors(color_map, columns)
    else:
        s = _tok_colors(color_map, columns)
    print_color(s)
    builtins.__xonsh__.env["XONSH_COLOR_STYLE"] = style_stash


def _tutorial(args):
    import webbrowser

    webbrowser.open("http://xon.sh/tutorial.html")


def _web(args):
    import subprocess

    subprocess.run([sys.executable, "-m", "xonsh.webconfig"] + args.orig_args[1:])


def _jupyter_kernel(args):
    """Make xonsh available as a Jupyter kernel."""
    try:
        from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel
    except ImportError as e:
        raise ImportError("Jupyter not found in current Python environment") from e

    ksm = KernelSpecManager()

    root = args.root
    prefix = args.prefix if args.prefix else sys.prefix
    user = args.user
    spec = {
        "argv": [
            sys.executable,
            "-m",
            "xonsh.jupyter_kernel",
            "-f",
            "{connection_file}",
        ],
        "display_name": "Xonsh",
        "language": "xonsh",
        "codemirror_mode": "shell",
    }

    if root and prefix:
        # os.path.join isn't used since prefix is probably absolute
        prefix = root + prefix

    try:
        old_jup_kernel = ksm.get_kernel_spec(XONSH_JUPYTER_KERNEL)
        if not old_jup_kernel.resource_dir.startswith(prefix):
            print(
                "Removing existing Jupyter kernel found at {0}".format(
                    old_jup_kernel.resource_dir
                )
            )
        ksm.remove_kernel_spec(XONSH_JUPYTER_KERNEL)
    except NoSuchKernel:
        pass

    if sys.platform == "win32":
        # Ensure that conda-build detects the hard coded prefix
        spec["argv"][0] = spec["argv"][0].replace(os.sep, os.altsep)
        prefix = prefix.replace(os.sep, os.altsep)

    with tempfile.TemporaryDirectory() as d:
        os.chmod(d, 0o755)  # Starts off as 700, not user readable
        with open(os.path.join(d, "kernel.json"), "w") as f:
            json.dump(spec, f, sort_keys=True)

        print("Installing Jupyter kernel spec:")
        print("  root: {0!r}".format(root))
        if user:
            print("  as user: {0}".format(user))
        elif root and prefix:
            print("  combined prefix {0!r}".format(prefix))
        else:
            print("  prefix: {0!r}".format(prefix))
        ksm.install_kernel_spec(
            d, XONSH_JUPYTER_KERNEL, user=user, prefix=(None if user else prefix)
        )
        return 0


@functools.lru_cache(1)
def _xonfig_create_parser():
    p = argparse.ArgumentParser(
        prog="xonfig", description="Manages xonsh configuration."
    )
    subp = p.add_subparsers(title="action", dest="action")
    info = subp.add_parser(
        "info", help=("displays configuration information, " "default action")
    )
    info.add_argument(
        "--json", action="store_true", default=False, help="reports results as json"
    )
    web = subp.add_parser("web", help="Launch configurator in browser.")
    web.add_argument(
        "--no-browser",
        action="store_false",
        dest="browser",
        default=True,
        help="don't open browser",
    )
    wiz = subp.add_parser("wizard", help="Launch configurator in terminal")
    wiz.add_argument(
        "--file", default=None, help="config file location, default=$XONSHRC"
    )
    wiz.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="confirm that the wizard should be run.",
    )
    sty = subp.add_parser("styles", help="prints available xonsh color styles")
    sty.add_argument(
        "--json", action="store_true", default=False, help="reports results as json"
    )
    colors = subp.add_parser("colors", help="preview color style")
    colors.add_argument(
        "style", nargs="?", default=None, help="style to preview, default: <current>"
    )
    subp.add_parser("tutorial", help="Launch tutorial in browser.")
    kern = subp.add_parser("jupyter-kernel", help="Generate xonsh kernel for jupyter.")
    kern.add_argument(
        "--user",
        action="store_true",
        default=False,
        help="Install kernel spec in user config directory.",
    )
    kern.add_argument(
        "--root",
        default=None,
        help="Install relative to this alternate root directory.",
    )
    kern.add_argument(
        "--prefix", default=None, help="Installation prefix for bin, lib, etc."
    )

    return p


XONFIG_MAIN_ACTIONS = {
    "info": _info,
    "web": _web,
    "wizard": _wizard,
    "styles": _styles,
    "colors": _colors,
    "tutorial": _tutorial,
    "jupyter-kernel": _jupyter_kernel,
}


def xonfig_main(args=None):
    """Main xonfig entry point."""
    if not args or (
        args[0] not in XONFIG_MAIN_ACTIONS and args[0] not in {"-h", "--help"}
    ):
        args.insert(0, "info")
    parser = _xonfig_create_parser()
    ns = parser.parse_args(args)
    ns.orig_args = args
    if ns.action is None:  # apply default action
        ns = parser.parse_args(["info"] + args)
    return XONFIG_MAIN_ACTIONS[ns.action](ns)


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
    shell_type = builtins.__xonsh__.env.get("SHELL_TYPE")
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
