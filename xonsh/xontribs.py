"""Tools for helping manage xontributions."""
import importlib
import importlib.util
import json
import pkgutil
import sys
import typing as tp
from enum import IntEnum
from pathlib import Path

from xonsh.built_ins import XSH
from xonsh.cli_utils import ArgParserAlias, Arg, Annotated
from xonsh.completers.tools import RichCompletion
from xonsh.xontribs_meta import get_xontribs
from xonsh.tools import print_color, print_exception


class ExitCode(IntEnum):
    OK = 0
    NOT_FOUND = 1
    INIT_FAILED = 2


def find_xontrib(name):
    """Finds a xontribution from its name."""
    if name.startswith("."):
        spec = importlib.util.find_spec(name, package="xontrib")
    else:
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

    print(
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
    meta = get_xontribs()
    spec = importlib.util.find_spec("xontrib")
    for module in pkgutil.walk_packages(spec.submodule_search_locations):
        xont = meta.get(module.name)
        full_name = f"xontrib.{module.name}"

        if xont and full_name not in sys.modules:
            yield RichCompletion(
                module.name, append_space=True, description=xont.description
            )


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
    for name in names:
        if verbose:
            print("loading xontrib {0!r}".format(name))
        try:
            update_context(name, ctx=ctx)
        except Exception:
            res = ExitCode.INIT_FAILED
            print_exception("Failed to load xontrib {}.".format(name))
    if hasattr(update_context, "bad_imports"):
        res = ExitCode.NOT_FOUND
        prompt_xontrib_install(update_context.bad_imports)  # type: ignore
        del update_context.bad_imports  # type: ignore
    return res


def xontrib_installed(names: tp.Set[str]):
    """Returns list of installed xontribs."""
    installed_xontribs = set()
    spec = importlib.util.find_spec("xontrib")
    if spec:
        xontrib_locations = spec.submodule_search_locations
        if xontrib_locations:
            for xl in xontrib_locations:
                for x in Path(xl).glob("*"):
                    name = x.name.split(".")[0]
                    if name[0] == "_" or (names and name not in names):
                        continue
                    installed_xontribs.add(name)
    return installed_xontribs


def xontrib_data(names=()):
    """Collects and returns the data about xontribs."""
    meta = get_xontribs()
    data = {}
    names: tp.Set[str] = set(names or ())
    for xo_name in meta:
        if xo_name not in names:
            continue
        spec = find_xontrib(xo_name)
        if spec is None:
            installed = loaded = False
        else:
            installed = True
            loaded = spec.name in sys.modules
        data[xo_name] = {"name": xo_name, "installed": installed, "loaded": loaded}

    installed_xontribs = xontrib_installed(names)
    for name in installed_xontribs:
        if name not in data:
            loaded = f"xontrib.{name}" in sys.modules
            data[name] = {"name": name, "installed": True, "loaded": loaded}

    return dict(sorted(data.items()))


def xontribs_loaded(ns=None):
    """Returns list of loaded xontribs."""
    return [k for k, v in xontrib_data(ns).items() if v["loaded"]]


def _list(
    names: Annotated[tuple, Arg(nargs="*")] = (),
    to_json=False,
):
    """List xontribs, whether they are installed, and loaded.

    Parameters
    ----------
    to_json : -j, --json
        reports results as json
    names
        names of xontribs
    """
    data = xontrib_data(names)
    if to_json:
        s = json.dumps(data)
        print(s)
    else:
        nname = max([6] + [len(x) for x in data])
        s = ""
        for name, d in data.items():
            lname = len(name)
            s += "{PURPLE}" + name + "{RESET}  " + " " * (nname - lname)
            if d["installed"]:
                s += "{GREEN}installed{RESET}      "
            else:
                s += "{RED}not-installed{RESET}  "
            if d["loaded"]:
                s += "{GREEN}loaded{RESET}"
            else:
                s += "{RED}not-loaded{RESET}"
            s += "\n"
        print_color(s[:-1])


class XontribAlias(ArgParserAlias):
    """Manage xonsh extensions"""

    def build(self):
        parser = self.create_parser()
        parser.add_command(xontribs_load, prog="load")
        parser.add_command(_list)
        return parser


xontribs_main = XontribAlias(threadable=False)
