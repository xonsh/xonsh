"""The xontext command."""

import sys

from xonsh.built_ins import XSH
from xonsh.cli_utils import ArgParserAlias
from xonsh.platform import IN_APPIMAGE
from xonsh.procs.executables import locate_executable
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

    # Pre-resolve the PATH-visible binaries once so we can both display them
    # in the "commands environment" section and compare them against the
    # session-specific values (xxonsh/xpython/xpip) to decide coloring.
    # Uses xonsh's own ``locate_executable`` rather than ``shutil.which``
    # because the stdlib one is flagged (deprecated for ``PathLike`` args on
    # Windows < 3.12), and xonsh's version is the recommended replacement.
    path_resolved = {
        "xonsh": locate_executable("xonsh"),
        "python": locate_executable("python"),
        "pip": locate_executable("pip"),
        "pytest": locate_executable("pytest"),
    }

    # xpip alias value as a single string (for display AND for match check).
    xpip = XSH.aliases.get("xpip")
    if isinstance(xpip, list) and all(isinstance(x, str) for x in xpip):
        xpip_display = " ".join(xpip)
    elif xpip:
        xpip_display = str(xpip)
    else:
        xpip_display = None

    # Color tokens: section headers are purple; within a family (xonsh/xxonsh,
    # python/xpython, pip/xpip) both labels go GREEN when the session binary
    # matches what ``$PATH`` resolves to — otherwise they stay in the "attention"
    # color (yellow / orange / blue). Printed via print_color, which dispatches
    # to the active shell's own color renderer.
    PURPLE = "{PURPLE}"
    GREEN = "{GREEN}"
    ORANGE = "{#ff8800}"
    BLUE = "{BLUE}"
    YELLOW = "{YELLOW}"
    RESET = "{RESET}"

    xonsh_color = GREEN if current_xonsh == path_resolved["xonsh"] else YELLOW
    python_color = GREEN if xpy == path_resolved["python"] else ORANGE
    pip_color = GREEN if xpip_display == path_resolved["pip"] else BLUE

    label_color = {
        "xonsh": xonsh_color,
        "xxonsh": xonsh_color,
        "python": python_color,
        "xpython": python_color,
        "pip": pip_color,
        "xpip": pip_color,
        "pytest": YELLOW,
    }

    def _label(name):
        """Return ``{COLOR}name:{RESET}`` for ``print_color`` format strings."""
        return f"{label_color.get(name, YELLOW)}{name}:{RESET}"

    print_color(f"{PURPLE}[Current xonsh session]{RESET}", file=stdout)
    print_color(f"{_label('xxonsh')} {current_xonsh}", file=stdout)
    print_color(f"{_label('xpython')} {xpy}  # {xpy_ver}", file=stdout)
    if xpip_display is not None:
        print_color(f"{_label('xpip')} {xpip_display}", file=stdout)
    else:
        print_color(f"{_label('xpip')} not found", file=stdout)

    print("", file=stdout)
    print_color(f"{PURPLE}[Current commands environment]{RESET}", file=stdout)
    cmds = ["xonsh", "python", "pip"]
    if path_resolved["pytest"]:
        cmds.append("pytest")
    for cmd in cmds:
        path = path_resolved[cmd]
        if path:
            ver = ""
            if cmd == "python":
                ver = f"  # {_get_version(path)}"
            print_color(f"{_label(cmd)} {path}{ver}", file=stdout)
        else:
            print_color(f"{_label(cmd)} not found", file=stdout)
    print("", file=stdout)
    print_color(f"{PURPLE}[Current environment]{RESET}", file=stdout)
    envs = ["CONDA_DEFAULT_ENV", "VIRTUAL_ENV"]
    for ev in envs:
        val = XSH.env.get(ev)
        if val:
            print_color(f"{_label(ev)} {val}", file=stdout)
    return 0


xcontext = ArgParserAlias(
    func=xcontext_main, has_args=True, prog="xcontext", threadable=False
)
