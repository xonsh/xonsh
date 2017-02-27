**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* On Windows, ``os.environ`` is case insensitive. This would potentially
  change the case of envrionment variables set into the environment.
  Xonsh now uses ``nt.envrion``, the case sensitive counterpart, to avoid
  these issues on Windows.

**Security:** None
