**Added:**

* The python-mode ``@(expr)`` syntax may now be used inside of subprocess
  arguments, not just as a stand-alone argument. For example:

  .. code-block:: sh

    $ x = 'hello'
    $ echo /path/to/@(x)
    /path/to/hello

  This syntax will even properly expand to the outer product if the ``expr``
  is a list (or other non-string iterable) of values:

  .. code-block:: sh

    $ echo /path/to/@(['hello', 'world'])
    /path/to/hello /path/to/world

    $ echo @(['a', 'b']):@('x', 'y')
    a:x a:y b:x b:y

  Previously this was not possible.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
