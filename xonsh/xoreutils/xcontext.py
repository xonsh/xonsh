"""The xontext command."""

import errno
import functools
import json
import os
import subprocess
import sys
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Resolved:
    """A resolved binary path probed by :class:`XContext`.

    ``path`` may be a string (resolved file path), a list (alias args
    where ``path[0]`` is the executable), or ``None`` (not found / no
    such alias). ``bad`` is True when the entry is unusable: symlink
    loop, missing file, not a regular file, lacks ``+x``, or its
    ``--version`` probe failed (Windows Store ``python.exe`` alias).
    ``version`` is the trimmed ``--version`` output, populated only
    for python-family entries.

    The :attr:`display` property renders the entry as a single string —
    list paths are space-joined the way the CLI shows them, plain
    strings pass through, and ``None`` becomes ``None`` so callers can
    detect "not found" without re-checking ``path``.
    """

    path: object = None
    bad: bool = False
    version: str = ""

    @property
    def display(self):
        if isinstance(self.path, list) and all(isinstance(x, str) for x in self.path):
            return " ".join(self.path)
        return str(self.path) if self.path else None


def _cached_method(method):
    """Per-instance, opt-in memoization for no-arg instance methods.

    Stores the result in ``self._cache`` keyed by the method name when
    caching is enabled, so the cache is bounded to the lifetime of the
    instance — a plain :func:`functools.cache` on bound methods would
    leak ``self`` references at the class level. When the holder
    instance has ``self._cache is None`` (the default constructor mode),
    every call re-runs the underlying probe so callers that hold onto an
    :class:`XContext` see fresh ``$PATH`` / alias state on each read.
    """
    name = method.__name__

    @functools.wraps(method)
    def wrapper(self):
        if self._cache is None:
            return method(self)
        if name not in self._cache:
            self._cache[name] = method(self)
        return self._cache[name]

    return wrapper


class XContext:
    """Lazy collector of every value displayed by ``xcontext``.

    Each ``get_*`` method computes its value and returns a
    :class:`Resolved` (or, for env getters, a plain string / ``None``).
    Construct with ``resolve=False`` to skip symlink resolution — the
    accessibility / ``+x`` check still runs, matching the
    ``--no-resolve`` CLI flag.

    Caching is **off by default** so a long-lived instance always
    reflects the current ``$PATH`` and alias state — callers that read a
    getter twice after mutating the environment get the new value, not a
    stale snapshot. Pass ``cache=True`` to enable per-instance memoization
    for the lifetime of the report; ``xcontext_main`` does this so each
    ``--version`` subprocess runs at most once per invocation.
    """

    def __init__(self, resolve=True, cache=False):
        self._resolve = resolve
        self._cache: dict | None = {} if cache else None

    # ---- session: what the running xonsh process actually uses --------

    @_cached_method
    def get_session_xxonsh(self) -> Resolved:
        """Return the path to the currently running xonsh interpreter."""
        # Local import: ``xonsh.main`` pulls in heavy modules.
        from xonsh.main import get_current_xonsh

        path, bad = _resolve_path(get_current_xonsh(), self._resolve)
        return Resolved(path=path, bad=bad)

    @_cached_method
    def get_session_xpython(self) -> Resolved:
        """Return the python interpreter that's running this xonsh.

        Inside an AppImage, ``sys.executable`` points at the AppImage
        bootstrap rather than the bundled python — fall back to ``$_``
        so the displayed binary is something the user can actually
        invoke.
        """
        appimage_python = XSH.env.get("_") if IN_APPIMAGE else None
        path, bad = _resolve_path(
            appimage_python if appimage_python else sys.executable, self._resolve
        )
        ver, ver_ok = _get_version(path)
        return Resolved(path=path, bad=bad or not ver_ok, version=ver)

    @_cached_method
    def get_session_xpip(self) -> Resolved:
        """Return the ``xpip`` alias value (typically ``[python, -m, pip]``)."""
        path, bad = _resolve_path(XSH.aliases.get("xpip"), self._resolve)
        return Resolved(path=path, bad=bad)

    # ---- commands: what ``$PATH`` lookup currently resolves to --------

    def _get_command(self, name: str) -> Resolved:
        path, bad = _resolve_path(locate_executable(name), self._resolve)
        return Resolved(path=path, bad=bad)

    @_cached_method
    def get_commands_xonsh(self) -> Resolved:
        """Return the ``xonsh`` binary that ``$PATH`` resolves to."""
        return self._get_command("xonsh")

    @_cached_method
    def get_commands_python(self) -> Resolved:
        """Return the ``python`` binary on ``$PATH``, with version probed.

        The version probe doubles as a spawn check — a Windows Store
        ``python.exe`` App Execution Alias can be located on ``$PATH``
        but raises WinError 1920 on execution. Such entries get
        ``bad=True`` so the row renders red.
        """
        base = self._get_command("python")
        if not base.path:
            return base
        ver, ver_ok = _get_version(base.path)
        return Resolved(path=base.path, bad=base.bad or not ver_ok, version=ver)

    @_cached_method
    def get_commands_pip(self) -> Resolved:
        """Return the ``pip`` binary that ``$PATH`` resolves to."""
        return self._get_command("pip")

    @_cached_method
    def get_commands_pytest(self) -> Resolved:
        """Return the ``pytest`` binary that ``$PATH`` resolves to."""
        return self._get_command("pytest")

    @_cached_method
    def get_commands_uv(self) -> Resolved:
        """Return the ``uv`` binary that ``$PATH`` resolves to."""
        return self._get_command("uv")

    # ---- env: virtualenv / conda flags --------------------------------

    def get_env_conda_default_env(self):
        """Return ``$CONDA_DEFAULT_ENV`` or ``None`` if unset."""
        return XSH.env.get("CONDA_DEFAULT_ENV")

    def get_env_virtual_env(self):
        """Return ``$VIRTUAL_ENV`` or ``None`` if unset."""
        return XSH.env.get("VIRTUAL_ENV")


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
    stdout = _stdout or sys.stdout
    # cache=True so each ``--version`` subprocess runs at most once
    # across the color-check + row-print + match comparisons.
    xc = XContext(resolve=not no_resolve, cache=True)

    session_xxonsh = xc.get_session_xxonsh()
    session_xpython = xc.get_session_xpython()
    session_xpip = xc.get_session_xpip()
    cmd_xonsh = xc.get_commands_xonsh()
    cmd_pip = xc.get_commands_pip()
    cmd_pytest = xc.get_commands_pytest()
    cmd_uv = xc.get_commands_uv()

    if as_json:
        # Skip color/version probes — JSON consumers want raw paths only.
        # ``commands`` keeps every probed key (None for not-on-PATH) so the
        # shape is predictable; ``env`` mirrors the text section and omits
        # unset variables. Use ``_get_command`` for python here so we don't
        # spawn a subprocess just to throw the version away.
        cmd_python_raw = xc._get_command("python")
        report = {
            "session": {
                "xxonsh": session_xxonsh.path,
                "xpython": session_xpython.path,
                "xpip": session_xpip.display,
            },
            "commands": {
                "xonsh": cmd_xonsh.path,
                "python": cmd_python_raw.path,
                "pip": cmd_pip.path,
                "pytest": cmd_pytest.path,
                "uv": cmd_uv.path,
            },
            "env": {
                ev: val
                for ev, val in (
                    ("CONDA_DEFAULT_ENV", xc.get_env_conda_default_env()),
                    ("VIRTUAL_ENV", xc.get_env_virtual_env()),
                )
                if val
            },
        }
        print(json.dumps(report, indent=2), file=stdout)
        return 0

    # The version-probing variant only runs in the colored path, where
    # the version string is actually displayed.
    cmd_python = xc.get_commands_python()

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

    xonsh_color = GREEN if session_xxonsh.path == cmd_xonsh.path else BLUE
    python_color = GREEN if session_xpython.path == cmd_python.path else BLUE
    pip_color = GREEN if session_xpip.display == cmd_pip.path else BLUE

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
        _format_row("xxonsh", session_xxonsh.path, bad=session_xxonsh.bad),
        file=stdout,
    )
    print_color(
        _format_row(
            "xpython",
            session_xpython.path,
            ver=f"  # {session_xpython.version}",
            bad=session_xpython.bad,
        ),
        file=stdout,
    )
    if session_xpip.display is not None:
        print_color(
            _format_row("xpip", session_xpip.display, bad=session_xpip.bad),
            file=stdout,
        )
    else:
        print_color(_format_row("xpip", "not found"), file=stdout)

    print("", file=stdout)
    print_color(f"{PURPLE}[Current commands environment]{RESET}", file=stdout)
    cmd_rows: list[tuple[str, Resolved]] = [
        ("xonsh", cmd_xonsh),
        ("python", cmd_python),
        ("pip", cmd_pip),
    ]
    if cmd_pytest.path:
        cmd_rows.append(("pytest", cmd_pytest))
    if cmd_uv.path:
        cmd_rows.append(("uv", cmd_uv))
    for name, r in cmd_rows:
        if r.path:
            ver = f"  # {r.version}" if r.version else ""
            print_color(_format_row(name, r.path, ver=ver, bad=r.bad), file=stdout)
        else:
            print_color(_format_row(name, "not found"), file=stdout)

    env_rows = [
        (ev, val)
        for ev, val in (
            ("CONDA_DEFAULT_ENV", xc.get_env_conda_default_env()),
            ("VIRTUAL_ENV", xc.get_env_virtual_env()),
        )
        if val
    ]
    if env_rows:
        print("", file=stdout)
        print_color(f"{PURPLE}[Current environment]{RESET}", file=stdout)
        for ev, val in env_rows:
            print_color(_format_row(ev, val), file=stdout)
    return 0


xcontext = ArgParserAlias(
    func=xcontext_main, has_args=True, prog="xcontext", threadable=False
)
