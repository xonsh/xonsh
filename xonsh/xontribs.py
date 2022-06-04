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


class XontribNotInstalled(Exception):
    """raised when the requested xontrib is not found"""


def find_xontrib(name):
    """Finds a xontribution from its name."""
    spec = None
    if name.startswith("."):
        spec = importlib.util.find_spec(name, package="xontrib")
    else:
        with contextlib.suppress(ValueError):
            spec = importlib.util.find_spec("." + name, package="xontrib")
    return spec or importlib.util.find_spec(name)


def xontrib_context(name, full_module=False):
    """Return a context dictionary for a xontrib of a given name."""
    if full_module:
        spec = importlib.util.find_spec(name)
    else:
        spec = find_xontrib(name)
    if spec is None:
        return None
    module = importlib.import_module(spec.name)
    ctx = {}

    def _get__all__():
        pubnames = getattr(module, "__all__", None)
        if pubnames is None:
            for k in dir(module):
                if not k.startswith("_"):
                    yield k, getattr(module, k)
        else:
            for attr in pubnames:
                yield attr, getattr(module, attr)

    entrypoint = getattr(module, "_load_xontrib_", None)
    if entrypoint is None:
        ctx.update(dict(_get__all__()))
    else:
        result = entrypoint(xsh=XSH)
        if result is not None:
            ctx.update(result)
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


def update_context(name, ctx: dict, full_module=False):
    """Updates a context in place from a xontrib."""
    modctx = xontrib_context(name, full_module)
    if modctx is None:
        raise XontribNotInstalled(f"Xontrib - {name} is not found.")
    else:
        ctx.update(modctx)
    return ctx


def _xontrib_name_completions(loaded=False):
    for name, meta, spec in _get_xontrib_specs():
        if (spec.name in sys.modules) is loaded:
            yield RichCompletion(name, append_space=True, description=meta.description)


def xontrib_names_completer(**_):
    yield from _xontrib_name_completions(loaded=False)


def xontrib_unload_completer(**_):
    yield from _xontrib_name_completions(loaded=True)


def xontribs_load(
    names: Annotated[
        tp.Sequence[str],
        Arg(nargs="+", completer=xontrib_names_completer),
    ] = (),
    verbose=False,
    full_module=False,
):
    """Load xontribs from a list of names

    Parameters
    ----------
    names
        names of xontribs
    verbose : -v, --verbose
        verbose output
    full_module : -f, --full
        indicates that the names are fully qualified module paths and not inside ``xontrib`` package
    """
    ctx = {} if XSH.ctx is None else XSH.ctx
    res = ExitCode.OK
    stdout = None
    stderr = None
    bad_imports = []
    for name in names:
        if verbose:
            print(f"loading xontrib {name!r}")
        try:
            update_context(name, ctx=ctx, full_module=full_module)
        except XontribNotInstalled:
            bad_imports.append(name)
        except Exception:
            res = ExitCode.INIT_FAILED
            print_exception(f"Failed to load xontrib {name}.")
    if bad_imports:
        res = ExitCode.NOT_FOUND
        stderr = prompt_xontrib_install(bad_imports)
    return stdout, stderr, res


def xontribs_unload(
    names: Annotated[
        tp.Sequence[str],
        Arg(nargs="+", completer=xontrib_unload_completer),
    ] = (),
    verbose=False,
):
    """Unload the given xontribs

    Parameters
    ----------
    names
        name of xontribs to unload

    Notes
    -----
    Proper cleanup can be implemented by the xontrib. The default is equivalent to ``del sys.modules[module]``.
    """
    for name in names:
        if verbose:
            print(f"unloading xontrib {name!r}")
        spec = find_xontrib(name)
        try:
            if spec and spec.name in sys.modules:
                module = sys.modules[spec.name]
                unloader = getattr(module, "_unload_xontrib_", None)
                if unloader is not None:
                    unloader(XSH)
                del sys.modules[spec.name]
        except Exception as ex:
            print_exception(f"Failed to unload xontrib {name} ({ex})")


def xontribs_reload(
    names: Annotated[
        tp.Sequence[str],
        Arg(nargs="+", completer=xontrib_unload_completer),
    ] = (),
    verbose=False,
):
    """Reload the given xontribs

    Parameters
    ----------
    names
        name of xontribs to reload
    """
    for name in names:
        if verbose:
            print(f"reloading xontrib {name!r}")
        xontribs_unload([name])
        xontribs_load([name])


def _get_xontrib_specs():
    for xo_name, meta in get_xontribs().items():
        yield xo_name, meta, find_xontrib(xo_name)


def xontrib_data():
    """Collects and returns the data about installed xontribs."""
    data = {}
    for xo_name, _, spec in _get_xontrib_specs():
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


def _get_xontrib_entrypoints(blocked) -> "tp.Iterable[str]":
    from importlib.metadata import entry_points

    for entry in entry_points(group="xonsh.xontribs"):
        if entry not in blocked:
            yield entry.value


def auto_load_xontribs_from_entrypoints(blocked: "tuple[str]" = ()):
    """Load xontrib modules exposed via setuptools's entrypoints"""
    xontribs = list(_get_xontrib_entrypoints(blocked))
    return xontribs_load(xontribs, full_module=True)


class XontribAlias(ArgParserAlias):
    """Manage xonsh extensions"""

    def build(self):
        parser = self.create_parser(prog="xontrib")
        parser.add_command(xontribs_load, prog="load")
        parser.add_command(xontribs_unload, prog="unload")
        parser.add_command(xontribs_reload, prog="reload")
        parser.add_command(_list)
        return parser


xontribs_main = XontribAlias(threadable=False)
