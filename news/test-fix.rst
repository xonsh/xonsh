**Added:** None

**Changed:**

* Pytest plugin now uses ``xonsh.main.setup()`` to setup test environment.
* Linux platform discovery will no longer use ``platform.linux_distribution()``
  on Python >=3.6.6. due to pending deprecation warning.

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed further raw string deprecation warnings thoughout the code base.

**Security:** None
