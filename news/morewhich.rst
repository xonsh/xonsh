**Added:**

* Callable aliases may now take a final ``spec`` arguemnt, which is the
  cooresponding ``SubprocSpec`` instance.

**Changed:**

* The ``which`` alias no longer has a trailing newline if it is captured.
  This means that ``$(which cmd)`` will simply be the path to the command.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
