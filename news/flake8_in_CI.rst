**Added:**

* CI step to run flake8 after pytest.

**Changed:**

* Updated pytest_plugin for pytest 5.4 API, pip requirements for pytest>= 5.4

**Deprecated:**

* `pytest --flake8`_ now exits with error message to use flake8 instead.
  Allows single list of lint exceptions to apply in CI and your IDE.

**Removed:**

* pytest-flake8 package from requirements\*.txt

**Fixed:**

* Updated development guide to reference flake8 instead of pylint
* Corrected flake8 config for allowed exceptions.
* various pytest warnings in a "clean" test run.

**Security:**

* <news item>
