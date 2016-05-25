.. _xonsh_platform:

Platform-specific constants and implementations (``xonsh.platform``)
====================================================================

Functions
---------

.. automodule:: xonsh.platform
    :members: has_prompt_toolkit, is_readline_available, ptk_version,
              ptk_version_info

.. py:module:: xonsh.platform

.. py:function:: scandir

   This is either `os.scandir` on Python 3.5+ or a function providing a
   compatibility layer for it.
   It is recommended for iterations over directory entries at a significantly
   higher speed than `os.listdir` on Python 3.5+. It also caches properties
   that are commonly used for filtering.

   :param str path: The path to scan for entries.
   :return: A generator yielding `DirEntry` instances.


Constants
---------

.. autodata:: BASH_COMPLETIONS_DEFAULT
    :annotation:

.. autodata:: BEST_SHELL_TYPE
    :annotation:

.. autodata:: DEFAULT_ENCODING
    :annotation:

.. autodata:: HAS_PYGMENTS
    :annotation:

.. autodata:: LINUX_DISTRO
    :annotation:

.. autodata:: ON_ANACONDA
    :annotation:

.. autodata:: ON_DARWIN
    :annotation:

.. autodata:: ON_LINUX
    :annotation:

.. autodata:: ON_POSIX
    :annotation:

.. autodata:: ON_WINDOWS
    :annotation:

.. autodata:: PLATFORM_INFO
    :annotation:

.. autodata:: PYGMENTS_VERSION
    :annotation:

.. autodata:: PYTHON_VERSION_INFO
    :annotation:
