"""Tools for helping manage xontributions."""
import contextlib
import importlib
import importlib.util
import json
import sys
import typing as tp
from enum import IntEnum

from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.completers.tools import RichCompletion
from xonsh.tools import print_color, print_exception
from xonsh.xontribs_meta import get_xontribs


class ExitCode(IntEnum):
    OK = 0
    NOT_FOUND = 1
    INIT_FAILED = 2


def find_xontrib(name):
    """Finds a xontribution from its name."""
    spec = None
    if name.startswith("."):
        spec = importlib.util.find_spec(name, package="xontrib")
    else:
        with contextlib.suppress(ValueError):
            spec = importlib.util.find_spec("." + name, package="xontrib")
    return spec or importlib.util.find_spec(name)


def xontrib_context(name):
    """Return a context dictionary for a xontrib of a given name."""
    spec = find_xontrib(name)
    if spec is None:
        return None
    m = importlib.import_module(spec.name)
    pubnames = getattr(m, "__all__", None)
    if pubnames is not None:
        ctx = {k: getattr(m, k) for k in pubnames}
    else:
        ctx = {k: getattr(m, k) for k in dir(m) if not k.startswith("_")}
    return ctx


def prompt_xontrib_install(names: tp.List[str]):
    """Returns a formatted string with name of xontrib package to prompt user"""
    xontribs = get_xontribs()
    packages = []
    for name in names:
        if name in xontribs:
            xontrib = xontribs[name]
            if xontrib.package:
                packages.append(xontrib.package.name)

    return (
        "The following xontribs are enabled but not installed: \n"
        "   {xontribs}\n"
        "To install them run \n"
        "    xpip install {packages}".format(
            xontribs=" ".join(names), packages=" ".join(packages)
        )
    )


def update_context(name, ctx=None):
    """Updates a context in place from a xontrib. If ctx is not provided,
    then __xonsh__.ctx is updated.
    """
    if ctx is None:
        ctx = XSH.ctx
    modctx = xontrib_context(name)
    if modctx is None:
        if not hasattr(update_context, "bad_imports"):
            update_context.bad_imports = []
        update_context.bad_imports.append(name)
        return ctx
    return ctx.update(modctx)


def xontrib_names_completer(**_):
    for name, meta in get_xontribs().items():
        full_name = f"xontrib.{name}"
        if full_name not in sys.modules:
            yield RichCompletion(name, append_space=True, description=meta.description)


def xontribs_load(
    names: Annotated[
        tp.Sequence[str],
        Arg(nargs="+", completer=xontrib_names_completer),
    ] = (),
    verbose=False,
):
    """Load xontribs from a list of names

    Parameters
    ----------
    names
        names of xontribs
    verbose : -v, --verbose
        verbose output
    """
    ctx = XSH.ctx
    res = ExitCode.OK
    stdout = None
    stderr = None
    for name in names:
        if verbose:
            print(f"loading xontrib {name!r}")
        try:
            update_context(name, ctx=ctx)
        except Exception:
            res = ExitCode.INIT_FAILED
            print_exception(f"Failed to load xontrib {name}.")
    if hasattr(update_context, "bad_imports"):
        res = ExitCode.NOT_FOUND
        stderr = prompt_xontrib_install(update_context.bad_imports)  # type: ignore
        del update_context.bad_imports  # type: ignore
    return stdout, stderr, res


def xontrib_data():
    """Collects and returns the data about installed xontribs."""
    meta = get_xontribs()
    data = {}
    for xo_name in meta:
        spec = find_xontrib(xo_name)
        loaded = spec.name in sys.modules
        data[xo_name] = {"name": xo_name, "loaded": loaded}

    return dict(sorted(data.items()))


def xontribs_loaded():
    """Returns list of loaded xontribs."""
    return [k for k, v in xontrib_data().items() if v["loaded"]]


def _list(
    to_json=False,
):
    """List installed xontribs and show whether they are loaded or not

    Parameters
    ----------
    to_json : -j, --json
        reports results as json
    """
    data = xontrib_data()
    if to_json:
        s = json.dumps(data)
        print(s)
    else:
        nname = max([6] + [len(x) for x in data])
        s = ""
        for name, d in data.items():
            lname = len(name)
            s += "{PURPLE}" + name + "{RESET}  " + " " * (nname - lname)
            if d["loaded"]:
                s += "{GREEN}loaded{RESET}"
            else:
                s += "{RED}not-loaded{RESET}"
            s += "\n"
        print_color(s[:-1])


class XontribAlias(ArgParserAlias):
    """Manage xonsh extensions"""

    def build(self):
        parser = self.create_parser(prog="xontrib")
        parser.add_command(xontribs_load, prog="load")
        parser.add_command(_list)
        return parser


xontribs_main = XontribAlias(threadable=False)
