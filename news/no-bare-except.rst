**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Bare ``except:`` was replaced with ``except Exception`` to prevent
  accidentally catching utility exceptions such as KeyboardInterrupt, which
  caused unexpected problems like printing out the raw $PROMPT string.

**Security:** None
