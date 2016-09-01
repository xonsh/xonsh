**Added:** None

**Changed:**

* Context sensitive AST transformation now checks that all names in an
  expression are in scope. If they are, then Python mode is retained. However,
  if even one is missing, subprocess wrapping is attempted. Previously, only the
  left-most name was examined for being within scope.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
