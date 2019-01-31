**Added:**

* Rendering of ``{env_name}`` in ``$PROMPT`` is now suppressed if
  the ``$VIRTUAL_ENV_DISABLE_PROMPT`` environment variable is
  defined and truthy.
* Rendering of ``{env_name}`` in ``$PROMPT`` is now overridden by
  the value of ``str($VIRTUAL_ENV_PROMPT)`` if that environment variable
  is defined and ``not None``. ``$VIRTUAL_ENV_DISABLE_PROMPT`` takes precedence
  over ``$VIRTUAL_ENV_PROMPT``.

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
