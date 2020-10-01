**Added:**

* Added ``_DIRS``,``_FILES``,``_FILE``, ``_DIR`` to registered env_path and path types.

**Changed:**

* ``$EXAMPLE_PATH.paths`` is now function that returns list of Path objects by default.
  And the ``type`` argument could be set to ``str`` to get list of strings -
  it's the same as ``list($EXAMPLE_PATH)``.
* ``str_to_path`` function returns the value without changes if it's not a ``str`` type
  to save environment variables that detected as path but not a path (e.g. ``$I_LIKE_PATH=True`` stay as ``True``)

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
