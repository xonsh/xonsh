**Added:** None

**Changed:**

* ``xonsh.prompt.gitstatus.gitstatus`` now returns a namedtuple

* implementation of ``xonsh.prompt.vc_branch.get_git_branch`` and
  ``xonsh.prompt.vc_branch.git_dirty_working_directory`` to use 'git status --procelain'

**Deprecated:** None

**Removed:** None

**Fixed:**

* ``xonsh.prompt.vc_branch.git_dirty_working_directory``
   uses ``porcelain`` option instead of using the bytestring
   ``nothing to commit`` to find out if a git directory is dirty

**Security:** None
