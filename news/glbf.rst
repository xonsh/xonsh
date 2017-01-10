**Added:** None

**Changed:**

* The ``Block`` and ``Functor`` context managers from ``xonsh.contexts`` have been
  rewritten to use xonsh's macro capabilities. You must now enter these via the
   ``with!`` statement, e.g. ``with! Block(): pass``.
* The ``distributed`` xontrib now needs to use the ``with!`` statement, since it
  relies on ``Functor``.

**Deprecated:** None

**Removed:**

* ``XonshBlockError`` has been removed, since it no longer serves a purpose.

**Fixed:** None

**Security:** None
