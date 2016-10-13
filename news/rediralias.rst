**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue with alais redirections to files throwing an OSError because
  the function ProcProxies were not being waited upon.
* Fixed issue with callablable aliases that happen to call sys.exit() or
  raise SystemExit taking out the whole xonsh process.

**Security:** None
