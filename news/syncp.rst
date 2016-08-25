**Added:** None

**Changed:**

* ``yacc_debug=True`` now load the parser on the same thread that the
  Parser instance is created. ``setup.py`` now uses this synchronous
  form as it was causing the parser table to be missed by some package
  managers.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
