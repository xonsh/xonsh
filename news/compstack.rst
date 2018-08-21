**Added:**

* Callable aliases may now accept a ``stack`` argument. If they do, then the
  stack, as computed from the aliases call site, is provided as a list of
  ``FrameInfo`` objects (as detailed in the standard library ``inspect``
  module). Otherwise, the ``stack`` parameter is ``None``.
* ``SubprocSpec`` now has a ``stack`` attribute, for passing the call stack
  to callable aliases. This defaults to ``None`` if the spec does not
  need the stack. The ``resolve_stack()`` method computes the ``stack``
  attribute.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* The ``completer`` command now correctly finds completion functions
  when nested inside of other functions.

**Security:** None
