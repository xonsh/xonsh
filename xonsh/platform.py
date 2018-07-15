"""Module for platform-specific constants and implementations, as well as
compatibility layers to make use of the 'best' implementation available
on a platform.
"""
import os
import sys
import ctypes
import signal
import pathlib
import builtins
import platform
import functools
import subprocess
import collections
import importlib.util

from xonsh.lazyasd import LazyBool, lazyobject, lazybool
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
ON_DARWIN = LazyBool(lambda: platform.system() == 'Darwin',
                     globals(), 'ON_DARWIN')
"""``True`` if executed on a Darwin platform, else ``False``. """
ON_LINUX = LazyBool(lambda: platform.system() == 'Linux',
                    globals(), 'ON_LINUX')
"""``True`` if executed on a Linux platform, else ``False``. """
ON_WINDOWS = LazyBool(lambda: platform.system() == 'Windows',
                      globals(), 'ON_WINDOWS')
"""``True`` if executed on a native Windows platform, else ``False``. """
ON_CYGWIN = LazyBool(lambda: sys.platform == 'cygwin', globals(), 'ON_CYGWIN')
"""``True`` if executed on a Cygwin Windows platform, else ``False``. """
ON_MSYS = LazyBool(lambda: sys.platform == 'msys', globals(), 'ON_MSYS')
"""``True`` if executed on a MSYS Windows platform, else ``False``. """
ON_POSIX = LazyBool(lambda: (os.name == 'posix'), globals(), 'ON_POSIX')
"""``True`` if executed on a POSIX-compliant platform, else ``False``. """
ON_FREEBSD = LazyBool(lambda: (sys.platform.startswith('freebsd')),
                      globals(), 'ON_FREEBSD')
"""``True`` if on a FreeBSD operating system, else ``False``."""
ON_NETBSD = LazyBool(lambda: (sys.platform.startswith('netbsd')),
                     globals(), 'ON_NETBSD')
"""``True`` if on a NetBSD operating system, else ``False``."""


@lazybool
def ON_BSD():
    """``True`` if on a BSD operating system, else ``False``."""
    return bool(ON_FREEBSD) or bool(ON_NETBSD)


@lazybool
def ON_BEOS():
    """True if we are on BeOS or Haiku."""
    return sys.platform == 'beos5' or sys.platform == 'haiku1'


#
# Python & packages
#

PYTHON_VERSION_INFO = sys.version_info[:3]
""" Version of Python interpreter as three-value tuple. """


@lazyobject
def PYTHON_VERSION_INFO_BYTES():
    """The python version info tuple in a canonical bytes form."""
    return '.'.join(map(str, sys.version_info)).encode()


ON_ANACONDA = LazyBool(
    lambda: any(s in sys.version for s in {'Anaconda', 'Continuum', 'conda-forge'}),
    globals(), 'ON_ANACONDA')
""" ``True`` if executed in an Anaconda instance, else ``False``. """
CAN_RESIZE_WINDOW = LazyBool(lambda: hasattr(signal, 'SIGWINCH'),
                             globals(), 'CAN_RESIZE_WINDOW')
"""``True`` if we can resize terminal window, as provided by the presense of
signal.SIGWINCH, else ``False``.
"""


@lazybool
def HAS_PYGMENTS():
    """``True`` if `pygments` is available, else ``False``."""
    spec = importlib.util.find_spec('pygments')
    return (spec is not None)


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
def has_prompt_toolkit():
    """Tests if the `prompt_toolkit` is available."""
    spec = importlib.util.find_spec('prompt_toolkit')
    return (spec is not None)


@functools.lru_cache(1)
def ptk_version():
    """Returns `prompt_toolkit.__version__` if available, else ``None``."""
    if has_prompt_toolkit():
        import prompt_toolkit
        return getattr(prompt_toolkit, '__version__', '<0.57')
    else:
        return None


@functools.lru_cache(1)
def ptk_version_info():
    """ Returns `prompt_toolkit`'s version as tuple of integers. """
    if has_prompt_toolkit():
        return tuple(int(x) for x in ptk_version().strip('<>+-=.').split('.'))
    else:
        return None


@functools.lru_cache(1)
def ptk_above_min_supported():
    minimum_required_ptk_version = (1, 0)
    return ptk_version_info()[:2] >= minimum_required_ptk_version


@functools.lru_cache(1)
def ptk_shell_type():
    """Returns the prompt_toolkit shell type based on the installed version."""
    if ptk_version_info()[:2] < (2, 0):
        return 'prompt_toolkit1'
    else:
        return 'prompt_toolkit2'


@functools.lru_cache(1)
def ptk_below_max_supported():
    ptk_max_version_cutoff = (2, 0)
    return ptk_version_info()[:2] < ptk_max_version_cutoff


@functools.lru_cache(1)
def best_shell_type():
    if ON_WINDOWS or has_prompt_toolkit():
        return 'prompt_toolkit'
    else:
        return 'readline'


@functools.lru_cache(1)
def is_readline_available():
    """Checks if readline is available to import."""
    spec = importlib.util.find_spec('readline')
    return (spec is not None)


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
    if not path.startswith('~'):
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
    githash_file = '{}/dev.githash'.format(install_base)
    if not os.path.exists(githash_file):
        return None, None
    sha = None
    date_ = None
    try:
        with open(githash_file) as f:
            sha, date_ = f.read().strip().split('|')
    except ValueError:
        pass
    return sha, date_


#
# Encoding
#

DEFAULT_ENCODING = sys.getdefaultencoding()
""" Default string encoding. """


if PYTHON_VERSION_INFO < (3, 5, 0):
    class DirEntry:
        def __init__(self, directory, name):
            self.__path__ = pathlib.Path(directory) / name
            self.name = name
            self.path = str(self.__path__)
            self.is_symlink = self.__path__.is_symlink

        def inode(self):
            return os.stat(self.path, follow_symlinks=False).st_ino

        def is_dir(self, *, follow_symlinks=True):
            if follow_symlinks:
                return self.__path__.is_dir()
            else:
                return not self.__path__.is_symlink() \
                    and self.__path__.is_dir()

        def is_file(self, *, follow_symlinks=True):
            if follow_symlinks:
                return self.__path__.is_file()
            else:
                return not self.__path__.is_symlink() \
                    and self.__path__.is_file()

        def stat(self, *, follow_symlinks=True):
            return os.stat(self.path, follow_symlinks=follow_symlinks)

    def scandir(path):
        """ Compatibility layer for  `os.scandir` from Python 3.5+. """
        return (DirEntry(path, x) for x in os.listdir(path))
else:
    scandir = os.scandir


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
        elif PYTHON_VERSION_INFO < (3, 7, 0):
            ld = platform.linux_distribution()[0] or 'unknown'
        elif '-ARCH-' in platform.platform():
            ld = 'arch'  # that's the only one we need to know for now
        else:
            ld = 'unknown'
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
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             'SOFTWARE\\GitForWindows')
        gfwp, _ = winreg.QueryValueEx(key, "InstallPath")
    except FileNotFoundError:
        gfwp = None
    return gfwp


@functools.lru_cache(1)
def windows_bash_command():
    """Determines the command for Bash on windows."""
    # Check that bash is on path otherwise try the default directory
    # used by Git for windows
    wbc = 'bash'
    cmd_cache = builtins.__xonsh_commands_cache__
    bash_on_path = cmd_cache.lazy_locate_binary('bash', ignore_alias=True)
    if bash_on_path:
        try:
            out = subprocess.check_output([bash_on_path, '--version'],
                                          stderr=subprocess.PIPE,
                                          universal_newlines=True)
        except subprocess.CalledProcessError:
            bash_works = False
        else:
            # Check if Bash is from the "Windows Subsystem for Linux" (WSL)
            # which can't be used by xonsh foreign-shell/completer
            bash_works = out and 'pc-linux-gnu' not in out.splitlines()[0]

        if bash_works:
            wbc = bash_on_path
        else:
            gfwp = git_for_windows_path()
            if gfwp:
                bashcmd = os.path.join(gfwp, 'bin\\bash.exe')
                if os.path.isfile(bashcmd):
                    wbc = bashcmd
    return wbc

#
# Environment variables defaults
#

if ON_WINDOWS:
    class OSEnvironCasePreserving(collections.MutableMapping):
        """ Case-preserving wrapper for os.environ on Windows.
            It uses nt.environ to get the correct cased keys on
            initialization. It also preserves the case of any variables
            add after initialization.
        """
        def __init__(self):
            import nt
            self._upperkeys = dict((k.upper(), k) for k in nt.environ)

        def _sync(self):
            """ Ensure that the case sensitive map of the keys are
                in sync with os.environ
            """
            envkeys = set(os.environ.keys())
            for key in envkeys.difference(self._upperkeys):
                self._upperkeys[key] = key.upper()
            for key in set(self._upperkeys).difference(envkeys):
                del self._upperkeys[key]

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


@functools.lru_cache(1)
def bash_command():
    """Determines the command for Bash on the current platform."""
    if ON_WINDOWS:
        bc = windows_bash_command()
    else:
        bc = 'bash'
    return bc


@lazyobject
def BASH_COMPLETIONS_DEFAULT():
    """A possibly empty tuple with default paths to Bash completions known for
    the current platform.
    """
    if ON_LINUX or ON_CYGWIN or ON_MSYS:
        bcd = ('/usr/share/bash-completion/bash_completion', )
    elif ON_DARWIN:
        bcd = ('/usr/local/share/bash-completion/bash_completion',  # v2.x
               '/usr/local/etc/bash_completion')  # v1.x
    elif ON_WINDOWS and git_for_windows_path():
        bcd = (os.path.join(git_for_windows_path(),
                            'usr\\share\\bash-completion\\bash_completion'),
               os.path.join(git_for_windows_path(),
                            'mingw64\\share\\git\\completion\\'
                            'git-completion.bash'))
    else:
        bcd = ()
    return bcd


@lazyobject
def PATH_DEFAULT():
    if ON_LINUX or ON_CYGWIN or ON_MSYS:
        if linux_distro() == 'arch':
            pd = ('/usr/local/sbin',
                  '/usr/local/bin', '/usr/bin', '/usr/bin/site_perl',
                  '/usr/bin/vendor_perl', '/usr/bin/core_perl')
        else:
            pd = (os.path.expanduser('~/bin'), '/usr/local/sbin',
                  '/usr/local/bin', '/usr/sbin', '/usr/bin', '/sbin', '/bin',
                  '/usr/games', '/usr/local/games')
    elif ON_DARWIN:
        pd = ('/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin')
    elif ON_WINDOWS:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
        pd = tuple(winreg.QueryValueEx(key, 'Path')[0].split(os.pathsep))
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
    elif ON_CYGWIN:
        libc = ctypes.CDLL('cygwin1.dll')
    elif ON_MSYS:
        libc = ctypes.CDLL('msys-2.0.dll')
    elif ON_BSD:
        try:
            libc = ctypes.CDLL('libc.so')
        except AttributeError:
            libc = None
        except OSError:
            # OS X; can't use ctypes.util.find_library because that creates
            # a new process on Linux, which is undesirable.
            try:
                libc = ctypes.CDLL('libc.dylib')
            except OSError:
                libc = None
    elif ON_POSIX:
        try:
            libc = ctypes.CDLL('libc.so')
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
                libc = ctypes.CDLL('libc.so.6')
            except OSError:
                libc = None
        if not hasattr(libc, 'sysinfo'):
            # Not Linux.
            libc = None
    elif ON_WINDOWS:
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            libc = ctypes.windll.kernel32
        else:
            try:
                # Windows CE uses the cdecl calling convention.
                libc = ctypes.CDLL('coredll.lib')
            except (AttributeError, OSError):
                libc = None
    elif ON_BEOS:
        libc = ctypes.CDLL('libroot.so')
    else:
        libc = None
    return libc
