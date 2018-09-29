**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* try_subproc_toks now works for subprocs with trailing and leading whitespace

  Previously, non-greedy wrapping of commands would fail if they had leading and trailing whitespace:

  .. code-block:: sh

    $ true && false || echo a                                                                                           
    xonsh: For full traceback set: $XONSH_SHOW_TRACEBACK = True
    NameError: name 'false' is not defined

    $ echo; echo && echo a

    xonsh: For full traceback set: $XONSH_SHOW_TRACEBACK = True
    NameError: name 'echo' is not defined

  Now, the commands are parsed as expected:

  .. code-block:: sh

    $ true && false || echo a 
    a

    $ echo; echo && echo a


    a


**Security:** None
