**Added:**

* New tools in ``xonsh.lazyasd`` module for loading modules in background
  threads.

**Changed:**

* Sped up loading of pygments by ~100x by loading ``pkg_resources`` in
  background.
* Sped up loading of prompt-toolkit by ~2x-3x by loading ``pkg_resources``
  in background.
* ``setup.py`` will no longer git checkout to replace the version number.
  Now it simply stores and reuses the original version line.

**Deprecated:** None

**Removed:** None

**Fixed:**

* Minor amalgamate bug with ``import pkg.mod`` amalgamated imports.

**Security:** None
