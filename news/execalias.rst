**Added:**

* New ``xonsh.aliases.ExecAlias`` class enables multi-statement aliases.
* New ``xonsh.ast.isexpression()`` function will return a boolean of whether
  code is a simple xonsh expression or not.
* Added top-level ``run-tests.xsh`` script for safely running the test suite.

**Changed:**

* String aliases are no longer split with ``shlex.split()``, but instead use
  ``xonsh.lexer.Lexer.split()``.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
