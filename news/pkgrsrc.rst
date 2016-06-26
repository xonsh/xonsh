**Added:**

* New ``xonsh.bg_pkg_resources`` module for loading the ``pkg_resources``
  module in a background thread.

**Changed:**

* Sped up loading of pygments by ~100x by loading ``pkg_resources`` in
  background.
* Sped up loading of prompt-toolkit by ~2x-3x by loading ``pkg_resources``
  in background.

**Deprecated:** None

**Removed:** None

**Fixed:**

* Minor amalgamate bug with ``import pkg.mod`` amalgamated imports.

**Security:** None
