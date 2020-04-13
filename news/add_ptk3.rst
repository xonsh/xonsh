**Added:**

* Support package prompt-toolkit V3 as well as V2 in prompt_toolkit shell.

**Changed:**

* $SHELL_TYPE "prompt_toolkit" with any suffix creates the "prompt_toolkit" shell, requires package prompt-toolkit >= 2.0
* Moved code from package xonsh.ptk2 to xonsh.ptk_shell (because it's the only one now); package xonsh.ptk2 redirects thence.

**Deprecated:**

* prompt-toolkit versions before 2.0

**Removed:**

* package xonsh.ptk

**Fixed:**

* <news item>

**Security:**

* <news item>
