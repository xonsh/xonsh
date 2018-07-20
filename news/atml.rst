**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue with multiline string inside of ``@(expr)`` in
  unwrapped subprocesses. For example, the following now works::

    echo @("""hello
    mom""")

**Security:** None
