**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Run control files are now read in with ``$THREAD_SUBPROCS`` off.
  This prevents a weird error when starting xonsh from Bash (and
  possibly other shells) where the top-level xonsh process would
  be stopped and placed into the background during startup. It
  may be necessary to set ``$THREAD_SUBPROCS=False`` in downstream
  xonsh scripts and modules.

**Security:**

* <news item>
