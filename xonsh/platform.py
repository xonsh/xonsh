"""Module for platform-specific constants and implementations, as well as
compatibility layers to make use of the 'best' implementation available
on a platform.
"""
import os
import sys
import pathlib
import platform
import functools
import subprocess
import importlib.util

from xonsh.lazyasd import LazyObject, LazyBool

def _distro():
    try:
        import distro as d
    except ImportError:
        d = None
    except:
        raise
    return d


distro = LazyObject(_distro, globals(), 'distro')
del _distro

# do not import any xonsh-modules here to avoid circular dependencies


#
# OS
#
ON_DARWIN = LazyBool(lambda: platform.system() == 'Darwin',
                     globals(), 'ON_DARWIN')
""" ``True`` if executed on a Darwin platform, else ``False``. """
ON_LINUX = LazyBool(lambda: platform.system() == 'Linux',
                    globals(), 'ON_LINUX')
""" ``True`` if executed on a Linux platform, else ``False``. """
ON_WINDOWS = LazyBool(lambda: platform.system() == 'Windows',
                      globals(), 'ON_WINDOWS')
""" ``True`` if executed on a native Windows platform, else ``False``. """
ON_CYGWIN = LazyBool(lambda: sys.platform == 'cygwin', globals(), 'ON_CYGWIN')
""" ``True`` if executed on a Cygwin Windows platform, else ``False``. """
ON_POSIX = LazyBool(lambda: (os.name == 'posix'), globals(), 'ON_POSIX')
""" ``True`` if executed on a POSIX-compliant platform, else ``False``. """


#
# Python & packages
#

PYTHON_VERSION_INFO = sys.version_info[:3]
""" Version of Python interpreter as three-value tuple. """
ON_ANACONDA = LazyBool(
    lambda: any(s in sys.version for s in {'Anaconda', 'Continuum'}),
    globals(), 'ON_ANACONDA')
""" ``True`` if executed in an Anaconda instance, else ``False``. """

def _has_pygments():
    spec = importlib.util.find_spec('pygments')
    return (spec is not None)


HAS_PYGMENTS = LazyBool(_has_pygments, globals(), 'HAS_PYGMENTS')
""" ``True`` if `pygments` is available, else ``False``. """
del _has_pygments


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
    """ Tests if the `prompt_toolkit` is available. """
    spec = importlib.util.find_spec('pygments')
    return (spec is not None)


@functools.lru_cache(1)
def ptk_version():
    """ Returns `prompt_toolkit.__version__` if available, else ``None``. """
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
def ptk_version_is_supported():
    minimum_required_ptk_version = (1, 0)
    return ptk_version_info()[:2] >= minimum_required_ptk_version


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
    """Determines teh command for Bash on windows."""
    import winreg
    # Check that bash is on path otherwise try the default directory
    # used by Git for windows
    wbc = 'bash'
    try:
        subprocess.check_call([wbc, '--version'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError):
        gfwp = git_for_windows_path()
        if gfwp:
            bashcmd = os.path.join(gfwp, 'bin\\bash.exe')
            if os.path.isfile(bashcmd):
                wbc = bashcmd
    return wbc

#
# Environment variables defaults
#

def _bcd():
    """A possibly empty tuple with default paths to Bash completions known for
    the current platform.
    """
    if ON_LINUX or ON_CYGWIN:
        if linux_distro() == 'arch':
            bcd = (
                '/usr/share/bash-completion/bash_completion',
                '/usr/share/bash-completion/completions')
        else:
            bcd = ('/usr/share/bash-completion',
                   '/usr/share/bash-completion/completions')
    elif ON_DARWIN:
        bcd = ('/usr/local/etc/bash_completion',
               '/opt/local/etc/profile.d/bash_completion.sh')
    elif ON_WINDOWS and git_for_windows_path():
        bcd = (os.path.join(git_for_windows_path(),
                    'usr\\share\\bash-completion'),
               os.path.join(git_for_windows_path(),
                    'usr\\share\\bash-completion\\completions'),
               os.path.join(git_for_windows_path(),
                     'mingw64\\share\\git\\completion\\git-completion.bash'))
    else:
        bcd = ()
    return bcd


BASH_COMPLETIONS_DEFAULT = LazyObject(_bcd, globals(),
                                      'BASH_COMPLETIONS_DEFAULT')
del _bcd


def _pd():
    if ON_LINUX or ON_CYGWIN:
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

PATH_DEFAULT = LazyObject(_pd, globals(), 'PATH_DEFAULT')
del _pd
