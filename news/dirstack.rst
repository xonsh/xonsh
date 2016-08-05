**Added:** None

**Changed:**

* ``dirstack.pushd`` and ``dirstack.popd`` now handle UNC paths (of form `\\<server>\<share>\...`), but only on Windows.
  They emulate behavior of `CMD.EXE` by creating a temporary mapped drive letter (starting from z: down) to replace
  the `\\<server>\<share>` portion of the path, on the ``pushd`` and unmapping the drive letter when all references
  to it are popped.

* And ``dirstack`` suppresses this temporary drive mapping funky jive if registry entry
  `HKLM\software\microsoft\command processor\DisableUNCCheck` is a DWORD value 1.  This allows Xonsh to show
  the actual UNC path in your prompt string and *also* allows subprocess commands invoking `CMD.EXE` to run in the
  expected working directory. See https://support.microsoft.com/en-us/kb/156276 to satisfy any lingering curiosity.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
