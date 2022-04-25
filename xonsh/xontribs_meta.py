"""
This modules is the place where one would define the xontribs.
"""

import functools
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


@functools.lru_cache()
def get_xontribs() -> tp.Dict[str, Xontrib]:
    """Return xontrib definitions lazily."""
    return define_xontribs()


def define_xontribs():
    """Xontrib registry."""
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

    return {
        "abbrevs": Xontrib(
            url="http://xon.sh",
            description=lazyobject(lambda: get_module_docstring("xontrib.abbrevs")),
            package=core_pkg,
        ),
        "autovox": Xontrib(
            url="http://xon.sh",
            description="Manages automatic activation of virtual " "environments.",
            package=core_pkg,
        ),
        "bashisms": Xontrib(
            url="http://xon.sh",
            description="Enables additional Bash-like syntax while at the "
            "command prompt. For example, the ``!!`` syntax "
            "for running the previous command is now usable. "
            "Note that these features are implemented as "
            "precommand events and these additions do not "
            "affect the xonsh language when run as script. "
            "That said, you might find them useful if you "
            "have strong muscle memory.\n"
            "\n"
            "**Warning:** This xontrib may modify user "
            "command line input to implement its behavior. To "
            "see the modifications as they are applied (in "
            "unified diffformat), please set ``$XONSH_DEBUG`` "
            "to ``2`` or higher.\n"
            "\n"
            "The xontrib also adds commands: ``alias``, "
            "``export``, ``unset``, ``set``, ``shopt``, "
            "``complete``.",
            package=core_pkg,
        ),
        "coreutils": Xontrib(
            url="http://xon.sh",
            description="Additional core utilities that are implemented "
            "in xonsh. The current list includes:\n"
            "\n"
            "* cat\n"
            "* echo\n"
            "* pwd\n"
            "* tee\n"
            "* tty\n"
            "* yes\n"
            "\n"
            "In many cases, these may have a lower "
            "performance overhead than the posix command "
            "line utility with the same name. This is "
            "because these tools avoid the need for a full "
            "subprocess call. Additionally, these tools are "
            "cross-platform.",
            package=core_pkg,
        ),
        "free_cwd": Xontrib(
            url="http://xon.sh",
            description="Windows only xontrib, to release the lock on the "
            "current directory whenever the prompt is shown. "
            "Enabling this will allow the other programs or "
            "Windows Explorer to delete or rename the current "
            "or parent directories. Internally, it is "
            "accomplished by temporarily resetting CWD to the "
            "root drive folder while waiting at the prompt. "
            "This only works with the prompt_toolkit backend "
            "and can cause cause issues if any extensions are "
            "enabled that hook the prompt and relies on "
            "``os.getcwd()``",
            package=core_pkg,
        ),
        "pdb": Xontrib(
            url="http://xon.sh",
            description="Simple built-in debugger. Runs pdb on reception of "
            "SIGUSR1 signal.",
            package=core_pkg,
        ),
        "vox": Xontrib(
            url="http://xon.sh",
            description="Python virtual environment manager for xonsh.",
            package=core_pkg,
        ),
        "whole_word_jumping": Xontrib(
            url="http://xon.sh",
            description="Jumping across whole words "
            "(non-whitespace) with Ctrl+Left/Right. "
            "Alt+Left/Right remains unmodified to "
            "jump over smaller word segments. "
            "Shift+Delete removes the whole word.",
            package=core_pkg,
        ),
    }
