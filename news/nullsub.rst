**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Null bytes handed to Popen are now automatically escaped prior
  to running a subprocess. This preevents Popen from issuing
  embedded null byte exceptions.

**Security:** None
