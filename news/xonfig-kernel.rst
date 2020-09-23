**Added:**

* ``xonfig jupyter-kernel`` new subcommand to generate xonsh kernel spec for jupyter.  
  Installing a new xonsh kernel for jupyter automatically removes any other one registered with jupyter, 
  otherwise the new one might not be used.

**Changed:**

* ``xonfig info`` displays whether jupyter detected in environment and 
  also path of xonsh jupyter kernel spec, if any.

**Deprecated:**

* <news item>

**Removed:**

* setup no longer (tries to) install jupyter kernel automatically, 
  user must run ``xonfig jupyter-kernel`` manually.

**Fixed:**

* Setup wasn't consistently detecting jupyter in environment; ``python setup.py install`` worked, but
  ``pip install .`` wouldn't (because pip mucks with ``sys.path``), 
  nor would install from wheel (because it doesn't run ``setup.py``).
* ``xonfig info`` now displays actual value of ON_MSYS and ON_CYGWIN instead of lazy bool type.
  (maybe was happening only on Windows?)

**Security:**

* <news item>
