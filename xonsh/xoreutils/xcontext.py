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

    Returns ``(original, resolved, is_bad)``. ``original`` is the input
    value preserved verbatim — the caller renders it on the ``name:``
    row. ``resolved`` is the same value after the Windows PATHEXT lookup
    and, when ``resolve`` is True, ``os.path.realpath`` — the caller
    renders it on the optional ``name resolved:`` row when it differs
    from ``original``. A path is considered bad — and the caller renders
    its whole row in RED — if any of:

    * a symlink cycle is detected (both ``original`` and ``resolved``
      keep the input verbatim because the chain can't be followed),
    * the resolved path is not an accessible executable file (missing,
      not a regular file, or lacks the ``+x`` bit).

    If ``resolve`` is False, symlinks are NOT followed, but the
    accessibility / executable check still runs on the raw value, so
    ``--no-resolve`` still reports broken entries in red. The Windows
    PATHEXT fallback also still runs, so ``resolved`` can legitimately
    differ from ``original`` even in ``--no-resolve`` mode.
    """
    if not value:
        return value, value, False

    original = value

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
                return original, value, True
            # Windows / edge cases: walk the chain ourselves before giving up.
            if os.path.islink(value) and _has_symlink_cycle(value):
                return original, value, True
            # Non-cyclic failure (dangling link, missing target, permission
            # error, etc.) — fall back to the lenient ``realpath``, which
            # never raises but may return a non-existent path.
            resolved = os.path.realpath(value)
    else:
        resolved = value

    # ----- Accessibility / executable phase --------------------------------
    return original, resolved, not _is_executable_file(resolved)


def _resolve_path(value, resolve):
    """Return ``(original_value, resolved_value, is_bad)`` for an alias value.

    Accepts ``None`` (passed through), a string path (resolved via
    :func:`_resolve_one`), or a list whose first element is an executable
    path (only the first element is resolved — the remaining args are
    kept as-is on both the original and the resolved side). ``is_bad`` is
    True if the resolved (or, for lists, the first-element) path is a
    symlink loop or is missing / not executable.
    """
    if value is None:
        return None, None, False
    if isinstance(value, str):
        return _resolve_one(value, resolve)
    if isinstance(value, list) and value and isinstance(value[0], str):
        orig_head, resolved_head, bad = _resolve_one(value[0], resolve)
        tail = list(value[1:])
        return [orig_head] + tail, [resolved_head] + tail, bad
    return value, value, False


@dataclass(frozen=True)
class Resolved:
    """A binary path probed by :class:`XContext`.

    ``path`` is the input value as discovered (whatever
    :func:`locate_executable`, :func:`get_current_xonsh`,
    :data:`sys.executable`, or the alias lookup returned) — preserved
    verbatim so the colored output and the JSON consumer can show the
    user the path they would actually type. ``resolved`` is the same
    value after PATHEXT lookup and (in default mode) ``os.path.realpath``;
    when symlinks weren't followed *and* no PATHEXT substitution
    happened, it equals ``path``. Both may be a string, a list (alias
    args where ``[0]`` is the executable), or ``None`` (not found / no
    such alias).

    ``bad`` is True when the entry is unusable: symlink loop, missing
    file, not a regular file, lacks ``+x``, or its ``--version`` probe
    failed (Windows Store ``python.exe`` alias). ``version`` is the
    trimmed ``--version`` output, populated only for python-family
    entries.

    :attr:`display` renders ``path`` for the colored row; list paths
    are space-joined the way the CLI shows them, plain strings pass
    through, and ``None`` becomes ``None`` so callers can detect "not
    found" without re-checking ``path``. :attr:`resolved_display`
    renders the same thing for ``resolved``. :attr:`differs` reports
    whether the resolved value is meaningfully different from the
    input — when it's False, the colored renderer suppresses the
    ``name resolved:`` row.
    """

    path: object = None
    resolved: object = None
    bad: bool = False
    version: str = ""

    @property
    def display(self):
        return self._render(self.path)

    @property
    def resolved_display(self):
        return self._render(self.resolved)

    @property
    def differs(self):
        """True when ``resolved`` is set and is not identical to ``path``.

        Drives whether the colored renderer emits the secondary
        ``name resolved:`` row — same value on both sides would just
        duplicate the line.
        """
        return self.resolved is not None and self.resolved != self.path

    @staticmethod
    def _render(value):
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return " ".join(value)
        return str(value) if value else None


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

        original, resolved, bad = _resolve_path(get_current_xonsh(), self._resolve)
        return Resolved(path=original, resolved=resolved, bad=bad)

    @_cached_method
    def get_session_xpython(self) -> Resolved:
        """Return the python interpreter that's running this xonsh.

        Inside an AppImage, ``sys.executable`` points at the AppImage
        bootstrap rather than the bundled python — fall back to ``$_``
        so the displayed binary is something the user can actually
        invoke.
        """
        appimage_python = XSH.env.get("_") if IN_APPIMAGE else None
        original, resolved, bad = _resolve_path(
            appimage_python if appimage_python else sys.executable, self._resolve
        )
        # Probe the resolved binary — the original may be a symlink or
        # a non-existent shim (PATHEXT case) that can't be executed
        # directly.
        ver, ver_ok = _get_version(resolved)
        return Resolved(
            path=original, resolved=resolved, bad=bad or not ver_ok, version=ver
        )

    @_cached_method
    def get_session_xpip(self) -> Resolved:
        """Return the ``xpip`` alias value (typically ``[python, -m, pip]``)."""
        original, resolved, bad = _resolve_path(XSH.aliases.get("xpip"), self._resolve)
        return Resolved(path=original, resolved=resolved, bad=bad)

    # ---- commands: what ``$PATH`` lookup currently resolves to --------

    def _get_command(self, name: str) -> Resolved:
        original, resolved, bad = _resolve_path(locate_executable(name), self._resolve)
        return Resolved(path=original, resolved=resolved, bad=bad)

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
        ver, ver_ok = _get_version(base.resolved)
        return Resolved(
            path=base.path,
            resolved=base.resolved,
            bad=base.bad or not ver_ok,
            version=ver,
        )

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

    The colored text report shows the input path of each binary on a
    ``name:`` row and — when symlink resolution (or, on Windows, the
    PATHEXT lookup) changes it — the resolved path on a second
    ``name resolved:`` row. The label-color match check (GREEN/BLUE)
    uses the resolved paths so two entries that ultimately point to the
    same underlying file compare equal even when their input paths
    differ.

    Parameters
    ----------
    no_resolve : -n, --no-resolve
        Show raw paths as-is without following symlinks (turns off the
        default resolution). The accessibility / executable check still
        runs, so broken entries are still flagged in red.
    as_json : -j, --json
        Emit the paths as a JSON object on stdout instead of the colored
        text report. Top-level keys mirror the text sections
        (``session``, ``commands``, ``env``). Each entry in ``session``
        and ``commands`` carries the input path under its base key
        (e.g. ``xxonsh``) — and, **only when the resolved path differs
        from the input**, an additional sibling key with a ``_resolved``
        suffix (e.g. ``xxonsh_resolved``). This mirrors the colored
        output's secondary row: with ``--no-resolve`` (or when paths
        already match their realpath) the ``_resolved`` keys are
        omitted entirely instead of duplicating the value. ``env`` only
        contains variables that are set.
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
        # Skip the version probe — JSON consumers can call ``--version``
        # themselves if they need it. ``commands`` always lists every
        # probed name (``null`` for not-on-PATH) so the base schema is
        # stable; the ``_resolved`` siblings, however, are only emitted
        # when ``r.differs`` is True — same rule as the colored output's
        # secondary row. That way ``--no-resolve`` (and the common case
        # where the input is already a realpath) produce a clean JSON
        # without echoing every path twice.
        cmd_python_raw = xc._get_command("python")

        def _section(items):
            out: dict = {}
            for key, r in items:
                out[key] = r.display
                if r.differs:
                    out[f"{key}_resolved"] = r.resolved_display
            return out

        report = {
            "session": _section(
                [
                    ("xxonsh", session_xxonsh),
                    ("xpython", session_xpython),
                    ("xpip", session_xpip),
                ]
            ),
            "commands": _section(
                [
                    ("xonsh", cmd_xonsh),
                    ("python", cmd_python_raw),
                    ("pip", cmd_pip),
                    ("pytest", cmd_pytest),
                    ("uv", cmd_uv),
                ]
            ),
            "env": {
                ev: val
                for ev, val in (
                    ("VIRTUAL_ENV", xc.get_env_virtual_env()),
                    ("CONDA_DEFAULT_ENV", xc.get_env_conda_default_env()),
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
    # matches what ``$PATH`` resolves to, otherwise BLUE. The match check
    # compares the *resolved* paths so two entries that point at the same
    # underlying file via different symlinks still register as the same.
    # Labels outside any family (pytest, ``[Current environment]`` vars)
    # stay YELLOW. Any row whose path is "bad" — symlink loop, missing,
    # inaccessible, or not executable — is rendered entirely in RED,
    # overriding the row color. Printed via print_color, which dispatches
    # to the active shell's own color renderer.
    PURPLE = "{PURPLE}"
    GREEN = "{GREEN}"
    BLUE = "{BLUE}"
    YELLOW = "{YELLOW}"
    RED = "{RED}"
    RESET = "{RESET}"

    xonsh_color = GREEN if session_xxonsh.resolved == cmd_xonsh.resolved else BLUE
    python_color = GREEN if session_xpython.resolved == cmd_python.resolved else BLUE
    # ``xpip`` is a ``[python, -m, pip]`` list while the PATH-resolved ``pip``
    # is a plain string, so a direct equality compare wouldn't match by
    # construction. Compare the executable head element instead.
    xpip_head = (
        session_xpip.resolved[0]
        if isinstance(session_xpip.resolved, list) and session_xpip.resolved
        else None
    )
    pip_color = GREEN if xpip_head == cmd_pip.resolved else BLUE

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
        rendered in the default terminal color. ``name`` may carry the
        trailing ``" resolved"`` suffix used by the secondary row; the
        family color is looked up against the base name so both rows
        share the same color.
        """
        if bad:
            return f"{RED}{name}: {value}{ver}{RESET}"
        base = name.removesuffix(" resolved")
        color = label_color.get(base, YELLOW)
        return f"{color}{name}:{RESET} {value}{ver}"

    def _print_pair(name, r, show_not_found=True):
        """Print the row for ``r`` and, when its resolved path differs
        from the input, a second ``name resolved:`` row.

        The version line (``# Python 3.13.3``) is repeated on both rows
        — it describes the binary regardless of which spelling of its
        path the reader is looking at.
        """
        ver = f"  # {r.version}" if r.version else ""
        if r.display is None:
            if show_not_found:
                print_color(_format_row(name, "not found"), file=stdout)
            return
        print_color(_format_row(name, r.display, ver=ver, bad=r.bad), file=stdout)
        if r.differs:
            print_color(
                _format_row(f"{name} resolved", r.resolved_display, ver=ver, bad=r.bad),
                file=stdout,
            )

    print_color(f"{PURPLE}[Current xonsh session]{RESET}", file=stdout)
    _print_pair("xxonsh", session_xxonsh)
    _print_pair("xpython", session_xpython)
    _print_pair("xpip", session_xpip)

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
        _print_pair(name, r)

    env_rows = [
        (ev, val)
        for ev, val in (
            ("VIRTUAL_ENV", xc.get_env_virtual_env()),
            ("CONDA_DEFAULT_ENV", xc.get_env_conda_default_env()),
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
