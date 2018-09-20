**Added:**

* Format strings (f-strings) now allow environment variables to be looked up.
  For example, ``f"{$HOME}"`` will yield ``"/home/user"``. Note that this will
  look up and fill in the ``detype()``-ed version of the environment variable,
  i.e. it's native string representation.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
