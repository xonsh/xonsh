**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Properly throw ``SyntaxError`` when no kwargs are defined
  in a kwarg-only function. This used to throw a
  ``TypeError: 'NoneType' object is not iterable``.

**Security:** None
