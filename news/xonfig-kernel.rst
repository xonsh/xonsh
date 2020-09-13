**Added:**

* ``xonfig kernel`` new subcommand to generate xonsh kernel spec for jupyter.

**Changed:**

* ``xonfig info`` displays whether jupyter detected in environment and 
  also path of xonsh jupyter kernel spec, if any.

**Deprecated:**

* <news item>

**Removed:**

* setup no longer (tries to) install jupyter kernel automatically, 
  user must run ``xonfig kernel`` manually.

**Fixed:**

* Setup wasn't consistently detecting jupyter in environment; ``python setup.py install`` worked, but
  ``pip install .`` wouldn't (because pip mucks with ``sys.path``), 
  nor would install from wheel (because it doesn't run ``setup.py``).

**Security:**

* <news item>
