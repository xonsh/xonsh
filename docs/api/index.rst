.. _api:

=================
Xonsh API
=================

The ``xonsh.api`` package is a set of public libraries that can be used
in third-party projects as well as in xonsh extensions (xontribs).  If
you are writing a xontrib, using ``xonsh.api`` is the recommended way to
interact with xonsh internals.

.. warning::

    The API is under development and currently has a small number
    of methods.  Contributions are welcome!

For the full internal library reference, see :doc:`/lib/index`.


``xonsh.api.subprocess``
========================

Drop-in replacements for :mod:`subprocess` functions that use xonsh's
subprocess pipeline under the hood.

.. autofunction:: xonsh.api.subprocess.run

.. autofunction:: xonsh.api.subprocess.check_call

.. autofunction:: xonsh.api.subprocess.check_output


``xonsh.api.os``
================

Xonsh-powered utilities inspired by the :mod:`os` module.

.. autofunction:: xonsh.api.os.rmtree

.. autodata:: xonsh.api.os.indir
