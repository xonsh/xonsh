"""The xontext command."""

import shutil
import subprocess
import sys

from xonsh.built_ins import XSH
from xonsh.cli_utils import ArgParserAlias
from xonsh.platform import IN_APPIMAGE


def _get_version(binary):
    """Helper to get version string from a binary."""
    try:
        out = subprocess.check_output(
            [binary, "--version"], text=True, stderr=subprocess.STDOUT
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            out = subprocess.check_output(
                [binary, "-V"], text=True, stderr=subprocess.STDOUT
            )
            return out.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""


def xcontext_main(_args=None, _stdin=None, _stdout=None, _stderr=None):
    """Report information about the current xonsh environment."""
    stdout = _stdout or sys.stdout
    print("[Current xonsh session]", file=stdout)

    current_xonsh = sys.argv[0]
    print(f"xonsh: {current_xonsh}", file=stdout)

    appimage_python = XSH.env.get("_") if IN_APPIMAGE else None
    xpy = appimage_python if appimage_python else sys.executable
    xpy_ver = _get_version(xpy)
    print(f"xpython: {xpy} # {xpy_ver}", file=stdout)

    xpip = XSH.aliases.get("xpip")
    if xpip:
        if isinstance(xpip, list) and all(isinstance(x, str) for x in xpip):
            print(f"xpip: {' '.join(xpip)}", file=stdout)
        else:
            print(f"xpip: {xpip}", file=stdout)
    else:
        print("xpip: not found", file=stdout)

    print("", file=stdout)
    print("[Current commands environment]", file=stdout)
    cmds = ["xonsh", "python", "pip"]
    if shutil.which("pytest"):
        cmds.append("pytest")
    for cmd in cmds:
        path = shutil.which(cmd)
        if path:
            ver = ""
            if cmd == "python":
                ver = f" # {_get_version(path)}"
            print(f"{cmd}: {path}{ver}", file=stdout)
        else:
            print(f"{cmd}: not found", file=stdout)
    print("", file=stdout)
    envs = ["CONDA_DEFAULT_ENV", "VIRTUAL_ENV"]
    for ev in envs:
        val = XSH.env.get(ev)
        if val:
            print(f"{ev}: {val}", file=stdout)
    return 0


xcontext = ArgParserAlias(func=xcontext_main, has_args=True, prog="xcontext")
