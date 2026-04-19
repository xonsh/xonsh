"""The xontext command."""

import errno
import json
import os
import subprocess
import sys

from xonsh.built_ins import XSH
from xonsh.cli_utils import ArgParserAlias
from xonsh.platform import IN_APPIMAGE
from xonsh.procs.executables import locate_executable, locate_relative_path
from xonsh.tools import print_color


def _get_version(binary, arg_ver="--version"):
    """Return ``(version_string, ok)`` for a python/xonsh/pip binary.

    ``ok`` is False when the spawn itself failed — the binary "exists"
    on disk but couldn't be executed. The canonical Windows trigger is
    the "Microsoft Store" App Execution Alias at
    ``%LOCALAPPDATA%\\Microsoft\\WindowsApps\\python.exe``: a zero-byte
    reparse point present in ``$PATH`` by default on Windows 11, which
    :func:`locate_executable` happily finds but :class:`subprocess.Popen`
    rejects with ``OSError: [WinError 1920] The file cannot be accessed
    by the system``. The caller uses ``ok=False`` to mark the row red.

    We deliberately use :mod:`subprocess` directly instead of
    ``XSH.subproc_captured_stdout``. The xonsh pipeline framework
    (``xonsh/procs/pipelines.py``) catches spawn errors and calls
    ``print_exception()`` unconditionally, which would leak a full
    traceback into the ``xcontext`` output for this exact case.
    Going through :func:`subprocess.run` lets us swallow the error
    silently (unless ``$DEBUG`` is set).
    """
    if isinstance(binary, str):
        cmd = [binary, arg_ver]
    elif isinstance(binary, list):
        cmd = list(binary) + [arg_ver]
    else:
        return "", True
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        if XSH.env.get("DEBUG", False):
            raise
        return "", False
    # Some tools (pip) print version on stdout, others (older python)
    # on stderr — fall back to stderr when stdout is empty.
    version = result.stdout or result.stderr or ""
    cleaned = (version.split("from")[0] if "from" in version else version).strip()
    return cleaned, True


def _has_symlink_cycle(path, max_depth=40):
    """Walk the symlink chain starting at ``path`` and detect cycles.

    Cross-platform fallback for when :func:`os.path.realpath` with
    ``strict=True`` raises an ``OSError`` whose ``errno`` is not
    :data:`errno.ELOOP`. On Windows, symlink loops surface as winerror
    codes (e.g. ``ERROR_CANT_ACCESS_FILE``) rather than ``ELOOP``, so
    we can't rely on errno alone — this function walks the link chain
    via :func:`os.readlink` and flags the path as cyclic if it revisits
    a normalized node or exceeds ``max_depth``.
    """
    seen: set[str] = set()
    current = path
    try:
        for _ in range(max_depth):
            normalized = os.path.normcase(os.path.abspath(current))
            if normalized in seen:
                return True
            seen.add(normalized)
            if not os.path.islink(current):
                return False
            target = os.readlink(current)
            if not os.path.isabs(target):
                target = os.path.join(os.path.dirname(current), target)
            current = target
    except OSError:
        return False
    # Depth exceeded without a non-link terminus → treat as cyclic.
    return True


def _is_executable_file(path):
    """Return True if ``path`` is an existing, accessible, executable file.

    Used by :func:`_resolve_one` to flag a displayed path as "bad" when it
    is inaccessible (missing file, stat error) or not marked executable.
    Cross-platform:

    * POSIX — checks the ``+x`` bit for the current user via
      :func:`os.access`.
    * Windows — :func:`os.access` with ``X_OK`` inspects the file
      extension against ``PATHEXT`` (Python 3.12+) or always returns
      ``True`` for readable files (earlier versions). Either way the
      accessibility check (``isfile``) still catches missing/unreachable
      paths, which is the more important signal for xcontext.

    Special case: a file named ``__main__.py`` is treated as "good" as
    long as it exists. Such files are module entry points invoked via
    ``python -m <pkg>`` and are never marked ``+x`` by convention, but
    they are a perfectly valid way to launch the package — flagging
    them red would be a false positive for ``xxonsh`` when the current
    session was started via ``python -m xonsh``.
    """
    if not path:
        return False
    try:
        if not os.path.isfile(path):
            return False
        if os.path.basename(path) == "__main__.py":
            return True
        return os.access(path, os.X_OK)
    except OSError:
        return False


def _resolve_one(value, resolve):
    """Resolve a single string path and report whether it's "bad".

    Returns ``(resolved_value, is_bad)``. A path is considered bad — and
    the caller renders its whole row in RED — if any of:

    * a symlink cycle is detected (original path is preserved as the
      display value; the caller can't meaningfully resolve further),
    * the resolved path is not an accessible executable file (missing,
      not a regular file, or lacks the ``+x`` bit).

    If ``resolve`` is False, symlinks are NOT followed, but the
    accessibility / executable check still runs on the raw value, so
    ``--no-resolve`` still reports broken entries in red.
    """
    if not value:
        return value, False

    if not os.path.exists(value):
        located = locate_relative_path(value, use_pathext=True, check_executable=True)
        if located:
            value = located

    if resolve:
        try:
            resolved = os.path.realpath(value, strict=True)
        except OSError as e:
            # POSIX reliably uses ELOOP for cycles.
            if getattr(e, "errno", None) == errno.ELOOP:
                return value, True
            # Windows / edge cases: walk the chain ourselves before giving up.
            if os.path.islink(value) and _has_symlink_cycle(value):
                return value, True
            # Non-cyclic failure (dangling link, missing target, permission
            # error, etc.) — fall back to the lenient ``realpath``, which
            # never raises but may return a non-existent path.
            resolved = os.path.realpath(value)
    else:
        resolved = value

    # ----- Accessibility / executable phase --------------------------------
    return resolved, not _is_executable_file(resolved)


def _resolve_path(value, resolve):
    """Return ``(resolved_value, is_bad)`` for the given alias value.

    Accepts ``None`` (passed through), a string path (resolved via
    :func:`_resolve_one`), or a list whose first element is an executable
    path (only the first element is resolved — the remaining args are
    kept as-is). ``is_bad`` is True if the resolved (or, for lists, the
    first-element) path is a symlink loop or is missing / not executable.
    """
    if value is None:
        return None, False
    if isinstance(value, str):
        return _resolve_one(value, resolve)
    if isinstance(value, list) and value and isinstance(value[0], str):
        head, bad = _resolve_one(value[0], resolve)
        return [head] + list(value[1:]), bad
    return value, False


def xcontext_main(no_resolve: bool = False, as_json: bool = False, _stdout=None):
    """Report information about the current xonsh environment.

    By default, all displayed binary paths (xxonsh, xpython, xpip and the
    ``$PATH``-resolved ``xonsh``/``python``/``pip``/``pytest``) have their
    symlinks followed to the real underlying files. This also makes the
    match check that decides the label color (GREEN for match, BLUE for
    mismatch) more accurate, because two paths that ultimately point to
    the same file compare equal after resolution.

    Parameters
    ----------
    no_resolve : -n, --no-resolve
        Show raw paths as-is without following symlinks (turns off the
        default resolution).
    as_json : -j, --json
        Emit the resolved paths as a JSON object on stdout instead of the
        colored text report. Top-level keys mirror the text sections
        (``session``, ``commands``, ``env``); ``commands`` always
        includes every probed name with ``null`` for entries not on
        ``$PATH``; ``env`` only contains variables that are set.
    """
    # Local import: xonsh.main pulls in heavy modules, keep the dependency lazy.
    from xonsh.main import get_current_xonsh

    stdout = _stdout or sys.stdout
    resolve = not no_resolve

    current_xonsh, xxonsh_bad = _resolve_path(get_current_xonsh(), resolve)
    appimage_python = XSH.env.get("_") if IN_APPIMAGE else None
    xpy, xpython_bad = _resolve_path(
        appimage_python if appimage_python else sys.executable, resolve
    )
    xpy_ver, xpy_ver_ok = _get_version(xpy)
    xpython_bad = xpython_bad or not xpy_ver_ok

    # Pre-resolve the PATH-visible binaries once so we can both display them
    # in the "commands environment" section and compare them against the
    # session-specific values (xxonsh/xpython/xpip) to decide coloring.
    # Uses xonsh's own ``locate_executable`` rather than ``shutil.which``
    # because the stdlib one is flagged (deprecated for ``PathLike`` args on
    # Windows < 3.12), and xonsh's version is the recommended replacement.
    path_resolved = {}
    path_bad: dict[str, bool] = {}
    for cmd in ("xonsh", "python", "pip", "pytest", "uv"):
        path, bad = _resolve_path(locate_executable(cmd), resolve)
        path_resolved[cmd] = path
        path_bad[cmd] = bad

    # xpip alias value as a single string (for display AND for match check).
    xpip, xpip_bad = _resolve_path(XSH.aliases.get("xpip"), resolve)
    if isinstance(xpip, list) and all(isinstance(x, str) for x in xpip):
        xpip_display = " ".join(xpip)
    elif xpip:
        xpip_display = str(xpip)
    else:
        xpip_display = None

    if as_json:
        # Skip color/version probes — JSON consumers want raw paths only.
        # ``commands`` keeps every probed key (None for not-on-PATH) so the
        # shape is predictable; ``env`` mirrors the text section and omits
        # unset variables.
        report = {
            "session": {
                "xxonsh": current_xonsh,
                "xpython": xpy,
                "xpip": xpip_display,
            },
            "commands": {cmd: path_resolved[cmd] for cmd in path_resolved},
            "env": {
                ev: XSH.env.get(ev)
                for ev in ("CONDA_DEFAULT_ENV", "VIRTUAL_ENV")
                if XSH.env.get(ev)
            },
        }
        print(json.dumps(report, indent=2), file=stdout)
        return 0

    # Color tokens: section headers are purple; within a family (xonsh/xxonsh,
    # python/xpython, pip/xpip) both labels go GREEN when the session binary
    # matches what ``$PATH`` resolves to, otherwise BLUE. Labels outside any
    # family (pytest, ``[Current environment]`` vars) stay YELLOW. Any row
    # whose path is "bad" — symlink loop, missing, inaccessible, or not
    # executable — is rendered entirely in RED, overriding the row color.
    # Printed via print_color, which dispatches to the active shell's own
    # color renderer.
    PURPLE = "{PURPLE}"
    GREEN = "{GREEN}"
    BLUE = "{BLUE}"
    YELLOW = "{YELLOW}"
    RED = "{RED}"
    RESET = "{RESET}"

    xonsh_color = GREEN if current_xonsh == path_resolved["xonsh"] else BLUE
    python_color = GREEN if xpy == path_resolved["python"] else BLUE
    pip_color = GREEN if xpip_display == path_resolved["pip"] else BLUE

    label_color = {
        "xonsh": xonsh_color,
        "xxonsh": xonsh_color,
        "python": python_color,
        "xpython": python_color,
        "pip": pip_color,
        "xpip": pip_color,
        "pytest": YELLOW,
        "uv": YELLOW,
    }

    def _format_row(name, value, ver="", bad=False):
        """Build a ``print_color`` format string for one label/value row.

        If ``bad`` is True, the whole line (label + value + version) is
        wrapped in :data:`RED` to flag the problem (cycle, missing file,
        or not executable) — the label's normal color is overridden.
        Otherwise the label uses its family color and the value is
        rendered in the default terminal color.
        """
        if bad:
            return f"{RED}{name}: {value}{ver}{RESET}"
        color = label_color.get(name, YELLOW)
        return f"{color}{name}:{RESET} {value}{ver}"

    print_color(f"{PURPLE}[Current xonsh session]{RESET}", file=stdout)
    print_color(
        _format_row("xxonsh", current_xonsh, bad=xxonsh_bad),
        file=stdout,
    )
    print_color(
        _format_row("xpython", xpy, ver=f"  # {xpy_ver}", bad=xpython_bad),
        file=stdout,
    )
    if xpip_display is not None:
        print_color(
            _format_row("xpip", xpip_display, bad=xpip_bad),
            file=stdout,
        )
    else:
        print_color(_format_row("xpip", "not found"), file=stdout)

    print("", file=stdout)
    print_color(f"{PURPLE}[Current commands environment]{RESET}", file=stdout)
    cmds = ["xonsh", "python", "pip"]
    if path_resolved["pytest"]:
        cmds.append("pytest")
    if path_resolved["uv"]:
        cmds.append("uv")
    for cmd in cmds:
        path = path_resolved[cmd]
        bad = path_bad[cmd]
        if path:
            ver = ""
            if cmd == "python":
                ver_str, ver_ok = _get_version(path)
                ver = f"  # {ver_str}"
                # Spawn failure (e.g. Windows Store ``python.exe``
                # alias) → flag the whole row as bad even though the
                # file technically "exists".
                bad = bad or not ver_ok
            print_color(_format_row(cmd, path, ver=ver, bad=bad), file=stdout)
        else:
            print_color(_format_row(cmd, "not found"), file=stdout)
    envs = ["CONDA_DEFAULT_ENV", "VIRTUAL_ENV"]
    env_rows = [(ev, XSH.env.get(ev)) for ev in envs]
    env_rows = [(ev, val) for ev, val in env_rows if val]
    if env_rows:
        print("", file=stdout)
        print_color(f"{PURPLE}[Current environment]{RESET}", file=stdout)
        for ev, val in env_rows:
            print_color(_format_row(ev, val), file=stdout)
    return 0


xcontext = ArgParserAlias(
    func=xcontext_main, has_args=True, prog="xcontext", threadable=False
)
