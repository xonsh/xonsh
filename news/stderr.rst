**Added:**

* New ``$XONSH_STDERR_PREFIX`` and ``$XONSH_STDERR_POSTFIX`` environment
  variables allow the user to print a prompt-like string before and after
  all stderr that is seen. For example, say that you would like stderr
  to appear on a red background, you might set
  ``$XONSH_STDERR_PREFIX = "{BACKGROUND_RED}"`` and
  ``$XONSH_STDERR_PREFIX = "{NO_COLOR}"``.
* New ``xonsh.pyghooks.XonshTerminal256Formatter`` class patches
  the pygments formatter to understand xonsh color token semantics.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
