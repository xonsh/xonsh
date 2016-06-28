.. _tutorial_xontrib:

************************************
Tutorial: Extensions (Xontribs)
************************************
Take a deep breath and prepare for some serious Show & Tell; it's time to
learn about xonsh extensions!

Overview
================================
Xontributions, or ``xontribs``, are a set of tools and conventions for
extending the functionality of xonsh beyond what is provided by default. This
allows 3rd party developers and users to improve their xonsh experience without
having to go through the xonsh development and release cycle.

Many tools and libraries have extension capabilities. Here are some that we
took inspiration from for xonsh:

* `Sphinx <http://sphinx-doc.org/>`_: Extensions are just Python modules,
  bundles some extensions with the main package, interface is a list of
  string names.
* `Oh My Zsh <http://ohmyz.sh/>`_: Centralized registry, autoloading, and
  for a shell.
* `ESLint <http://eslint.org/>`_: Ability to use language package manager
  to install/remove extensions.


Structure
==========
Xontribs are modules written in either xonsh (``*.xsh``) or Python (``*.py``).
Normally, these are stored and found in an
`implicit namespace package <https://www.python.org/dev/peps/pep-0420/>`_
called ``xontrib``. However, xontribs may be placed in any package or directory
that is on the ``$PYTHONPATH``.

If a module is in the ``xontrib`` namespace package, it can be referred to just
by its module name. If a module is in any other package, then it must be
referred to by its full package path, separated by ``.`` like you would in an
import statement.  Of course, a module in ``xontrib`` may be referred to
with the full ``xontrib.myext``. But just calling it ``myext`` is a lot shorter
and one of the main advantages of placing an extension in the ``xontrib``
namespace package.

Here is a sample file system layout and what the xontrib names would be::

    |- xontrib/
       |- javert.xsh     # "javert", because in xontrib
       |- your.py        # "your",
       |- eyes/
          |- __init__.py
          |- scream.xsh  # "eyes.scream", because eyes is in xontrib
    |- mypkg/
       |- __init__.py    # a regular package with an init file
       |- other.py       # not a xontrib
       |- show.py        # "mypkg.show", full module name
       |- tell.xsh       # "mypkg.tell", full module name
       |- subpkg/
          |- __init__.py
          |- done.py     # "mypkg.subpkg.done", full module name


Loading Xontribs
================
Xontribs may be loaded in a few different ways: from the config file,
dynamically at runtime with the ``xontrib`` command, or by importing the
module normally. Since these extensions are just Python modules, by
default, they cannot be unloaded (easily).

.. note::

    When a xontrib is loaded from a config file or via the xontrib command,
    its public variables are placed in the current execution context, just
    like variables set in run control files.

Loading xontribs in the config file is as simple as adding a list of string
xontrib names to the top-level ``"xontribs"`` key. For example, the following
would load the ``"mpl"`` and ``"example"`` xontribs.

.. code:: json

    {"xontribs": ["mpl", "example"]}

Extensions may also be loaded via the ``xontrib`` command, which is a xonsh
default alias. This command may be run from anywhere in a xonshrc file or at
any point after xonsh has started up. Loading is the default action of the
``xontrib`` command. Thus the following methods for loading via this command
are equivalent:

.. code-block:: xonsh

    xontrib myext mpl mypkg.show
    xontrib load myext mpl mypkg.show

Loading the same xontrib multiple times does not have any effect after the
first. Xontribs are simply Python modules, and therefore follow the same
caching rules. So by the same token, you can also import them normally.
Of course, you have to use the full module name to import a xontrib:

.. code-block:: python

    import xontrib.mpl
    from xontrib import myext
    from mypkg.show import *


Listing Known Xontribs
======================
In addition to loading extensions, the ``xontrib`` command also allows you to
list the known xontribs. This command will report whether known xontribs are
installed and if they are loaded in the current session. To display this
information, pass the ``list`` action to the ``xontrib`` command:

.. code-block:: xonshcon

    >>> xontrib list
    mpl     installed      not-loaded
    myext   not-installed  not-loaded

By default, this will display information for all known xontribs. However,
you can restrict this to a set of names passed in on the command line.

.. code-block:: xonshcon

    >>> xontrib list mpl
    mpl     installed      not-loaded

For programmatic access, you may also have this command print a JSON formatted
string:

.. code-block:: xonshcon

    >>> xontrib list --json mpl
    {"mpl": {"loaded": false, "installed": true}}

Authoring Xontribs
=========================
Writing a xontrib is as easy as writing a xonsh or Python file and sticking
it in a directory named ``xontrib/``. However, please do not place an
``__init__.py`` in the ``xontrib/`` directory. It is an
*implicit namespace package* and should not have one. See
`PEP 420 <https://www.python.org/dev/peps/pep-0420/>`_ for more details.

.. warning::

    Do not place an ``__init__.py`` in the ``xontrib/`` directory!

If you plan on using ``*.xsh`` files in you xontrib, then you'll
have to add some hooks to distutils, setuptools, pip, etc. to install these
files. Try adding entries like the following entries to your ``setup()`` call
in your ``setup.py``:

.. code-block:: python

    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup

    setup(...,
          packages=[..., 'xontrib'],
          package_dir={..., 'xontrib': 'xontrib'},
          package_data={..., 'xontrib': ['*.xsh']},
          ...)

Something similar can be done for any non-xontrib package or sub-package
that needs to distribute ``*.xsh`` files.


Tell Us About Your Xontrib!
===========================
We request that you register your xontrib with us.  We think that this is a
good idea, in general, because then:

* Your xontrib will show up as an extension the xonsh website,
* It will appear in the ``xontrib list`` command, and
* It will show up in ``xonfig wizard``.

All of this let's users know that your xontrib is out there, ready to be used.
Of course, your under no obligation to register your xontrib.  Users will
still be able to load your xontrib, as long as they have it installed.

To register a xontrib, add an entry to
`the xontribs.json file <https://github.com/xonsh/xonsh/blob/master/xonsh/xontribs.json>`_
in the main xonsh repository.  A pull request is probably best, but if you
are having trouble figuring it out please contact one of the xonsh devs
with the relevant information.
This is a JSON file with two top-level keys: ``"xontribs"`` and ``"packages"``.

The ``"xontribs"`` key is a list of dictionaries that describes the xontrib
module itself.  Such entries have the following structure:

.. code-block:: json

    {"xontribs": [
     {"name": "xontrib-name",
      "package": "package-name",
      "url": "http://example.com/api/xontrib",
      "description": ["Textual description as string or list or strings ",
                      "enabling long content to be split over many lines."]
      }
     ]
    }

The ``"packages"`` key, on the other hand, is a dict mapping package names
(associated with the xontrib entries) to metadata about the package. Package
entries have the following structure:

.. code-block:: json

    {"packages": {
      "package-name": {
       "license": "WTFPL v1.1",
       "url": "http://example",
       "install": {
        "conda": "conda install package-name",
        "pip": "pip install package-name"}
       }
     }
    }

Note that you can have as many entries in the ``"install"`` dict as you
want. Also, the keys are arbitrary labels, so feel free to pick whatever
you want.

Go forth!
