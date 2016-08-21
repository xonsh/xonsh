**Added:** None

**Changed:**

* ``dirstack.pushd`` and ``dirstack.popd`` now handle UNC paths (of form `\\<server>\<share>\...`), but only on Windows.
  They emulate behavior of `CMD.EXE` by creating a temporary mapped drive letter (starting from z: down) to replace
  the `\\<server>\<share>` portion of the path, on the ``pushd`` and unmapping the drive letter when all references
  to it are popped.

* And ``dirstack`` suppresses this temporary drive mapping funky jive if registry entry
  `HKCU\software\microsoft\command processor\DisableUNCCheck` (or HKLM\...) is a DWORD value 1.  This allows Xonsh
  to show the actual UNC path in your prompt string and *also* allows subprocess commands invoking `CMD.EXE` to run in
  the expected working directory. See https://support.microsoft.com/en-us/kb/156276 to satisfy any lingering curiosity.

**Deprecated:** None

**Removed:** None

**Fixed:**

* ``cd \\<server>\<share>`` now works when $AUTO_PUSHD is set, either creating a temporary mapped drive or simply
  setting UNC working directory based on registry ``DisableUNCCheck``.  However, if $AUTO_PUSHD is not set and UNC
  checking is enabled (default for Windows), it issues an error message and fails.  This improves on prior behavior,
  which would fail to change the current working directory, but would set $PWD and prompt string to the UNC path,
  creating false expectations.

**Security:** None
