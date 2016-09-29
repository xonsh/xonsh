**Added:** None

**Changed:**

* moved prompt formatting specific functions from ``xonsh.environ``
  to ``xonsh.prompt.base``

**Deprecated:** None

**Removed:** None

**Fixed:**

* non string type value in $FORMATTER_DICT turning prompt ugly
* whole prompt turning useless when one formatting function raises an exception

**Security:** None
