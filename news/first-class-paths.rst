**Added:**

Since shells are all about paths, some syntactic sugar to make using
``pathlib.Path`` objects easy is added:

* p-strings: ``p'/foo/bar'`` is short for ``Path("/foo/bar")``
* p-backticks: the ``p`` modifier to a backticks search (``p`.*` ``) returns a
  list of ``Path`` objects instead of strings. This can be combined with the
  existing modifiers, eg ``pg`**` `` to use glob instead of regex. (This only
  applies in python mode).

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
