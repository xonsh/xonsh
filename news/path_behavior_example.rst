PATH Environment Variable Behavior
==================================

The ``$PATH`` environment variable in xonsh is always an ``EnvPath`` object, which provides
convenient methods for path manipulation. This behavior is consistent regardless of how
xonsh is started.

EnvPath Methods
---------------

The ``EnvPath`` class provides several useful methods:

* ``.prepend(path)``: Add a path to the beginning
* ``.append(path)``: Add a path to the end  
* ``.remove(path)``: Remove a path
* ``.insert(index, path)``: Insert at specific position

Examples
--------

Basic usage::

    # Add a directory to the front of PATH
    $PATH.prepend('/usr/local/bin')
    
    # Add to the end
    $PATH.append('/opt/custom/bin')
    
    # Remove a directory
    $PATH.remove('/unwanted/path')

This works consistently whether xonsh is started normally or with flags like ``--no-env``.

Before Fix (Buggy Behavior)
---------------------------

Previously, when using ``xonsh --no-env``, the ``$PATH`` variable would be a regular Python
list, causing errors:

.. code-block:: xonsh

    $ xonsh --no-env
    >>> $PATH.prepend('/usr/local/bin')
    AttributeError: 'list' object has no attribute 'prepend'

After Fix (Current Behavior)  
----------------------------

Now ``$PATH`` is always an ``EnvPath`` object:

.. code-block:: xonsh

    $ xonsh --no-env
    >>> $PATH.prepend('/usr/local/bin')  # Works correctly!
    >>> type($PATH).__name__
    'EnvPath'
