**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed an issue with ``openpty()`` returning non-unix line endings in its buffer.
  This was causing git and ssh to fail when xonsh was used as the login shell on the
  server. See https://mail.python.org/pipermail/python-list/2013-June/650460.html for
  more details.

**Security:** None
