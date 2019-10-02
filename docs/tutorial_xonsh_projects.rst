.. _tutorial_xonsh_projects:

************************************
Tutorial: Xonsh Projects
************************************
Bam! Suppose you want to get beyond scripting and write a whole
library, utility, or other big project in xonsh. Here is how you do
that. Spoiler alert: it is easy, powerful, and fun!

Overview
================================
Xonsh is fully interoperable with Python. Writing a xonsh library is
very similar to writing a Python library, using all of the same tooling
and infrastructure for packaging pure Python code.

Structure
==========
Xonsh modules are written in xonsh files (``*.xsh``), side-by-side with Python files
(``*.py``). Suppose we have a package called ``mypkg`` which uses xonsh files.
Here is a sample file system layout would be::

    |- mypkg/
       |- __init__.py    # a regular package with an init file
       |- other.py       # not a xonsh file
       |- show.py        # "mypkg.show", full module name
       |- tell.xsh       # "mypkg.tell", full module name
       |- subpkg/
          |- __init__.py
          |- a.py      # "mypkg.subpkg.a", full module name
          |- b.xsh     # "mypkg.subpkg.b", full module name

To ensure that these files are installed, you need to provide the
appropriate information in ``setup.py`` file for your project.
For the above structure, this looks like the following.

**setup.py**::

    setup(
        packages=['mypkg', 'mypkg.subpkg'],
        package_dir={'mypkg': 'mypkg', 'mypkg.subpkg': 'mypkg/subpkg'},
        package_data={'mypkg': ['*.xsh'], 'mypkg.subpkg': ['*.xsh']},
    )

With this, the xonsh code will be installed and included in any source
distribution you create!

Setting up xonsh sessions
=========================
Xonsh code requires a ``XonshSession`` to exist as ``builtins.__xonsh__`` and for
be that object to be setup correctly. This can be quite a bit of work and
the exact setup depends on the execution context. To simplify the process
of constructing the session properly, xonsh provides the ``xonsh.main.setup()``
function specifically for use in 3rd party packages.

While ``xonsh.main.setup()`` is safely re-entrant, it is a good idea to add the following
snippet to the root-level ``__init__.py`` of your project. With the ``mypkg`` example
above, the session setup is as follows:

``mypkg/__init__.py``

.. code-block:: python

    from xonsh.main import setup
    setup()
    del setup

Enjoy!
