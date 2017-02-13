**Added:**

* New ``--rc`` command line option allows users to specify paths to run control
  files from the command line. This includes both xonsh-based and JSON-based
  configuration.

**Changed:**

* ``$XONSHRC`` and related configuration variables now accept JSON-based
  static configuration file names as elements. This unifies the two methods
  of run control to a single entry point and loading system.
* The ``xonsh.shell.Shell()`` class now requires that an Execer instance
  be explicitly provided to its init method. This class is no longer
  responsible for creating an execer an its deprendencies.

**Deprecated:**

* The ``--config-path`` command line option is now deprecated in favor of
  ``--rc``.

**Removed:** None

**Fixed:** None

**Security:** None
