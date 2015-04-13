.. _aliases:

********************
Aliases
********************

xonsh builtin aliases.

xexec
====================
xexec uses the ``os.execvpe()`` function to replace the xonsh process with
the specified program. This provides the functionality of the bash ``exec`` 
builtin.

.. code-block:: bash

  >>> xexec bash
  bash $ 

