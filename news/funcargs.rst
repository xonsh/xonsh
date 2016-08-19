**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Context senstitive AST transformer was not adding argument names to the
  local scope. This would then enable extraneous subprocess mode wrapping
  for expressions whose leftmost name was function argument. This has been
  fixed by properly adding the argument names to the scope.

**Security:** None
