**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* ``xonsh`` will return a non-zero exit code if it is run in file mode and
  cannot find the file specified, e.g.

  .. code-block::

     $ xonsh thisfiledoesntexist.xsh
     xonsh: thisfiledoesntexist.xsh: No such file or directory.
     $ _.returncode
     1

**Security:**

* <news item>
