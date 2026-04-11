"""The xontext command."""

import shutil
import sys

from xonsh.built_ins import XSH
from xonsh.cli_utils import ArgParserAlias
from xonsh.platform import IN_APPIMAGE
from xonsh.tools import print_color


def _get_version(binary, arg_ver="--version"):
    """Helper to get version string from a python/xonsh/pip binary."""
    version = ""
    try:
        if isinstance(binary, str):
            version = XSH.subproc_captured_stdout([binary, arg_ver])
        elif isinstance(binary, list):
            version = XSH.subproc_captured_stdout(binary + [arg_ver])
    except Exception:
        if XSH.env.get("DEBUG", False):
            raise
    return (version.split("from")[0] if "from" in version else version).strip()


def xcontext_main(_args=None, _stdin=None, _stdout=None, _stderr=None):
    """Report information about the current xonsh environment."""
    # Local import: xonsh.main pulls in heavy modules, keep the dependency lazy.
    from xonsh.main import get_current_xonsh

    stdout = _stdout or sys.stdout
    current_xonsh = get_current_xonsh()
    appimage_python = XSH.env.get("_") if IN_APPIMAGE else None
    xpy = appimage_python if appimage_python else sys.executable
    xpy_ver = _get_version(xpy)

    # Per-label color tokens: python family is orange, pip family is blue,
    # everything else (xonsh variants, section headers, env vars) is yellow.
    # Printed via print_color, which dispatches to the active shell's own
    # color renderer (prompt_toolkit tokens, readline ANSI, etc.).
    ORANGE = "{#ff8800}"
    BLUE = "{BLUE}"
    YELLOW = "{YELLOW}"
    RESET = "{RESET}"
    label_color = {
        "xonsh": YELLOW,
        "xxonsh": YELLOW,
        "python": ORANGE,
        "xpython": ORANGE,
        "pip": BLUE,
        "xpip": BLUE,
        "pytest": YELLOW,
    }

    def _label(name):
        """Return ``{COLOR}name:{RESET}`` for ``print_color`` format strings."""
        return f"{label_color.get(name, YELLOW)}{name}:{RESET}"

    print_color(f"{YELLOW}[Current xonsh session]{RESET}", file=stdout)
    print_color(f"{_label('xxonsh')} {current_xonsh}", file=stdout)
    print_color(f"{_label('xpython')} {xpy}  # {xpy_ver}", file=stdout)

    xpip = XSH.aliases.get("xpip")
    if xpip:
        if isinstance(xpip, list) and all(isinstance(x, str) for x in xpip):
            print_color(f"{_label('xpip')} {' '.join(xpip)}", file=stdout)
        else:
            print_color(f"{_label('xpip')} {xpip}", file=stdout)
    else:
        print_color(f"{_label('xpip')} not found", file=stdout)

    print("", file=stdout)
    print_color(f"{YELLOW}[Current commands environment]{RESET}", file=stdout)
    cmds = ["xonsh", "python", "pip"]
    if shutil.which("pytest"):
        cmds.append("pytest")
    for cmd in cmds:
        path = shutil.which(cmd)
        if path:
            ver = ""
            if cmd == "python":
                ver = f"  # {_get_version(path)}"
            print_color(f"{_label(cmd)} {path}{ver}", file=stdout)
        else:
            print_color(f"{_label(cmd)} not found", file=stdout)
    print("", file=stdout)
    print_color(f"{YELLOW}[Current environment]{RESET}", file=stdout)
    envs = ["CONDA_DEFAULT_ENV", "VIRTUAL_ENV"]
    for ev in envs:
        val = XSH.env.get(ev)
        if val:
            print_color(f"{_label(ev)} {val}", file=stdout)
    return 0


xcontext = ArgParserAlias(
    func=xcontext_main, has_args=True, prog="xcontext", threadable=False
)
