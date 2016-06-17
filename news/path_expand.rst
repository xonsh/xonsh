**Added:**

* A new class, ``xonsh.tools.EnvPath`` has been added. This class implements a
  ``MutableSequence`` object and overrides the ``__getitem__`` method so that
  when its entries are requested (either explicitly or implicitly), variable
  and user expansion is performed, and relative paths are resolved.
  ``EnvPath`` accepts objects (or lists of objects) of ``str``, ``bytes`` or
  ``pathlib.Path`` types.

**Changed:**

* All ``PATH``-like environment variables are now stored in an ``EnvPath``
  object, so that non-absolute paths or paths containing environment variables
  can be resolved properly.

**Deprecated:** None

**Removed:** None

**Fixed:** 

* Issue where ``xonsh`` did not expand user and environment variables in
  ``$PATH``, forcing the user to add absolute paths.

**Security:** None
