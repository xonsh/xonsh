**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Replace deprecated calls to ``time.clock()`` by calls to
  ``time.perf_counter()``.
* Use ``clock()`` to set the start time of ``_timings`` in non-windows instead
  of manually setting it to ``0.0``.

**Security:** None
