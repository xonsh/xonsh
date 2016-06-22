.. _xonsh_platform:

Platform-specific constants and implementations (``xonsh.platform``)
====================================================================

.. automodule:: xonsh.platform
    :members:
    :undoc-members:


.. py:function:: scandir

   This is either `os.scandir` on Python 3.5+ or a function providing a
   compatibility layer for it.
   It is recommended for iterations over directory entries at a significantly
   higher speed than `os.listdir` on Python 3.5+. It also caches properties
   that are commonly used for filtering.

   :param str path: The path to scan for entries.
   :return: A generator yielding `DirEntry` instances.

