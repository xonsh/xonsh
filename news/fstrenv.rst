**Added:**

* <news item>

**Changed:**

* Now there is only a single instance of ``string.Formatter()`` in the
  code base, which is called ``xonsh.tools.FORMATTER``.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* f-strings (``f"{expr}"``) are now fully capable of executing xonsh expressions.
  The one exception to this is that ``![cmd]`` and ``!(cmd)`` do work because
  the ``!`` character interferes with Python string formatting. If you need to
  run subprocesses inside of f-strings, use ``$[cmd]`` and ``$(cmd)`` instead.

**Security:**

* <news item>
