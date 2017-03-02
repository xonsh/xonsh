**Added:** None

**Changed:**

* The private ``_TeeStd`` class will no longer attempt to write to a
  standard buffer after the tee has been 'closed' and the standard
  buffer returned to the system.

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue with foregrounding jobs that were started in the background.

**Security:** None
