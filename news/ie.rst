**Added:**

* New events for hooking into the Python import process are now available.
  You can now provide a handler for:

  - ``on_import_pre_find_spec``
  - ``on_import_post_find_spec``
  - ``on_import_pre_create_module``
  - ``on_import_post_create_module``
  - ``on_import_pre_exec_module``
  - ``on_import_post_exec_module``

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* The ``mpl`` xontrib has been updated to improve matplotlib
  handling. If ``xontrib load mpl`` is run before matplotlib
  is imported and xonsh is in ineteractive mode, matplotlib
  will automatically enter interactive mode as well. Additionally,
  ``pyplot.show()`` is patched in interactive mode to be non-blocking.
  If a non-blocking show fails to draw the figre for some reason,
  a regular blocking version is called.

**Security:** None
