**Added:**

* <news item>

**Changed:**

* The ``path`` type in ``${...}.register`` was renamed to ``env_path`` as it should be and added
  new ``path`` type instead that represent ``pathlib.Path``. Now you can register typed environment
  variables that will be converted to ``Path``.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Fixed getting a typed registered environment variable when it was initialized before registering.

**Security:**

* <news item>
