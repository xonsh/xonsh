**Added:**

* Wizard now has a ``FileInserter`` node that allows blocks to be
  inserted and replaced inside of a file. This adheres to conversion
  rules fordumping as provided on this node.
* New ``xonsh.wizard.StateVisitor.flatten()`` method for flattening the
  current state.

**Changed:**

* The xonsh startup wizard will only be triggered if no xonshrc files exist
  and the file ``~/.local/config/xonsh/no-wizard`` is not present.
* The ``xonfig wizard`` command will now run write out to the xonshrc file.
* Wizard nodes ``Save`` and ``Load`` had their names changed to ``SaveJSON``
  and ``LoadJSON``.


**Deprecated:** None

**Removed:**

* Static configuration is dead (``config.json``), long live run control (``xonshrc``)!
* The following evironment variables have been removed as they are no longer needed:
  ``$LOADED_CONFIG`` and ``$XONSHCONFIG``.
* Many support functions for static configuration have also been removed.

**Fixed:** None

**Security:** None
