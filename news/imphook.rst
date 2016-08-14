**Added:** None

**Changed:**

* ``xonsh.imphooks`` does not install the import hooks automatically, you now
  need to explicitly call the  `install_hook()` method defined in this module.
  For example: ``from xonsh.imphooks import install_hook; install_hook()``. The
  ``install_hook`` method can safely be called several times. If you need
  compatibility with previous versions of Xonsh you can use the following::

    from xonsh import imphooks
    getattr(imphooks, 'install_hook', lambda:None)()


**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
