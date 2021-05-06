**Added:**

* In addition to reading single rc files at startup (``/etc/xonshrc``, ``~/.config/xonsh/rc.xsh``),
  xonsh now also supports rc.d-style config directories, from which all files are sourced. This is
  designed to support drop-in style configuration where you could, for example, have a common config
  file shared across multiple machines and a separate machine specific file.

  This is controlled by the environment variable ``XONSHRC_DIR``, which defaults to
  ``["/etc/xonsh/rc.d", "~/.config/xonsh/rc.d"]``. If those directories exist, then any ``xsh`` files
  contained within are sorted and then sourced.

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
