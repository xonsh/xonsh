**Added:**

* <news item>

**Changed:**

* The environment variables ``XONSHRC`` and ``XONSHRC_DIR`` are no longer updated by xonsh on
  startup according to which files were actually loaded. This caused problems if xonsh is called
  recursively, as the child shells would inherit the modified startup environment of the parent.
  These variables will now be left untouched, and the actual RC files loaded (according to those
  variables and command line arguments) can be seen in the output of ``xonfig``.

**Deprecated:**

* <news item>

**Removed:**

* The environment variable ``LOADED_RC_FILES`` is no longer set. It contained a list of booleans
  as to which RC files had been successfully loaded, but it required knowledge of the RC loading
  internals to interpret which status corresponded to which file. As above, the (successfully)
  loaded RC files are now shown in ``xonfig``.

**Fixed:**

* <news item>

**Security:**

* <news item>
