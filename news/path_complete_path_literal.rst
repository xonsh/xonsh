**Added:**

* `_get_normalized_pstring_quote` returns a consistent set of prefixes, and the quote, for all path-string variants e.g. inputs `pr'` and `rp'` both produce the tuple `("pr", "'")`. This function is used by ``xonsh.completers.complete_path`` and ``xonsh.completers._path_from_partial_string``.

**Changed:**

* Remove `p`, `rp` and `pr` prefix from partial p-string used in ``xonsh.completers._path_from_partial_string``, such that ``ast.literal_eval`` does not raise ``SyntaxError``. `pr` and `rp` strings are now treated internally as raw strings, but the p-string quote is correctly returned.
* Increment the prefix length when the prefix input to ``xonsh.completers.complete_path`` is a p-string. This preserves the length of the prefix for path-string variants.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
