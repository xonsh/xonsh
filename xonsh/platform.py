""" Module for platform-specific constants and implementations, as well as
    compatibility layers to make use of the 'best' implementation available
    on a platform.
"""

from functools import lru_cache
import os
import platform
import sys

try:
    import distro
except ImportError:
    distro = None
except:
    raise


# do not import any xonsh-modules here to avoid circular dependencies


#
# OS
#

ON_DARWIN = platform.system() == 'Darwin'
""" ``True`` if executed on a Darwin platform, else ``False``. """
ON_LINUX = platform.system() == 'Linux'
""" ``True`` if executed on a Linux platform, else ``False``. """
ON_WINDOWS = platform.system() == 'Windows'
""" ``True`` if executed on a native Windows platform, else ``False``. """
ON_CYGWIN = sys.platform == 'cygwin'
""" ``True`` if executed on a Cygwin Windows platform, else ``False``. """
ON_POSIX = (os.name == 'posix')
""" ``True`` if executed on a POSIX-compliant platform, else ``False``. """



#
# Python & packages
#

PYTHON_VERSION_INFO = sys.version_info[:3]
""" Version of Python interpreter as three-value tuple. """
ON_ANACONDA = any(s in sys.version for s in {'Anaconda', 'Continuum'})
""" ``True`` if executed in an Anaconda instance, else ``False``. """


HAS_PYGMENTS = False
""" ``True`` if `pygments` is available, else ``False``. """
PYGMENTS_VERSION = None
""" `pygments.__version__` version if available, else ``Ǹone``. """

try:
    import pygments
except ImportError:
    pass
except:
    raise
else:
    HAS_PYGMENTS, PYGMENTS_VERSION = True, pygments.__version__


@lru_cache(1)
def has_prompt_toolkit():
    """ Tests if the `prompt_toolkit` is available. """
    try:
        import prompt_toolkit
    except ImportError:
        return False
    except:
        raise
    else:
        return True


@lru_cache(1)
def ptk_version():
    """ Returns `prompt_toolkit.__version__` if available, else ``None``. """
    if has_prompt_toolkit():
        import prompt_toolkit
        return getattr(prompt_toolkit, '__version__', '<0.57')
    else:
        return None


@lru_cache(1)
def ptk_version_info():
    """ Returns `prompt_toolkit`'s version as tuple of integers. """
    if has_prompt_toolkit():
        return tuple(int(x) for x in ptk_version().strip('<>+-=.').split('.'))
    else:
        return None


@lru_cache(1)
def best_shell_type():
    if ON_WINDOWS or has_prompt_toolkit():
        return 'prompt_toolkit'
    else:
        return 'readline'


@lru_cache(1)
def is_readline_available():
    """Checks if readline is available to import."""
    try:
        import readline
    except:  # pyreadline will sometimes fail in strange ways
        return False
    else:
        return True
#
# Encoding
#

DEFAULT_ENCODING = sys.getdefaultencoding()
""" Default string encoding. """


if PYTHON_VERSION_INFO < (3, 5, 0):
    from pathlib import Path

    class DirEntry:
        def __init__(self, directory, name):
            self.__path__ = Path(directory) / name
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

LINUX_DISTRO = None
""" The id of the Linux distribution running on, possibly 'unknown'.
    ``Ǹone`` on non-Linux platforms.
"""


if ON_LINUX:
    if distro:
        LINUX_DISTRO = distro.id()
    elif PYTHON_VERSION_INFO < (3, 7, 0):
        LINUX_DISTRO = platform.linux_distribution()[0] or 'unknown'
    elif '-ARCH-' in platform.platform():
        LINUX_DISTRO = 'arch'  # that's the only one we need to know for now
    else:
        LINUX_DISTRO = 'unknown'


#
# Windows
#

if ON_WINDOWS:
    try:
        import win_unicode_console
    except ImportError:
        win_unicode_console = None
else:
    win_unicode_console = None

    
if ON_WINDOWS:
    import winreg
    try: 
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\GitForWindows')
        GIT_FOR_WINDOWS_PATH, type = winreg.QueryValueEx(key, "InstallPath")
    except FileNotFoundError:    
        GIT_FOR_WINDOWS_PATH = None



if ON_WINDOWS:
    # Check that bash in on path otherwise try the default bin directory 
    # used by Git for windows
    import subprocess
    WINDOWS_BASH_COMMAND = 'bash'
    try: 
        subprocess.check_call([WINDOWS_BASH_COMMAND,'--version'])
    except FileNotFoundError:
        if GIT_FOR_WINDOWS_PATH: 
            bashcmd = os.path.join(GIT_FOR_WINDOWS_PATH, 'bin\\bash.exe')
            if os.path.isfile(bashcmd):
                WINDOWS_BASH_COMMAND = bashcmd

            
#
# Bash completions defaults
#

BASH_COMPLETIONS_DEFAULT = ()
""" A possibly empty tuple with default paths to Bash completions known for
    the current platform.
"""

if LINUX_DISTRO == 'arch':
    BASH_COMPLETIONS_DEFAULT = (
        '/etc/bash_completion',
        '/usr/share/bash-completion/completions')
elif ON_LINUX or ON_CYGWIN:
    BASH_COMPLETIONS_DEFAULT = (
        '/usr/share/bash-completion',
        '/usr/share/bash-completion/completions')
elif ON_DARWIN:
    BASH_COMPLETIONS_DEFAULT = (
        '/usr/local/etc/bash_completion',
        '/opt/local/etc/profile.d/bash_completion.sh')
elif ON_WINDOWS and GIT_FOR_WINDOWS_PATH:
    BASH_COMPLETIONS_DEFAULT = (
        os.path.join(GIT_FOR_WINDOWS_PATH, 'usr\\share\\bash-completion'),
        os.path.join(GIT_FOR_WINDOWS_PATH, 'usr\\share\\bash-completion\\completions'),
        os.path.join(GIT_FOR_WINDOWS_PATH, 'mingw64\\share\\git\\completion\\git-completion.bash'))

        
#
# All constants as a dict
#

PLATFORM_INFO = {name: obj for name, obj in globals().items()
                 if name.isupper()}
""" The constants of this module as dictionary. """
