""" Module for platform-specific constants and implementations, as well as
    compatibility layers to make use of the 'best' implementation available
    on a platform. """

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
ON_LINUX = platform.system() == 'Linux'
ON_WINDOWS = platform.system() == 'Windows'

ON_POSIX = (os.name == 'posix')



#
# Python & packages
#

PYTHON_VERSION_INFO = sys.version_info[:3]
ON_ANACONDA = any(s in sys.version for s in {'Anaconda', 'Continuum'})

try:
    import pygments
except ImportError:
    HAS_PYGMENTS, PYGMENTS_VERSION = False, None
except:
    raise
else:
    HAS_PYGMENTS, PYGMENTS_VERSION = True, pygments.__version__


@lru_cache(1)
def has_prompt_toolkit():
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
    if has_prompt_toolkit():
        import prompt_toolkit
        return getattr(prompt_toolkit, '__version__', '<0.57')
    else:
        return None


@lru_cache(1)
def ptk_version_info():
    if has_prompt_toolkit():
        return tuple(int(x) for x in ptk_version().strip('<>+-=.').split('.'))
    else:
        return None


if ON_WINDOWS or has_prompt_toolkit():
    BEST_SHELL_TYPE = 'prompt_toolkit'
else:
    BEST_SHELL_TYPE = 'readline'


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


#
# Linux distro
#

if ON_LINUX:
    if distro:
        LINUX_DISTRO = distro.id()
    elif PYTHON_VERSION_INFO < (3, 7, 0):
        LINUX_DISTRO = platform.linux_distribution()[0] or 'unknown'
    elif '-ARCH-' in platform.platform():
        LINUX_DISTRO = 'arch'  # that's the only one we need to know for now
    else:
        LINUX_DISTRO = 'unknown'
else:
    LINUX_DISTRO = None


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


#
# Bash completions defaults
#

if LINUX_DISTRO == 'arch':
    BASH_COMPLETIONS_DEFAULT = (
        '/etc/bash_completion',
        '/usr/share/bash-completion/completions')
elif ON_LINUX:
    BASH_COMPLETIONS_DEFAULT = (
        '/usr/share/bash-completion',
        '/usr/share/bash-completion/completions')
elif ON_DARWIN:
    BASH_COMPLETIONS_DEFAULT = (
        '/usr/local/etc/bash_completion',
        '/opt/local/etc/profile.d/bash_completion.sh')
else:
    BASH_COMPLETIONS_DEFAULT = ()

#
# All constants as a dict
#

PLATFORM_INFO = {name: obj for name, obj in globals().items()
                 if name.isupper()}
