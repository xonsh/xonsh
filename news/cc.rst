**Added:**

* New ``pathsep_to_set()`` and ``set_to_pathsep()`` functions convert to/from
  ``os.pathsep`` separated strings to a set of strings.

**Changed:**

* ``CommandsCache`` is now a mapping from command names to a tuple of
  (executable locations, has alias flags). This enables faster lookup times.
* ``locate_bin()`` now uses the ``CommandsCache``, rather than scanning the
  ``$PATH`` itself.
* ``$PATHEXT`` is now a set, rather than a list.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
