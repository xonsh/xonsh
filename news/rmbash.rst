**Added:**

* ``xonsh.platform`` now has a new ``PATH_DEFAULT`` variable.

**Changed:**

* ``Env`` now guarantees that the ``$PATH`` is available and mutable when
  initialized.

**Deprecated:** None

**Removed:**

* Bash is no longer loaded by default as a foreign shell for initial
  configuration. This was done to increase stock startup times. This
  behaviour can be recovered by adding ``{"shell": "bash"}`` to your
  ``"foreign_shells"`` in your config.json file. For more details,
  see http://xon.sh/xonshconfig.html#foreign-shells

**Fixed:** None

**Security:** None
