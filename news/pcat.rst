**Added:**

* New ``xonsh-cat`` command line utility, which is a xonsh replacement
  for the standard UNIX ``cat`` command.
* The new ``xonsh.xoreutils.cat.cat_main()`` enables the ``xonsh.xoreutils.cat``
  module to be run as a command line utility.
* New ``CommandsCache.is_only_functional_alias()`` and
  ``CommandsCache.lazy_is_only_functional_alias()`` methods for determining if
  if a command name is only implemented as a function, and thus has no
  underlying binary command to execute.
* ``xonsh.xontribs.xontribs_load()`` is a new first-class API for loading
  xontribs via a Python function.

**Changed:**

* The xonsh Jupyter kernel now will properly redirect the output of commands
  such as ``git log``, ``man``, ``less`` and other paged commands to the client.
  This is done by setting ``$PAGER = 'cat'``. If ``cat`` is not available
  on the system, ``xonsh-cat`` is used instead.
* The ``setup()`` function for starting up a working xonsh has ``aliases``,
  ``xontribs``, and ``threadable_predictors`` as new additional keyword
  arguments for customizing the loading of xonsh.

**Deprecated:** None

**Removed:** None

**Fixed:**

* ``CommandsCache.locate_binary()`` will now properly return None when
  ``ignore_alias=False`` and the command is only a functional alias,
  such as with ``cd``. Previously, it would return the name of the
  command.

**Security:** None
