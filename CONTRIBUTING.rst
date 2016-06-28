.. _devguide:

=================
Developer's Guide
=================
.. image:: _static/knight-vs-snail.jpg
   :width: 80 %
   :alt: knight-vs-snail
   :align: center

Welcome to the xonsh developer's guide!  This is a place for developers to
place information that does not belong in the user's guide or the library
reference but is useful or necessary for the next people that come along to
develop xonsh.

.. note:: All code changes must go through the pull request review procedure.

Changelog
=========
Pull requests will often have CHANGELOG entries associated with. However,
to avoid excessive merge conflicts, please follow the following procedure:

1. Go into the ``news/`` directory,
2. Copy the ``TEMPLATE.rst`` file to another file in the ``news/`` directory.
   We suggest using the branchname::

        $ cp TEMPLATE.rst branch.rst

3. Add your entries as a bullet pointed lists in your ``branch.rst`` file in
   the appropriate category. It is OK to leave the ``None`` entries for later
   use.
4. Commit your ``branch.rst``.

Feel free to update this file whenever you want! Please don't use someone
else's file name. All of the files in this ``news/`` directory will be merged
automatically at release time.  The ``None`` entries will be automatically
filtered out too!


Style Guide
===========
xonsh is a pure Python project, and so we use PEP8 (with some additions) to
ensure consistency throughout the code base.

----------------------------------
Rules to Write By
----------------------------------
It is important to refer to things and concepts by their most specific name.
When writing xonsh code or documentation please use technical terms
appropriately. The following rules help provide needed clarity.

**********
Interfaces
**********
* User-facing APIs should be as generic and robust as possible.
* Tests belong in the top-level ``tests`` directory.
* Documentation belongs in the top-level ``docs`` directory.

************
Expectations
************
* Code must have associated tests and adequate documentation.
* User-interaction code (such as the Shell class) is hard to test.
  Mechanism to test such constructs should be developed over time.
* Have *extreme* empathy for your users.
* Be selfish. Since you will be writing tests you will be your first user.

-------------------
Python Style Guide
-------------------
xonsh uses `PEP8`_ for all Python code. The following rules apply where `PEP8`_
is open to interpretation.

* Use absolute imports (``import xonsh.tools``) rather than explicit
  relative imports (``import .tools``). Implicit relative imports
  (``import tools``) are never allowed.
* Use ``'single quotes'`` for string literals, and
  ``"""triple double quotes"""`` for docstrings. Double quotes are allowed to
  prevent single quote escaping, e.g. ``"Y'all c'mon o'er here!"``
* We use sphinx with the numpydoc extension to autogenerate API documentation. Follow
  the `numpydoc`_ standard for docstrings.
* Simple functions should have simple docstrings.
* Lines should be at most 80 characters long. The 72 and 79 character
  recommendations from PEP8 are not required here.
* All Python code should be compliant with Python 3.4+.  At some
  unforeseen date in the future, Python 2.7 support *may* be supported.
* Tests should be written with pytest using a procedural style. Do not use
  unittest directly or write tests in an object-oriented style.
* Test generators make more dots and the dots must flow!

You can easily check for style issues, including some outright bugs such
as mispelled variable names, using pylint. If you're using Anaconda you'll
need to run "conda install pylint" once. You can easily run pylint on
the edited files in your uncommited git change::

    $ pylint $(git status -s | awk '/\.py$$/ { print $$2 }' | sort)

If you want to lint the entire code base run::

    $ pylint $(find tests xonsh -name \*.py | sort)

**********
Imports
**********
Xonsh source code may be amalgamated into a single file (``__amalgam__.py``)
to speed up imports. The way the code amalgamater works is that other modules
that are in the same package (and amalgamated) should be imported with::

    from pkg.x import a, c, d

This is because the amalgamater puts all such modules in the same globals(),
which is effectively what the from-imports do. For example, ``xonsh.ast`` and
``xonsh.execer`` are both in the same package (``xonsh``). Thus they should use
the above from from-import syntax.

Alternatively, for modules outside of the current package (or modules that are
not amalgamated) the import statement should be either ``import pkg.x`` or
``import pkg.x as name``. This is because these are the only cases where the
amalgamater is able to automatically insert lazy imports in way that is guarantted
to be safe. This is due to the ambiguity that ``from pkg.x import name`` may
import a variable that cannot be lazily constructed or may import a module.
So the simple rules to follow are that:

1. Import objects from modules in the same package directly in using from-import,
2. Import objects from moudules outside of the package via a direct import
   or import-as statement.

How to Test
================

----------------------------------
Docker
----------------------------------

If you want to run your "work in progress version" without installing
and in a fresh environment you can use Docker. If Docker is installed
you just have to run this::

  $ python xonsh-in-docker.py

This will build and run the current state of the repository in an isolated
container (it may take a while the first time you run it). There are two
additionals arguments you can pass this script.

* The version of python
* the version of ``prompt_toolkit``

Example::

  $ python docker.py 3.4 0.57

Ensure your cwd is the root directory of the project (i.e., the one containing the
.git directory).

----------------------------------
Dependencies
----------------------------------

Prep your environment for running the tests::

    $ pip install -r requirements-tests.txt


----------------------------------
Running the Tests - Basic
----------------------------------

Run all the tests using pytest::

    $ py.test -q

Use "-q" to keep pytest from outputting a bunch of info for every test.  

----------------------------------
Running the Tests - Advanced
----------------------------------

To perform all unit tests::

    $ py.test

If you want to run specific tests you can specify the test names to
execute. For example to run test_aliases::

    $ py.test test_aliases.py

Note that you can pass multiple test names in the above examples::

    $ py.test test_aliases.py test_environ.py

Happy testing!


How to Document
====================
Documentation takes many forms. This will guide you through the steps of
successful documentation.

----------
Docstrings
----------
No matter what language you are writing in, you should always have
documentation strings along with you code. This is so important that it is
part of the style guide.  When writing in Python, your docstrings should be
in reStructured Text using the `numpydoc`_ format.

------------------------
Auto-Documentation Hooks
------------------------
The docstrings that you have written will automatically be connected to the
website, once the appropriate hooks have been setup.  At this stage, all
documentation lives within xonsh's top-level ``docs`` directory.
We uses the sphinx tool to manage and generate the documentation, which
you can learn about from `the sphinx website <http://sphinx-doc.org/>`_.
If you want to generate the documentation, first xonsh itself must be installed
and then you may run the following command from the ``docs`` dir:

.. code-block:: bash

    ~/xonsh/docs $ make html

For each new
module, you will have to supply the appropriate hooks. This should be done the
first time that the module appears in a pull request.  From here, call the
new module ``mymod``.  The following explains how to add hooks.

------------------------
Python Hooks
------------------------
Python documentation lives in the ``docs/api`` directory.
First, create a file in this directory that represents the new module called
``mymod.rst``.
The ``docs/api`` directory matches the structure of the ``xonsh/`` directory.
So if your module is in a sub-package, you'll need to go into the sub-package's
directory before creating ``mymod.rst``.
The contents of this file should be as follows:

**mymod.rst:**

.. code-block:: rst

    .. _xonsh_mymod:

    =======================================
    My Awesome Module -- :mod:`xonsh.mymod`
    =======================================

    .. currentmodule:: xonsh.mymod

    .. automodule:: xonsh.mymod
        :members:

This will discover all of the docstrings in ``mymod`` and create the
appropriate webpage. Now, you need to hook this page up to the rest of the
website.

Go into the ``index.rst`` file in ``docs/xonsh`` or other subdirectory and add
``mymod`` to the appropriate ``toctree`` (which stands for table-of-contents
tree). Note that every sub-package has its own ``index.rst`` file.


Building the Website
===========================

Building the website/documentation requires the following dependencies:

#. `Sphinx <http://sphinx-doc.org/>`_
#. `Cloud Sphinx Theme <https://pythonhosted.org/cloud_sptheme/cloud_theme.html>`_

-----------------------------------
Procedure for modifying the website
-----------------------------------
The xonsh website source files are located in the ``docs`` directory.
A developer first makes necessary changes, then rebuilds the website locally
by executing the command::

    $ make html

This will generate html files for the website in the ``_build/html/`` folder.
The developer may view the local changes by opening these files with their
favorite browser, e.g.::

    $ google-chrome _build/html/index.html

Once the developer is satisfied with the changes, the changes should be
committed and pull-requested per usual. Once the pull request is accepted, the
developer can push their local changes directly to the website by::

    $ make push-root

Branches and Releases
=============================
Mainline xonsh development occurs on the ``master`` branch. Other branches
may be used for feature development (topical branches) or to represent
past and upcoming releases.

All releases should have a release candidate ('-rc1') that comes out 2 - 5 days
prior to the scheduled release.  During this time, no changes should occur to
a special release branch ('vX.X.X-release').

The release branch is there so that development can continue on the
develop branch while the release candidates (rc) are out and under review.
This is because otherwise any new developments would have to wait until
post-release to be merged into develop to prevent them from accidentally
getting released early.

As such, the 'vX.X.X-release' branch should only exist while there are
release candidates out.  They are akin to a temporary second level of staging,
and so everything that is in this branch should also be part of master.

Every time a new release candidate comes out the vX.X.X-release should be
tagged with the name 'X.X.X-rcX'.  There should be a 2 - 5 day period of time
in between release candidates.  When the full and final release happens, the
'vX.X.X-release' branch is merged into master and then deleted.

If you have a new fix that needs to be in the next release candidate, you
should make a topical branch and then pull request it into the release branch.
After this has been accepted, the topical branch should be merged with
master as well.

The release branch must be quiet and untouched for 2 - 5 days prior to the
full release.

The release candidate procedure here only applies to major and minor releases.
Micro releases may be pushed and released directly without having a release
candidate.

------------------
Checklist
------------------
When releasing xonsh, make sure to do the following items in order:

1. Review **ALL** issues in the issue tracker, reassigning or closing them as
   needed.
2. Ensure that all issues in this release's milestone have been closed. Moving issues
   to the next release's milestone is a perfectly valid strategy for
   completing this milestone.
3. Perform maintenance tasks for this project, see below.
4. Write and commit the release notes.
5. Review the current state of documentation and make appropriate updates.
6. Bump the version (in code, documentation, etc.) and commit the change.
7. If this is a release candidate, tag the release branch with a name that
   matches that of the release:

   * If this is the first release candidate, create a release branch called
     'vX.X.X-release' off of develop.  Tag this branch with the name
     'X.X.X-rc1'.
   * If this is the second or later release candidate, tag the release branch
     with the name 'X.X.X-rcX'.

8. If this is the full and final release (and not a release candidate),
   merge the release branch into the master branch.  Next, tag the master
   branch with the name 'X.X.X'. Finally, delete the release branch.
9. Push the tags upstream
10. Update release information on the website.

--------------------
Maintenance Tasks
--------------------
You can cleanup your local repository of transient files such as \*.pyc files
created by unit testing by running::

    $ rm -f xonsh/lexer_table.py xonsh/parser_table.py
    $ rm -f xonsh/lexer_test_table.py xonsh/parser_test_table.py
    $ rm -f xonsh/*.pyc tests/*.pyc
    $ rm -f xonsh/*.rej tests/*.rej
    $rm -fr build

-----------------------
Performing the Release
-----------------------
To perform the release, run these commands for the following tasks:

**pip upload:**

.. code-block:: bash

    $ ./setup.py sdist upload


**conda upload:**

.. code-block:: bash

    $ rm -f /path/to/conda/conda-bld/src_cache/xonsh.tar.gz
    $ conda build --no-test recipe
    $ conda convert -p all -o /path/to/conda/conda-bld /path/to/conda/conda-bld/linux-64/xonsh-X.X.X-0.tar.bz2
    $ binstar upload /path/to/conda/conda-bld/*/xonsh-X.X.X*.tar.bz2

**website:**

.. code-block:: bash

    $ cd docs
    $ make clean html push-root


Document History
===================
Portions of this page have been forked from the PyNE documentation,
Copyright 2011-2015, the PyNE Development Team. All rights reserved.

.. _PEP8: https://www.python.org/dev/peps/pep-0008/
.. _numpydoc: https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt
