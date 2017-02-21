**Added:**

* The lexer has a new ``split()`` method which splits strings
  according to xonsh's rules for whitespace and quotes.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* The ``@$(cmd)`` operator now correctly splits strings according to
  xonsh semantics, rather than just on whitespace using ``str.split()``.

**Security:** None
