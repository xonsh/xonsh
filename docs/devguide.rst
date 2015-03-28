.. _devguide:

=================
Developer's Guide
=================
Welcome to the xonsh developer's guide!  This is a place for developers to 
place information that does not belong in the user's guide or the library 
reference but is useful or necessary for the next people that come along to 
develop xonsh.

.. note:: All code changes must go through the pull request review procedure.

Style Guide
===========
xonsh is a pure Python project and so
we use PEP8 with some additions to ensure consistency throughout the code base.

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
  Mechanism to test such constucts should be developed over time.
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
  the numpydoc standard for docstrings `described here <https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt>`_.
* Simple functions should have simple docstrings.
* Lines should be at most 80 characters long. The 72 and 79 character 
  recommendations from PEP8 are not required here.
* All Python code should be compliant with Python 3.4+.  At some
  unforeseen date in the future, Python 2.7 support *may* be supported.
* Tests should be written with nose using a procedural style. Do not use 
  unittest directly or write tests in an object-oriented style.
* Test generators make more dots and the dots must flow!

How to Test
================
First, install nose: http://nose.readthedocs.org/en/latest/

To perform all unit tests::

    $ cd tests/
    $ nosetests

This will recursively look through the currently directory, open up every file
named test_* and run every function (or method) named test_*.

Nosetests can also take file(s) as an argument. For example, to just run the
mcnp and material module tests::

    $ nosetests test_lexer.py test_parser.py

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
in reStructured Text using the numpydoc format. 

------------------------
Auto-Documentation Hooks
------------------------
The docstrings that you have written will automatically be connected to the 
website, once the appropriate hooks have been setup.  At this stage, all 
documentation lives within xonsh's top-level ``docs`` directory. 
We uses the sphinx tool to manage and generate the documentation, which 
you can learn about from `the sphinx website <http://sphinx-doc.org/>`_.
If you want to generate the documentaion, first pyne itself must be installed 
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
First create a file in this directory that represents the new module called
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
commited and pull-requested per usual. Once the pull request is accepted, the
developer can push their local changes directly to the website by::

    $ make push-root


Document History
===================
Portions of this page have been forked from the PyNE documentation, 
Copyright 2011-2015, the PyNE Development Team. All rights reserved.

.. _PEP8: http://www.python.org/dev/peps/pep-0008/
