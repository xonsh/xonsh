"""Tools for helping manage xontributions."""
import os
import sys
import json
import builtins
import argparse
import functools
import importlib
import importlib.util

from enum import IntEnum
from xonsh.tools import print_color, print_exception, unthreadable


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


def prompt_xontrib_install(names):
    """Returns a formatted string with name of xontrib package to prompt user"""
    md = xontrib_metadata()
    packages = []
    for name in names:
        for xontrib in md["xontribs"]:
            if xontrib["name"] == name:
                packages.append(xontrib["package"])

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
        ctx = builtins.__xonsh__.ctx
    modctx = xontrib_context(name)
    if modctx is None:
        if not hasattr(update_context, "bad_imports"):
            update_context.bad_imports = []
        update_context.bad_imports.append(name)
        return ctx
    return ctx.update(modctx)


@functools.lru_cache()
def xontrib_metadata():
    """Loads and returns the xontribs.json file."""
    impres = None
    pkg_resources = None

    # NOTE: Reduce all of these alternate implementations when the minimum Python
    #       is >=3.7
    try:
        # Python 3.7
        import importlib.resources as impres
    except ImportError:
        try:
            # Optional backport for <3.7
            import importlib_resources as impres
        except ImportError:
            try:
                # Try the slower and clunkier pkg_resources
                # This is only available if setuptools is part of the environment
                import pkg_resources
            except ImportError:
                pass

    if impres:
        with impres.open_text("xonsh", "xontribs.json") as f:
            md = json.load(f)
    elif pkg_resources:
        # Despite the name, this is a bytes
        bytesdata = pkg_resources.resource_string("xonsh", "xontribs.json")
        md = json.loads(bytesdata.decode("utf-8"))
    else:
        path = os.path.join(os.path.dirname(__file__), "xontribs.json")
        with open(path, "r") as f:
            md = json.load(f)

    return md


def xontribs_load(names, verbose=False):
    """Load xontribs from a list of names"""
    ctx = builtins.__xonsh__.ctx
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
        prompt_xontrib_install(update_context.bad_imports)
        del update_context.bad_imports
    return res


def _load(ns):
    """load xontribs"""
    return xontribs_load(ns.names, verbose=ns.verbose)


def _list(ns):
    """Lists xontribs."""
    meta = xontrib_metadata()
    data = []
    nname = 6  # ensures some buffer space.
    names = None if len(ns.names) == 0 else set(ns.names)
    for md in meta["xontribs"]:
        name = md["name"]
        if names is not None and md["name"] not in names:
            continue
        nname = max(nname, len(name))
        spec = find_xontrib(name)
        if spec is None:
            installed = loaded = False
        else:
            installed = True
            loaded = spec.name in sys.modules
        d = {"name": name, "installed": installed, "loaded": loaded}
        data.append(d)
    if ns.json:
        jdata = {d.pop("name"): d for d in data}
        s = json.dumps(jdata)
        print(s)
    else:
        s = ""
        for d in data:
            name = d["name"]
            lname = len(name)
            s += "{PURPLE}" + name + "{NO_COLOR}  " + " " * (nname - lname)
            if d["installed"]:
                s += "{GREEN}installed{NO_COLOR}      "
            else:
                s += "{RED}not-installed{NO_COLOR}  "
            if d["loaded"]:
                s += "{GREEN}loaded{NO_COLOR}"
            else:
                s += "{RED}not-loaded{NO_COLOR}"
            s += "\n"
        print_color(s[:-1])


@functools.lru_cache()
def _create_xontrib_parser():
    # parse command line args
    parser = argparse.ArgumentParser(
        prog="xontrib", description="Manages xonsh extensions"
    )
    subp = parser.add_subparsers(title="action", dest="action")
    load = subp.add_parser("load", help="loads xontribs")
    load.add_argument(
        "-v", "--verbose", action="store_true", default=False, dest="verbose"
    )
    load.add_argument("names", nargs="+", default=(), help="names of xontribs")
    lyst = subp.add_parser(
        "list", help=("list xontribs, whether they are " "installed, and loaded.")
    )
    lyst.add_argument(
        "--json", action="store_true", default=False, help="reports results as json"
    )
    lyst.add_argument("names", nargs="*", default=(), help="names of xontribs")
    return parser


_MAIN_XONTRIB_ACTIONS = {"load": _load, "list": _list}


@unthreadable
def xontribs_main(args=None, stdin=None):
    """Alias that loads xontribs"""
    if not args or (
        args[0] not in _MAIN_XONTRIB_ACTIONS and args[0] not in {"-h", "--help"}
    ):
        args.insert(0, "load")
    parser = _create_xontrib_parser()
    ns = parser.parse_args(args)
    if ns.action is None:  # apply default action
        ns = parser.parse_args(["load"] + args)
    return _MAIN_XONTRIB_ACTIONS[ns.action](ns)
