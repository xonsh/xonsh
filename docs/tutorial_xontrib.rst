.. _tutorial_xontrib:

************************************
Tutorial: Extensions
************************************
Take a deep breath and prepare for some serious Show & Tell; it's time to
learn about xonsh extentions!

Overview
================================
Xontributions, or ``xontribs``, are a set of tools and conventions for
extending the functionality of xonsh beyond what is provided by default. This
allows 3rd party developers and users to improve thier xonsh experiance without
having to go through the xonsh development and release cycle.

Many tools anbd libraries have extension capabilities. Here are some that we
took inspiration from for xonsh:

* `Sphinx <http://sphinx-doc.org/>`_: Extensions are just Python modules,
  bundles some entensions with the main package, interface is a list of
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

If a module is in the ``xontrib`` namespace package, it can be refered to just
by its module name. If a module is in any other package, then it must be
refered to by its full package path, separated by ``.`` like you would in an
import statement.  Of course, a module in ``xontrib`` may be refered to
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

Exetnstions may also be loaded via the ``xontrib`` command, which is a xonsh
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


Tell Us About Your Xontrib!
===========================
x