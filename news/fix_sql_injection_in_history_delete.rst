**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* The `history delete` action on the sqlite backend used to
  pass matched history lines to a SQL statement without sanitization.
  This could lead to unexpected SQL being run on the history database.
  This is now fixed. Security risk: low.
