**Added:**

* New amalgamate tool collapses modules inside of a package into a single
  ``__amalgam__.py`` module. This tool glues together all of the code from the
  modules in a package, finds and removes intra-package imports, makes all
  non-package imports lazy, and adds hooks into the ``__init__.py``.
  This helps makes initial imports of modules fast and decreases startup time.
  Packages and sub-packages must be amalgamated separately.
* New lazy and self-destructive module ``xonsh.lazyasd`` adds a suite of
  classes for delayed creation of objects.

    - A ``LazyObject`` won't be created until it has an attribute accessed.
    - A ``LazyDict`` will load each value only when a key is accessed.
    - A ``LazyBool`` will only be created when ``__bool__()`` is called.

  Additionally, when fully loaded, the above objects will replace themselves
  by name in the context that they were handed, thus derefenceing themselves.
  This is useful for global variables that may be expensive to create,
  should only be created once, and may not be used in any particular session.
* New ``xon.sh`` script added for launching xonsh from a sh environment.
  This should be used if the normal ``xonsh`` script does not work for
  some reason.

**Changed:**

* ``$XONSH_DEBUG`` will now supress amalgamted imports. This usually needs to be
  set in the calling environment or prior to *any* xonsh imports.
* Restuctured ``xonsh.platform`` to be fully lazy.
* Restuctured ``xonsh.ansi_colors`` to be fully lazy.
* Ensured the ``pygments`` and ``xonsh.pyghooks`` are not imported until
  actually needed.
* Yacc parser is now loaded in a background thread.

**Deprecated:** None

**Removed:** None

* The ``'console_scripts'`` option to setuptools has been removed. It was found
  to cause slowdowns of over 150 ms on every startup.

**Fixed:** None

**Security:** None
