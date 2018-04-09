**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Commands like ``git c`` would complete to ``git 'checkout '`` because git adds an extra space
  to the end of the completion, which was being captured in the completion. Xonsh now fixes the git issue
  while retaining all whitespace when there is other internal whitespace.

**Security:** None
