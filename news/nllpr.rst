**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue with pygments-cache not properly generating a cache the first
  time when using prompt-toolkit. This was due to a lingering lazy import
  of ``pkg_resources`` that has been removed.

**Security:** None
