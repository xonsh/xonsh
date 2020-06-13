**Added:**

* CI step to run flake8 after pytest.

**Changed:**

* Updated pytest_plugin for pytest 5.4 API, pip requirements for pytest>= 5.4
* setup.cfg / flake8: removed all per-file ignores, replaced with per-line #noqa where not fixed.
  global list of 'builtins' includes xonsh builtins added by magic to global namespace
  global list of rules ignored in all files, added a few

**Deprecated:**

* `pytest --flake8`_ now exits with error message to use flake8 instead.
  flake8 uses use same list of lint exceptions in CI and your IDE.

**Removed:**

* pytest-flake8 package from requirements\*.txt

**Fixed:**

* Updated development guide to reference flake8 instead of pylint
* docs/ `make html`_ enable xonshcon code block,
  Eliminates warnings and errors during build -- docs look ever so much prettier.
* Resolved many but not all pytest deprecation warnings during a 'clean' test run.

**Security:**

* <news item>
