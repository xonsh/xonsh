**Added:** None

**Changed:**

* By default, ``stderr`` is colored in red.  This behavior can be modified with
  the ``$TRANSFORM_STDERR_LINE`` environment variable, which is applied to each
  line of ``stderr`` before it is displayed to the screen.
* Lines of stdout can also be transformed before being displayed, via the
  ``$TRANSFORM_STDOUT_LINE`` function.

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed an issue with the ``stderr`` attribute of ``ProcProxy`` objects, to
  ensure it is readable.

**Security:** None
