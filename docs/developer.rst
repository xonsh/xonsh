.. _developer:

Developer's Guide
=============================

.. image:: _static/knight-vs-snail.jpg

Welcome to the xonsh developer's guide! This is a place for developers to
place information that does not belong in the user's guide or the library
reference but is useful or necessary for the next people that come along to
develop xonsh.

.. note:: All code changes must go through the pull request review procedure.


Making Your First Change
-------------------------

Terminal-based workflow
^^^^^^^^^^^^^^^^^^^^^^^

The simplified terminal-based workflow to contribute to xonsh:

.. code-block:: bash

    mkdir -p ~/git && cd ~/git
    # For example your name is `snail` and you forked https://github.com/xonsh/xonsh on Github
    git clone git@github.com:snail/xonsh.git
    # You can setup IDE (see next section) to extremely speed up the work and test.
    cd xonsh

    # Set git user name. Without `--global` it will work in local repository.
    git config user.name "Snail"
    git config user.email "snail@email.com"

    # Create your feature or fix branch.
    git checkout -b my_awesome_feature

    # Install dev packages.
    # python -m ensurepip --upgrade  # install pip if you have python without pip
    pip install -U pip
    pip install '.[dev]' '.[doc]'

    # Make changes: add new environment variable.
    vim xonsh/environ.py
    git add xonsh/environ.py

    # Create test.
    vim tests/environ.py
    python -m pytest

    # Live test.
    python -m xonsh --no-rc

    # Push
    git commit -m "My new environment variable!"
    git push

    # Open https://github.com/xonsh/xonsh/pulls
    # Use green button to open Pull Request (PR)
    # Use Conventional Commits naming e.g.
    # "feat: New env variable $SNAIL"

IDE-based workflow
^^^^^^^^^^^^^^^^^^

You can also use IDE like PyCharm:

1. Install IDE e.g. `PyCharm <https://www.jetbrains.com/pycharm/>`_.
2. Go to ``File -> Project from Version Control -> URL`` https://github.com/xonsh/xonsh
3. Go to the terminal and update pip and install full dependencies:

   .. code-block:: xonsh

       # Run from PyCharm terminal with appropriate environment.
       python -m pip install -U pip  # you need pip >= 24
       python -m pip install '.[full]' '.[dev]' '.[doc]'

4. Setup IDE e.g. PyCharm:

   .. code-block:: text

       Create project based on xonsh code directory.
       Click "Run" - "Run..." - "Edit Configurations"
       Click "+" and choose "Python". Set:
           Name: "xonsh --no-rc".
           Run: choose "module" and write "xonsh".
           Script parameters: "--no-rc -DFROM=PYCHARM" (here "FROM" will help to identify process using `ps ax | grep PYCHARM`).
           Working directory: "/tmp"  # to avoid corrupting the source code during experiments
           Environment variables: add ";XONSH_SHOW_TRACEBACK=1"
           Modify options: click "Emulate terminal in output console".
       Save settings.

       Open `xonsh/procs/specs.py` and `def run_subproc` function.
       Put breakpoint to `specs = cmds_to_specs` code. See also: https://www.jetbrains.com/help/pycharm/using-breakpoints.html
       Click "Run" - "Debug..." - "xonsh". Now you can see xonsh prompt.
       Run `echo 1` and now you're in the debug mode on the breakpoint.
       Press F8 to step forward. Good luck!

5. Create git branch and solve `good first issue <https://github.com/xonsh/xonsh/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22+sort%3Areactions-%2B1-desc>`_ or `popular issue <https://github.com/xonsh/xonsh/issues?q=is%3Aissue+is%3Aopen+sort%3Areactions-%2B1-desc>`_.
6. Create pull request to xonsh.


Changelog
----------

1. Use `conventional commits <https://www.conventionalcommits.org/en/v1.0.0/>`_ for your git commits and Pull-Request titles
2. `CHANGELOG.md <CHANGELOG.md>`_ is automatically generated from these commit messages using `release-please-action <https://github.com/googleapis/release-please-action>`_
3. We squash the Pull-Request commits when merging to maintain linear history. So it is important to use


Style Guide
------------

xonsh is a pure Python project, and so we use PEP8 (with some additions) to
ensure consistency throughout the code base.

Rules to Write By
^^^^^^^^^^^^^^^^^^

It is important to refer to things and concepts by their most specific name.
When writing xonsh code or documentation please use technical terms
appropriately. The following rules help provide needed clarity.

Interfaces
"""""""""""

* User-facing APIs should be as generic and robust as possible.
* Tests belong in the top-level ``tests`` directory.
* Documentation belongs in the top-level ``docs`` directory.

Expectations
"""""""""""""

* Code must have associated tests and adequate documentation.
* User-interaction code (such as the Shell class) is hard to test.
  Mechanism to test such constructs should be developed over time.
* Have *extreme* empathy for your users.
* Be selfish. Since you will be writing tests you will be your first user.

Python Style Guide
^^^^^^^^^^^^^^^^^^^

xonsh follows `PEP8 <https://www.python.org/dev/peps/pep-0008/>`_ for all Python code. The following rules apply where
`PEP8 <https://www.python.org/dev/peps/pep-0008/>`_ is open to interpretation.

* Use absolute imports (``import xonsh.tools``) rather than explicit
  relative imports (``import .tools``). Implicit relative imports
  (``import tools``) are never allowed.
* We use sphinx with the numpydoc extension to autogenerate API documentation. Follow
  the `numpydoc <https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>`_ standard for docstrings.
* Simple functions should have simple docstrings.
* Lines should be at most 80 characters long. The 72 and 79 character
  recommendations from PEP8 are not required here.
* Tests should be written with `pytest <https://docs.pytest.org/>`_ using a procedural style. Do not use
  unittest directly or write tests in an object-oriented style.
* Test generators make more dots and the dots must flow!
* We use `ruff <https://docs.astral.sh/ruff/>`_ for linting and formatting the code. It is used as a `pre-commit <https://pre-commit.com/>`_ hook. Enable it by running:

.. code-block:: bash

    pre-commit install
    pre-commit run --all-files


How to Test
------------

Container
^^^^^^^^^

If you want to run your "work in progress version" without installing
and in a fresh environment you can use Docker. If Docker is installed
you just have to run this:

.. code-block:: bash

    python xonsh-in-docker.py

This will build and run the current state of the repository in an isolated
container (it may take a while the first time you run it). You can override
the default Python and ``prompt_toolkit`` versions with ``--python`` and
``--ptk``:

.. code-block:: bash

    python xonsh-in-docker.py --python 3.13 --ptk 3.0.52

Ensure your cwd is the root directory of the project (i.e., the one containing the
.git directory).

Dependencies
^^^^^^^^^^^^^

Prep your environment for running the tests:

.. code-block:: bash

    pip install -e '.[dev]'

Running the Tests - Basic
^^^^^^^^^^^^^^^^^^^^^^^^^^

Run all the tests using pytest. Use ``python -m pytest`` to prevent using xonsh code from ``site-packages`` if xonsh was installed in the same environment:

.. code-block:: bash

    python -m pytest -q

Use "-q" to keep pytest from outputting a bunch of info for every test.

Running the Tests - Advanced
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To perform all unit tests:

.. code-block:: bash

    python -m pytest

If you want to run specific tests you can specify the test names to
execute. For example to run test_aliases:

.. code-block:: bash

    python -m pytest test_aliases.py

Note that you can pass multiple test names in the above examples:

.. code-block:: bash

    python -m pytest test_aliases.py test_environ.py

Writing the Tests - Advanced
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

(refer to pytest documentation)

With the Pytest framework you can use bare ``assert`` statements on
anything you're trying to test, note that the name of the test function
has to be prefixed with ``test_``:

.. code-block:: python

    def test_whatever():
        assert is_true_or_false

The conftest.py in tests directory defines fixtures for mocking various
parts of xonsh for more test isolation. For a list of the various fixtures:

.. code-block:: bash

    python -m pytest --fixtures

when writing tests it's best to use pytest features i.e. parametrization:

.. code-block:: python

    @pytest.mark.parametrize('env', [test_env1, test_env2])
    def test_one(env, xession):
        # update the environment variables instead of setting the attribute
        # which could result in leaks to other tests.
        # each run will have the same set of default env variables set.
        xession.env.update(env)
        ...

this will run the test two times each time with the respective ``test_env``.
This can be done with a for loop too but the test will run
only once for the different test cases and you get less isolation.

With that in mind, each test should have the least ``assert`` statements,
preferably one.

At the moment, xonsh doesn't support any pytest plugins.

Happy Testing!


How to Document
----------------

Documentation takes many forms. This will guide you through the steps of
successful documentation.

Docstrings
^^^^^^^^^^^

No matter what language you are writing in, you should always have
documentation strings along with you code. This is so important that it is
part of the style guide. When writing in Python, your docstrings should be
in reStructured Text using the `numpydoc <https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>`_ format.

Auto-Documentation Hooks
^^^^^^^^^^^^^^^^^^^^^^^^^^

The docstrings that you have written will automatically be connected to the
website, once the appropriate hooks have been setup. At this stage, all
documentation lives within xonsh's top-level ``docs`` directory.
We uses the sphinx tool to manage and generate the documentation, which
you can learn about from `the sphinx website <http://sphinx-doc.org/>`_.
If you want to generate the documentation, first xonsh itself must be installed
and then you may run the following command from the ``docs`` dir:

.. code-block:: bash

    cd docs/
    make html

For each new
module, you will have to supply the appropriate hooks. This should be done the
first time that the module appears in a pull request. From here, call the
new module ``mymod``. The following explains how to add hooks.

Python Hooks
^^^^^^^^^^^^^

Python API documentation is generated for the entries in ``docs/api.rst``.
`sphinx-autosummary <https://www.sphinx-doc.org/en/master/usage/extensions/autosummary.html>`_
is used to generate documentation for the modules.
Mention your module ``mymod`` under appropriate header.
This will discover all of the docstrings in ``mymod`` and create the
appropriate webpage.


Building the Website
---------------------

Building the website/documentation requires the following dependencies:

1. `Sphinx <http://sphinx-doc.org/>`_
2. `Furo Theme <https://pradyunsg.me/furo/>`_
3. `numpydoc <https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>`_
4. `MyST Parser <https://myst-parser.readthedocs.io>`_

Note that xonsh itself needs to be installed too.

If you have cloned the git repository, you can install all of the doc-related
dependencies by running:

.. code-block:: bash

    pip install -e '.[doc]'

Procedure for modifying the website
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The xonsh website source files are located in the ``docs`` directory.
A developer first makes necessary changes, then rebuilds the website locally
by executing the command:

.. code-block:: bash

    cd docs/
    make html

This will generate html files for the website in the ``_build/html/`` folder.

You can watch for changes and automatically rebuild the documentation with the following command:

.. code-block:: bash

    make serve

The developer may view the local changes by opening these files with their
favorite browser, e.g.:

.. code-block:: bash

    firefox _build/html/index.html

Once the developer is satisfied with the changes, the changes should be
committed and pull-requested per usual. The docs are built and deployed using
GitHub Actions.

Docs associated with the latest release are hosted at `https://xon.sh <https://xon.sh>`_
while docs for the current ``main`` branch are available at `https://xon.sh/dev <https://xon.sh/dev>`_.


Branches and Releases
----------------------

Mainline xonsh development occurs on the ``main`` branch. Other branches
may be used for feature development (topical branches) or to represent
past and upcoming releases.

Maintenance Tasks
^^^^^^^^^^^^^^^^^^

You can cleanup your local repository of transient files such as \*.pyc files
created by unit testing by running:

.. code-block:: bash

    rm -f xonsh/parser_table.py xonsh/completion_parser_table.py
    rm -f xonsh/*.pyc tests/*.pyc
    rm -fr build

Performing the Release
^^^^^^^^^^^^^^^^^^^^^^^

Releases are automated via `GitHub Actions <https://github.com/xonsh/xonsh/tree/main/.github/workflows>`_.
All workflows for testing, building Python packages, and producing AppImage
binaries live in the ``.github/workflows`` directory of the repository.

Cross-platform testing
^^^^^^^^^^^^^^^^^^^^^^^

Most of the time, an actual VM machine is needed to test the nuances of cross platform testing.
But alas here are some other ways to test things

1. Windows

   - `wine <https://www.winehq.org/>`_ can be used to emulate the development environment. It provides cmd.exe with its default installation.

2. macOS

   - `darlinghq <https://www.darlinghq.org/>`_ can be used to emulate the development environment for Linux users.
     Windows users can use Linux inside a virtual machine or WSL to run the same.
   - `OSX KVM <https://github.com/kholia/OSX-KVM>`_ can be used for virtualization.

3. Linux

   - It far easier to test things for Linux. `docker <https://www.docker.com/>`_ is available on all three platforms.

One can leverage the Github Actions to provide a reverse shell to test things out.
Solutions like `actions-tmate <https://mxschmitt.github.io/action-tmate/>`_ are available,
but they should not in any way violate the Github Action policies.


Python versions support policy
------------------------------

Xonsh adopts `NEP-0029 <https://numpy.org/neps/nep-0029-deprecation_policy.html>`_ in supporting Python versions.
Simply speaking a minor Python release (X.*) will be supported for 42 months from its date of initial release.
Since Python has adopted yearly release cycle, most of the time,
the latest 4 minor versions of Python would be supported at any given time.


Testing xonsh on Different Operating Systems
---------------------------------------------

It is often useful to try xonsh in a clean environment on a distribution
other than your own — for example to reproduce a bug report or to
validate a change against a pristine setup. The recipes below use
rootless ``podman`` containers; ``docker`` would work just as well if
you prefer it.

NixOS
^^^^^

.. code-block:: bash

    podman run --rm -it nixos/nix
    nix-channel --update && nix-shell -p xonsh
    xonsh
    xcontext

Arch Linux
^^^^^^^^^^

.. code-block:: bash

    podman run --rm -it archlinux/archlinux
    pacman -Syu git python-pip
    pacman -Syu man-db man-pages bash-completion
    git clone https://github.com/xonsh/xonsh
    cd xonsh
    pip install --break-system-packages '.[dev]' '.[test]' '.[doc]'
    python -m pytest


Document History
-----------------

Portions of this page have been forked from the PyNE documentation,
Copyright 2011-2015, the PyNE Development Team. All rights reserved.

Chronicle
-----------------

.. toctree::
    :titlesonly:
    :maxdepth: 1
    :hidden:

    changelog
    talks_and_articles
    faq
