**Added:**

* A multipurpose add method to EnvPath
  example:
    $ $PATH
    EnvPath(
    ['/usr/bin', '/usr/local/bin', '/bin']
    )
    $ $PATH.add('~/.local/bin', front=True); $PATH
    EnvPath(
    ['/home/user/.local/bin', '/usr/bin', '/usr/local/bin', '/bin']
    )
    $ $PATH.add('/usr/bin', front=True, replace=True); $PATH
    EnvPath(
    ['/usr/bin', '/home/user/.local/bin', '/usr/local/bin', '/bin']
    )

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None

