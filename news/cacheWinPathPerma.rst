**Added:**

* Color highlighting for partial commands (currently only commands in ``$XONSH_DIR_PERMA_CACHE`` and ``$XONSH_DIR_SESSION_CACHE`` are supported) via a new ``Token.Name.Cmdprefix`` token scope, default is white underlines

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* (a little bit) Slow input lag on Windows due to testing whether the typed text is an executable file (for color highlighting) by caching a list of files in user configured dirs (``$XONSH_DIR_PERMA_CACHE``) permanently (suitable for dirs like ``C:\Windows\System32`` that are very large, but do not change).

**Security:**

* <news item>
