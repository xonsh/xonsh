"""
This modules is the place where one would define the xontribs.
"""

import importlib.util
import typing as tp
from pathlib import Path

from xonsh.lazyasd import LazyObject, lazyobject


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
