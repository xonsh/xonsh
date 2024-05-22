"""Tools for helping manage xontributions."""

import contextlib
import importlib
import importlib.util
import json
import os
import sys
import typing as tp
from enum import IntEnum
from pathlib import Path

from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.completers.tools import RichCompletion
from xonsh.tools import print_color, print_exception

if tp.TYPE_CHECKING:
    from importlib.metadata import Distribution, EntryPoint


class ExitCode(IntEnum):
    OK = 0
    NOT_FOUND = 1
    INIT_FAILED = 2


class XontribNotInstalled(Exception):
    """raised when the requested xontrib is not found"""


class Xontrib(tp.NamedTuple):
    """Meta class that is used to describe a xontrib"""

    module: str
    """path to the xontrib module"""
    distribution: "tp.Optional[Distribution]" = None
    """short description about the xontrib."""

    def get_description(self):
        if self.distribution:
            print(self, file=sys.stderr)
        if self.distribution and (
            summary := self.distribution.metadata.get("Summary", "")
        ):
            return summary
        return get_module_docstring(self.module)

    @property
    def url(self):
        if self.distribution:
            return self.distribution.metadata.get("Home-page", "")
        return ""

    @property
    def license(self):
        if self.distribution:
            return self.distribution.metadata.get("License", "")
        return ""

    @property
    def is_loaded(self):
        return self.module and self.module in sys.modules

    @property
    def is_auto_loaded(self):
        loaded = getattr(XSH.builtins, "autoloaded_xontribs", None) or {}
        return self.module in set(loaded.values())


def get_module_docstring(module: str) -> str:
    """Find the module and return its docstring without actual import"""
    import ast

    spec = importlib.util.find_spec(module)
    if spec and spec.has_location and spec.origin:
        return ast.get_docstring(ast.parse(Path(spec.origin).read_text())) or ""
    return ""


def get_xontribs() -> dict[str, Xontrib]:
    """Return xontrib definitions lazily."""
    return dict(_get_installed_xontribs())


def _patch_in_userdir():
    """
    Patch in user site packages directory.

    If xonsh is installed in non-writeable location, then xontribs will end up
    there, so we make them accessible."""
    if not os.access(os.path.dirname(sys.executable), os.W_OK):
        from site import getusersitepackages

        if (user_site_packages := getusersitepackages()) not in set(sys.path):
            sys.path.append(user_site_packages)


def _get_installed_xontribs(pkg_name="xontrib"):
    """List all core packages + newly installed xontribs"""
    _patch_in_userdir()
    spec = importlib.util.find_spec(pkg_name)

    def iter_paths():
        for loc in spec.submodule_search_locations:
            path = Path(loc)
            if path.exists():
                yield from path.iterdir()

    def iter_modules():
        # pkgutil is not finding `*.xsh` files
        for path in iter_paths():
            if path.suffix in {".py", ".xsh"}:
                yield path.stem

            elif path.is_dir():
                if (path / "__init__.py").exists():
                    yield path.name

    for name in iter_modules():
        module = f"xontrib.{name}"
        yield name, Xontrib(module)

    for entry in _get_xontrib_entrypoints():
        yield entry.name, Xontrib(entry.value, distribution=entry.dist)


def find_xontrib(name, full_module=False):
    """Finds a xontribution from its name."""
    _patch_in_userdir()

    # here the order is important. We try to run the correct cases first and then later trial cases
    # that will likely fail

    if name.startswith("."):
        return importlib.util.find_spec(name, package="xontrib")

    if full_module:
        return importlib.util.find_spec(name)

    autoloaded = getattr(XSH.builtins, "autoloaded_xontribs", None) or {}
    if name in autoloaded:
        return importlib.util.find_spec(autoloaded[name])

    with contextlib.suppress(ValueError):
        return importlib.util.find_spec("." + name, package="xontrib")

    return importlib.util.find_spec(name)


def xontrib_context(name, full_module=False):
    """Return a context dictionary for a xontrib of a given name."""

    spec = find_xontrib(name, full_module)
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


def prompt_xontrib_install(names: list[str]):
    """Returns a formatted string with name of xontrib package to prompt user"""
    return (
        "The following xontribs are enabled but not installed: \n"
        f"   {names}\n"
        "Please make sure that they are installed correctly by checking https://xonsh.github.io/awesome-xontribs/\n"
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
    for name, xontrib in get_xontribs().items():
        if xontrib.is_loaded is loaded:
            yield RichCompletion(
                name, append_space=True, description=xontrib.get_description()
            )


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
    suppress_warnings=False,
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
    suppress_warnings : -s, --suppress-warnings
        no warnings about missing xontribs and return code 0
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
            if not suppress_warnings:
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


def xontrib_data():
    """Collects and returns the data about installed xontribs."""
    data = {}
    for xo_name, xontrib in get_xontribs().items():
        data[xo_name] = {
            "name": xo_name,
            "loaded": xontrib.is_loaded,
            "auto": xontrib.is_auto_loaded,
            "module": xontrib.module,
        }

    return dict(sorted(data.items()))


def xontribs_loaded():
    """Returns list of loaded xontribs."""
    return [k for k, xontrib in get_xontribs().items() if xontrib.is_loaded]


def xontribs_list(to_json=False, _stdout=None):
    """List installed xontribs and show whether they are loaded or not

    Parameters
    ----------
    to_json : -j, --json
        reports results as json
    """
    data = xontrib_data()
    if to_json:
        s = json.dumps(data)
        return s
    else:
        nname = max([6] + [len(x) for x in data])
        s = ""
        for name, d in data.items():
            s += "{PURPLE}" + name + "{RESET}  " + " " * (nname - len(name))
            if d["loaded"]:
                s += "{GREEN}loaded{RESET}" + " " * 4
                if d["auto"]:
                    s += "  {GREEN}auto{RESET}"
                elif d["loaded"]:
                    s += "  {CYAN}manual{RESET}"
            else:
                s += "{RED}not-loaded{RESET}"
            s += "\n"
        print_color(s[:-1], file=_stdout)


def _get_xontrib_entrypoints() -> "tp.Iterable[EntryPoint]":
    from importlib import metadata

    name = "xonsh.xontribs"
    entries = metadata.entry_points()
    # for some reason, on CI (win py3.8) atleast, returns dict
    group = (
        entries.select(group=name)
        if hasattr(entries, "select")
        else entries.get(name, [])  # type: ignore
    )
    yield from group


def auto_load_xontribs_from_entrypoints(
    blocked: "tp.Sequence[str]" = (), verbose=False
):
    """Load xontrib modules exposed via setuptools's entrypoints"""

    if not hasattr(XSH.builtins, "autoloaded_xontribs"):
        XSH.builtins.autoloaded_xontribs = {}

    def get_loadable():
        for entry in _get_xontrib_entrypoints():
            if entry.name not in blocked:
                XSH.builtins.autoloaded_xontribs[entry.name] = entry.value
                yield entry.value

    modules = list(get_loadable())
    return xontribs_load(modules, verbose=verbose, full_module=True)


class XontribAlias(ArgParserAlias):
    """Manage xonsh extensions"""

    def build(self):
        parser = self.create_parser(prog="xontrib")
        parser.add_command(xontribs_load, prog="load")
        parser.add_command(xontribs_unload, prog="unload")
        parser.add_command(xontribs_reload, prog="reload")
        parser.add_command(xontribs_list, prog="list", default=True)
        return parser


xontribs_main = XontribAlias(threadable=False)
