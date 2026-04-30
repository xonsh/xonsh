"""Module for platform-specific constants and implementations, as well as
compatibility layers to make use of the 'best' implementation available
on a platform.
"""

import collections.abc as cabc
import ctypes  # noqa
import functools
import importlib.util
import os
import pathlib
import platform
import signal
import subprocess
import sys
from pathlib import Path

from xonsh.lib.lazyasd import LazyBool, lazybool, lazyobject

# do not import any xonsh-modules here to avoid circular dependencies

FD_STDIN = 0
FD_STDOUT = 1
FD_STDERR = 2


@lazyobject
def distro():
    try:
        import distro as d
    except ImportError:
        d = None
    except Exception:
        raise
    return d


#
# OS
#
ON_DARWIN = LazyBool(lambda: platform.system() == "Darwin", globals(), "ON_DARWIN")
"""``True`` if executed on a Darwin platform, else ``False``. """
ON_LINUX = LazyBool(lambda: platform.system() == "Linux", globals(), "ON_LINUX")
"""``True`` if executed on a Linux platform, else ``False``. """
ON_WINDOWS = LazyBool(lambda: platform.system() == "Windows", globals(), "ON_WINDOWS")
"""``True`` if executed on a native Windows platform, else ``False``. """
ON_CYGWIN = LazyBool(lambda: sys.platform == "cygwin", globals(), "ON_CYGWIN")
"""``True`` if executed on a Cygwin Windows platform, else ``False``. """
ON_MSYS = LazyBool(lambda: sys.platform == "msys", globals(), "ON_MSYS")
"""``True`` if executed on a MSYS Windows platform, else ``False``. """
ON_POSIX = LazyBool(lambda: os.name == "posix", globals(), "ON_POSIX")
"""``True`` if executed on a POSIX-compliant platform, else ``False``. """
ON_FREEBSD = LazyBool(
    lambda: sys.platform.startswith("freebsd"), globals(), "ON_FREEBSD"
)
"""``True`` if on a FreeBSD operating system, else ``False``."""
ON_DRAGONFLY = LazyBool(
    lambda: sys.platform.startswith("dragonfly"), globals(), "ON_DRAGONFLY"
)
"""``True`` if on a DragonFly BSD operating system, else ``False``."""
ON_NETBSD = LazyBool(lambda: sys.platform.startswith("netbsd"), globals(), "ON_NETBSD")
"""``True`` if on a NetBSD operating system, else ``False``."""
ON_OPENBSD = LazyBool(
    lambda: sys.platform.startswith("openbsd"), globals(), "ON_OPENBSD"
)
"""``True`` if on a OpenBSD operating system, else ``False``."""
IN_APPIMAGE = LazyBool(
    lambda: "APPIMAGE" in os.environ and "APPDIR" in os.environ,
    globals(),
    "IN_APPIMAGE",
)
"""``True`` if in AppImage, else ``False``."""
ON_TERMUX = LazyBool(
    lambda: "TERMUX_VERSION" in os.environ,
    globals(),
    "ON_TERMUX",
)
"""``True`` if running inside Termux on Android, else ``False``.

Detected via the ``TERMUX_VERSION`` environment variable, which Termux
sets unconditionally in every shell it spawns. Termux is a Linux-userland
emulator on Android, so ``ON_LINUX`` is also true there — ``ON_TERMUX``
is additive and identifies the Android sandbox specifically (no
``/usr``-style FHS, restricted ``tcsetpgrp``, no ``os.link``, etc.).
"""
IN_FLATPAK = LazyBool(
    lambda: "FLATPAK_ID" in os.environ,
    globals(),
    "IN_FLATPAK",
)
"""``True`` if in Flastpak, else ``False``."""


@lazybool
def ON_BSD():
    """``True`` if on a BSD operating system, else ``False``."""
    return bool(ON_FREEBSD) or bool(ON_NETBSD) or bool(ON_OPENBSD) or bool(ON_DRAGONFLY)


@lazybool
def ON_BEOS():
    """True if we are on BeOS or Haiku."""
    return sys.platform == "beos5" or sys.platform == "haiku1"


@lazybool
def ON_WSL():
    """True if we are on Windows Subsystem for Linux (WSL)"""
    return "microsoft" in platform.release()


@lazybool
def ON_WSL1():
    return bool(ON_WSL) and not bool(ON_WSL2)


@lazybool
def ON_WSL2():
    return bool(ON_WSL) and "WSL2" in platform.release()


#
# Python & packages
#

PYTHON_VERSION_INFO = sys.version_info[:3]
""" Version of Python interpreter as three-value tuple. """


@lazyobject
def PYTHON_VERSION_INFO_BYTES():
    """The python version info tuple in a canonical bytes form."""
    return ".".join(map(str, sys.version_info)).encode()


ON_ANACONDA = LazyBool(
    lambda: pathlib.Path(sys.prefix).joinpath("conda-meta").exists(),
    globals(),
    "ON_ANACONDA",
)
""" ``True`` if executed in an Anaconda instance, else ``False``. """
CAN_RESIZE_WINDOW = LazyBool(
    lambda: hasattr(signal, "SIGWINCH"), globals(), "CAN_RESIZE_WINDOW"
)
"""``True`` if we can resize terminal window, as provided by the presense of
signal.SIGWINCH, else ``False``.
"""


@lazybool
def HAS_PYGMENTS():
    """``True`` if `pygments` is available, else ``False``."""
    spec = importlib.util.find_spec("pygments")
    return spec is not None


@functools.lru_cache(1)
def pygments_version():
    """pygments.__version__ version if available, else None."""
    if HAS_PYGMENTS:
        import pygments

        v = pygments.__version__
    else:
        v = None
    return v


@functools.lru_cache(1)
def pygments_version_info():
    """Returns `pygments`'s version as tuple of integers."""
    if HAS_PYGMENTS:
        return tuple(int(x) for x in pygments_version().strip("<>+-=.").split("."))
    else:
        return None


@functools.lru_cache(1)
def has_prompt_toolkit():
    """Tests if the `prompt_toolkit` is available."""
    spec = importlib.util.find_spec("prompt_toolkit")
    return spec is not None


@functools.lru_cache(1)
def ptk_version():
    """Returns `prompt_toolkit.__version__` if available, else ``None``."""
    if has_prompt_toolkit():
        import prompt_toolkit

        return getattr(prompt_toolkit, "__version__", "<0.57")
    else:
        return None


@functools.lru_cache(1)
def ptk_version_info():
    """Returns `prompt_toolkit`'s version as tuple of integers."""
    if has_prompt_toolkit():
        return tuple(int(x) for x in ptk_version().strip("<>+-=.").split("."))
    else:
        return None


minimum_required_ptk_version = (2, 0, 0)
"""Minimum version of prompt-toolkit supported by Xonsh"""


@functools.lru_cache(1)
def ptk_above_min_supported():
    return ptk_version_info() and ptk_version_info() >= minimum_required_ptk_version


@functools.lru_cache(1)
def win_ansi_support():
    if ON_WINDOWS:
        try:
            from prompt_toolkit.utils import is_conemu_ansi, is_windows_vt100_supported
        except ImportError:
            return False
        return is_conemu_ansi() or is_windows_vt100_supported()
    else:
        return False


@functools.lru_cache(1)
def ptk_below_max_supported():
    ptk_max_version_cutoff = (99999, 0)  # currently, no limit.
    return ptk_version_info()[:2] < ptk_max_version_cutoff


@functools.lru_cache(1)
def best_shell_type():
    from xonsh.built_ins import XSH

    if XSH.env.get("TERM", "") == "dumb":
        return "dumb"
    if has_prompt_toolkit():
        return "prompt_toolkit"
    return "readline"


@functools.lru_cache(1)
def is_readline_available():
    """Checks if readline is available to import."""
    spec = importlib.util.find_spec("readline")
    return spec is not None


@lazyobject
def seps():
    """String of all path separators."""
    s = os.path.sep
    if os.path.altsep is not None:
        s += os.path.altsep
    return s


def pathsplit(p):
    """This is a safe version of os.path.split(), which does not work on input
    without a drive.
    """
    n = len(p)
    if n == 0:
        # lazy object seps does not get initialized when n is zero
        return "", ""
    while n and p[n - 1] not in seps:
        n -= 1
    pre = p[:n]
    pre = pre.rstrip(seps) or pre
    post = p[n:]
    return pre, post


def pathbasename(p):
    """This is a safe version of os.path.basename(), which does not work on
    input without a drive.  This version does.
    """
    return pathsplit(p)[-1]


@lazyobject
def expanduser():
    """Dispatches to the correct platform-dependent expanduser() function."""
    if ON_WINDOWS:
        return windows_expanduser
    else:
        return os.path.expanduser


def windows_expanduser(path):
    """A Windows-specific expanduser() function for xonsh. This is needed
    since os.path.expanduser() does not check on Windows if the user actually
    exists. This restricts expanding the '~' if it is not followed by a
    separator. That is only '~/' and '~\' are expanded.
    """
    path = str(path)
    if not path.startswith("~"):
        return path
    elif len(path) < 2 or path[1] in seps:
        return os.path.expanduser(path)
    else:
        return path


# termios tc(get|set)attr indexes.
IFLAG = 0
OFLAG = 1
CFLAG = 2
LFLAG = 3
ISPEED = 4
OSPEED = 5
CC = 6


#
# Dev release info
#


@functools.lru_cache(1)
def githash():
    """Returns a tuple contains two strings: the hash and the date."""
    install_base = os.path.dirname(__file__)
    githash_file = f"{install_base}/dev.githash"
    if not os.path.exists(githash_file):
        return None, None
    sha = None
    date_ = None
    try:
        with open(githash_file) as f:
            sha, date_ = f.read().strip().split("|")
    except ValueError:
        pass
    return sha, date_


#
# Encoding
#

DEFAULT_ENCODING = sys.getdefaultencoding()
""" Default string encoding. """


#
# Linux distro
#


@functools.lru_cache(1)
def linux_distro():
    """The id of the Linux distribution running on, possibly 'unknown'.
    None on non-Linux platforms.
    """
    if ON_LINUX:
        if distro:
            ld = distro.id()
        elif "-ARCH-" in platform.platform():
            ld = "arch"  # that's the only one we need to know for now
        else:
            ld = "unknown"
    else:
        ld = None
    return ld


#
# Windows
#


@functools.lru_cache(1)
def git_for_windows_path():
    """Returns the path to git for windows, if available and None otherwise."""
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\GitForWindows")
        gfwp, _ = winreg.QueryValueEx(key, "InstallPath")
    except FileNotFoundError:
        gfwp = None
    return gfwp


@functools.lru_cache(1)
def windows_bash_command():
    """Determines the command for Bash on windows."""
    # Check that bash is on path otherwise try the default directory
    # used by Git for windows
    from xonsh.built_ins import XSH

    wbc = "bash"
    cmd_cache = XSH.commands_cache
    bash_on_path = cmd_cache.lazy_locate_binary("bash", ignore_alias=True)
    if bash_on_path:
        try:
            out = subprocess.check_output(
                [bash_on_path, "--version"],
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError:
            bash_works = False
        else:
            # Check if Bash is from the "Windows Subsystem for Linux" (WSL)
            # which can't be used by xonsh foreign-shell/completer
            bash_works = out and "pc-linux-gnu" not in out.splitlines()[0]

        if bash_works:
            wbc = bash_on_path
        else:
            gfwp = git_for_windows_path()
            if gfwp:
                bashcmd = os.path.join(gfwp, "bin\\bash.exe")
                if os.path.isfile(bashcmd):
                    wbc = bashcmd
    return wbc


#
# Environment variables defaults
#

if ON_WINDOWS:

    class OSEnvironCasePreserving(cabc.MutableMapping):
        """Case-preserving wrapper for os.environ on Windows.
        It uses nt.environ to get the correct cased keys on
        initialization. It also preserves the case of any variables
        add after initialization.
        """

        def __init__(self):
            import nt

            self._upperkeys = {k.upper(): k for k in nt.environ}

        def _sync(self):
            """Ensure that the case sensitive map of the keys are
            in sync with os.environ
            """
            envkeys = {k.upper(): k for k in os.environ.keys()}
            for ukey in set(envkeys).difference(self._upperkeys):
                self._upperkeys[ukey] = envkeys[ukey]
            for ukey in set(self._upperkeys).difference(envkeys):
                del self._upperkeys[ukey]

        def __contains__(self, k):
            self._sync()
            return k.upper() in self._upperkeys

        def __len__(self):
            self._sync()
            return len(self._upperkeys)

        def __iter__(self):
            self._sync()
            return iter(self._upperkeys.values())

        def __getitem__(self, k):
            self._sync()
            return os.environ[k]

        def __setitem__(self, k, v):
            self._sync()
            self._upperkeys[k.upper()] = k
            os.environ[k] = v

        def __delitem__(self, k):
            self._sync()
            if k.upper() in self._upperkeys:
                del self._upperkeys[k.upper()]
                del os.environ[k]

        def getkey_actual_case(self, k):
            self._sync()
            return self._upperkeys.get(k.upper())


@lazyobject
def os_environ():
    """This dispatches to the correct, case-sensitive version of os.environ.
    This is mainly a problem for Windows. See #2024 for more details.
    This can probably go away once support for Python v3.5 or v3.6 is
    dropped.
    """
    if ON_WINDOWS:
        return OSEnvironCasePreserving()
    else:
        return os.environ


def bash_command():
    """Determines the command for Bash on the current platform."""
    if (bc := os.getenv("XONSH_BASH_PATH_OVERRIDE", None)) is not None:
        bc = str(bc)  # for pathlib Paths
    elif ON_WINDOWS:
        bc = windows_bash_command()
    else:
        bc = "bash"
    return bc


@lazyobject
def BASH_COMPLETIONS_DEFAULT():
    """A possibly empty tuple with default paths to Bash completions known for
    the current platform.

    The bridge picks the first existing file from this list, so order
    doesn't affect coverage — only which framework gets sourced when
    several are installed side by side. Distro/package-manager prefixes
    are listed alongside the standard FHS path so users don't have to
    extend ``$BASH_COMPLETIONS`` manually after installing
    bash-completion via Homebrew, MacPorts, Linuxbrew, Nix, etc.
    """
    if ON_LINUX or ON_CYGWIN or ON_MSYS:
        bcd = (
            "/usr/share/bash-completion/bash_completion",  # FHS, all major distros
            "/home/linuxbrew/.linuxbrew/share/bash-completion/bash_completion",  # Linuxbrew
            "/run/current-system/sw/share/bash-completion/bash_completion",  # NixOS
            os.path.expanduser(  # nix-env single-user profile
                "~/.nix-profile/share/bash-completion/bash_completion"
            ),
        )
    elif ON_DARWIN:
        bcd = (
            # Homebrew, Intel
            "/usr/local/share/bash-completion/bash_completion",  # v2.x
            "/usr/local/etc/bash_completion",  # v1.x
            # Homebrew, Apple Silicon
            "/opt/homebrew/share/bash-completion/bash_completion",  # v2.x
            "/opt/homebrew/etc/bash_completion",  # v1.x
            # MacPorts
            "/opt/local/share/bash-completion/bash_completion",  # v2.x
            "/opt/local/etc/bash_completion",  # v1.x
            # Nix (nix-darwin shared and per-user profiles)
            "/run/current-system/sw/share/bash-completion/bash_completion",
            os.path.expanduser("~/.nix-profile/share/bash-completion/bash_completion"),
        )
    elif ON_WINDOWS and git_for_windows_path():
        bcd = (
            os.path.join(
                git_for_windows_path(), "usr\\share\\bash-completion\\bash_completion"
            ),
            os.path.join(
                git_for_windows_path(),
                "mingw64\\share\\git\\completion\\git-completion.bash",
            ),
        )
    elif ON_BSD:
        # FreeBSD/DragonFly install bash-completion via ports/pkg under
        # /usr/local; NetBSD/OpenBSD use the same prefix via pkgsrc, plus
        # NetBSD's /usr/pkg fallback.
        # Note: bash-completion 2.17 (FreeBSD 16+) also ships a
        # ``bash_completion.sh`` wrapper next to the library. We do not
        # list it because it bails out in non-interactive bash
        # (``[[ "$-" =~ i ]] || return 0``) — and xonsh's bridge runs
        # bash with ``-c``, i.e. non-interactively. The wrapper would
        # silently no-op and produce empty completions; the library
        # file below works in either mode.
        bcd = (
            "/usr/local/share/bash-completion/bash_completion",  # v2.x library
            "/usr/local/etc/bash_completion",  # v1.x
            "/usr/pkg/share/bash-completion/bash_completion",  # pkgsrc
        )
    else:
        bcd = ()
    return bcd


@lazyobject
def PATH_DEFAULT():
    if ON_LINUX or ON_CYGWIN or ON_MSYS:
        if linux_distro() == "arch":
            pd = (
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/bin",
                "/usr/bin/site_perl",
                "/usr/bin/vendor_perl",
                "/usr/bin/core_perl",
            )
        else:
            pd = (
                os.path.expanduser("~/bin"),
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
                "/sbin",
                "/bin",
                "/usr/games",
                "/usr/local/games",
            )

            """
            On NixOS the coreutils bin path is versioned in /nix/store,
            so we need to locate something like: `/nix/store/<hash>-<coreutils>-<version>/bin`.
            """
            if Path("/nix").exists() and "PATH" in os.environ:
                path_list = os.environ["PATH"].split(os.pathsep)
                pd += tuple(
                    path
                    for path in path_list
                    if path.startswith("/nix") and path.endswith("/bin")
                )

    elif ON_DARWIN:
        pd = ("/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin")
    elif ON_BSD:
        # FreeBSD's /etc/login.conf default; also matches the layout NetBSD,
        # OpenBSD and DragonFly use, with /usr/local/{s,}bin coming from
        # ports / pkgsrc.
        pd = (
            "/sbin",
            "/bin",
            "/usr/sbin",
            "/usr/bin",
            "/usr/local/sbin",
            "/usr/local/bin",
            os.path.expanduser("~/bin"),
        )
    elif ON_WINDOWS:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
        pd = tuple(winreg.QueryValueEx(key, "Path")[0].split(os.pathsep))
    else:
        pd = ()
    return pd


#
# libc
#
@lazyobject
def LIBC():
    """The platform dependent libc implementation."""
    global ctypes
    if ON_DARWIN:
        import ctypes.util

        libc = ctypes.CDLL(ctypes.util.find_library("c"))
    elif ON_CYGWIN or ON_MSYS:
        # In MSYS2, sys.platform may report "cygwin" even though the
        # runtime library is msys-2.0.dll (not cygwin1.dll).  Try both.
        for _dll in ("msys-2.0.dll", "cygwin1.dll"):
            try:
                libc = ctypes.CDLL(_dll)
                break
            except OSError:
                continue
        else:
            libc = None
    elif ON_FREEBSD:
        try:
            libc = ctypes.CDLL("libc.so.7")
        except OSError:
            libc = None
    elif ON_BSD:
        try:
            libc = ctypes.CDLL("libc.so")
        except AttributeError:
            libc = None
        except OSError:
            # macOS; can't use ctypes.util.find_library because that creates
            # a new process on Linux, which is undesirable.
            try:
                libc = ctypes.CDLL("libc.dylib")
            except OSError:
                libc = None
    elif ON_POSIX:
        try:
            libc = ctypes.CDLL("libc.so")
        except AttributeError:
            libc = None
        except OSError:
            # Debian and derivatives do the wrong thing because /usr/lib/libc.so
            # is a GNU ld script rather than an ELF object. To get around this, we
            # have to be more specific.
            # We don't want to use ctypes.util.find_library because that creates a
            # new process on Linux. We also don't want to try too hard because at
            # this point we're already pretty sure this isn't Linux.
            try:
                libc = ctypes.CDLL("libc.so.6")
            except OSError:
                libc = None
        if not hasattr(libc, "sysinfo"):
            # Not Linux.
            libc = None
    elif ON_WINDOWS:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "kernel32"):
            libc = ctypes.windll.kernel32
        else:
            try:
                # Windows CE uses the cdecl calling convention.
                libc = ctypes.CDLL("coredll.lib")
            except (AttributeError, OSError):
                libc = None
    elif ON_BEOS:
        libc = ctypes.CDLL("libroot.so")
    else:
        libc = None
    return libc
