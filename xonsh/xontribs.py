"""Tools for helping manage xontributions."""
import contextlib
import importlib
import importlib.util
import json
import sys
import typing as tp
from enum import IntEnum
from pathlib import Path

from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.completers.tools import RichCompletion
from xonsh.lazyasd import LazyObject, lazyobject
from xonsh.tools import print_color, print_exception


class ExitCode(IntEnum):
    OK = 0
    NOT_FOUND = 1
    INIT_FAILED = 2


class XontribNotInstalled(Exception):
    """raised when the requested xontrib is not found"""


class _XontribPkg(tp.NamedTuple):
    """Class to define package information of a xontrib.

    Attributes
    ----------
    install
        a mapping of tools with respective install commands. e.g. {"pip": "pip install xontrib"}
    license
        license type of the xontrib package
    name
        full name of the package. e.g. "xontrib-argcomplete"
    url
        URL to the homepage of the xontrib package.
    """

    install: tp.Dict[str, str]
    license: str = ""
    name: str = ""
    url: tp.Optional[str] = None


class Xontrib(tp.NamedTuple):
    """Meta class that is used to describe xontribs.

    Attributes
    ----------
    url
        url to the home page of the xontrib.
    description
        short description about the xontrib.
    package
        pkg information for installing the xontrib
    tags
        category.
    """

    url: str = ""
    description: tp.Union[str, LazyObject] = ""
    package: tp.Optional[_XontribPkg] = None
    tags: tp.Tuple[str, ...] = ()


def get_module_docstring(module: str) -> str:
    """Find the module and return its docstring without actual import"""
    import ast

    spec = importlib.util.find_spec(module)
    if spec and spec.has_location and spec.origin:
        return ast.get_docstring(ast.parse(Path(spec.origin).read_text())) or ""
    return ""


def get_xontribs() -> tp.Dict[str, Xontrib]:
    """Return xontrib definitions lazily."""
    return dict(get_installed_xontribs())


def get_installed_xontribs(pkg_name="xontrib"):
    """List all core packages + newly installed xontribs"""
    core_pkg = _XontribPkg(
        name="xonsh",
        license="BSD 3-clause",
        install={
            "conda": "conda install -c conda-forge xonsh",
            "pip": "xpip install xonsh",
            "aura": "sudo aura -A xonsh",
            "yaourt": "yaourt -Sa xonsh",
        },
        url="http://xon.sh",
    )
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
        yield name, Xontrib(
            url="http://xon.sh",
            description=lazyobject(lambda: get_module_docstring(f"xontrib.{name}")),
            package=core_pkg,
        )


def find_xontrib(name, full_module=False):
    """Finds a xontribution from its name."""

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


def _get_xontrib_entrypoints() -> "tp.Iterable[tp.Tuple[str, str]]":
    from importlib import metadata

    for entry in metadata.entry_points(group="xonsh.xontribs"):  # type: ignore
        yield entry.name, entry.value  # type: ignore


def auto_load_xontribs_from_entrypoints(blocked: "tp.Sequence[str]" = ()):
    """Load xontrib modules exposed via setuptools's entrypoints"""

    if not hasattr(XSH.builtins, "autoloaded_xontribs"):
        XSH.builtins.autoloaded_xontribs = {}

    def get_loadable():
        for name, module in _get_xontrib_entrypoints():
            if name not in blocked:
                XSH.builtins.autoloaded_xontribs[name] = module
                yield module

    modules = list(get_loadable())
    return xontribs_load(modules, full_module=True)


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
