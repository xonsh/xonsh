**Added:**

* <news item>

**Changed:**

* Remove p-string prefix from partial string used in ``xonsh.completers._path_from_partial_string``, such that ``ast.literal_eval`` does not raise ``SyntaxError``.
* Strip leading ``p`` from quote used by ``xonsh.completers.path_path_from_partial_string`` to obtain the start of the path. This allows path completion to work as before, but preserves the leading ``p`` of the path literal already present on the command line.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
