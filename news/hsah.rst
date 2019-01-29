**Added:**

* <news item>

**Changed:**

* Some minor ``history show`` efficiency improvements.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Fixed issue with recursive aliases not being passes all keyword arguments
  that are part of the callable alias spec. This allows commands like
  ``aliases['hsa'] = "history show all"; hsa | head`` to no longer fail
  with strange errors.

**Security:**

* <news item>
