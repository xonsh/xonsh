.. _xontrib:

**********
Extensions
**********

Overview
========
xonsh is an extensible, user-patchable platform: third-party developers can
build and distribute their own extensions without going through the xonsh
release cycle, and end users can reshape any subsystem directly from their
:doc:`xonsh RC <xonshrc>` because every part of xonsh is a Python module.
In the xonsh ecosystem these extensions are called *xontribs*.

A xontrib can be:

* a set of aliases — plain strings, lists, or callable Python functions
* a tab-completer for a single command or a whole API
* a prompt field (e.g. battery, container, version-control, kubernetes)
* a handler for session events such as ``on_chdir``, ``on_postcommand``,
  or ``on_pre_prompt``
* a new environment variable or ``$XONSH_*`` setting
* a full subsystem — syntax-highlighting tokens, a history backend, an
  integration with an external tool, and so on

Search and Install Xontribs
===========================
Two good places to look for xontribs published by the community:

* `Awesome xontribs <https://xonsh.github.io/awesome-xontribs/>`_ — curated
  list of xontribs.
* `GitHub xontrib topic <https://github.com/topics/xontrib>`_ — every
  repository tagged with the ``xontrib`` topic on GitHub.


Listing Known Xontribs
======================
The ``xontrib`` command allows you to list the installed xontribs.
This command will report if they are loaded in the current session. To display this
information, pass the ``list`` action to the ``xontrib`` command:

.. code-block:: xonshcon

    @ xontrib list
    abbrevs             not-loaded          Expand command abbreviations while typing in the Xonsh shell.
    clp                 not-loaded          Copy output to clipboard. Cross-platform.
    cmd_done            not-loaded          Show long running commands durations in prompt with option to send notification when terminal is not focused.
    jedi                not-loaded          Use Jedi as xonsh's python completer.
    output_search       not-loaded          Get identifiers, paths, URLs and words from the previous command output and use them for the next command in xonsh shell
    pipeliner           not-loaded          Let your pipe lines flow thru the Python code in xonsh.
    prompt_starship     not-loaded          Starship cross-shell prompt in xonsh shell.
    sh                  not-loaded          Paste and run commands from bash, zsh, fish, tcsh in xonsh shell.

    @ xontrib info sh
    Name: sh
    Source: xontrib.sh at /Users/snail/.local/xonsh-env/lib/python3.14/site-packages/xontrib/sh.py
    Description: Paste and run commands from bash, zsh, fish, tcsh in xonsh shell.
    Loaded: no

For programmatic access, you may also have this command print a JSON formatted
string:

.. code-block:: xonshcon

    @ $(@json xontrib list --json)['abbrevs']
    {'name': 'abbrevs',
     'loaded': False,
     'auto': False,
     'module': 'xontrib.abbrevs',
     'description': 'Expand command abbreviations while typing in the Xonsh shell.'}

Loading Xontribs
================
Xontribs may be loaded in a few different ways: from your :doc:`xonsh RC <xonshrc>`,
dynamically at runtime with the ``xontrib`` command, or its Python API.

Extensions are loaded via the ``xontrib load`` command.
This command may be run from anywhere in your :doc:`xonsh RC <xonshrc>` or at any point
after xonsh has started up.

.. code-block:: xonsh

    xontrib load myext mpl mypkg.show

Pass ``-s`` (``--suppress-warnings``) to load every xontrib that is installed and
silently skip any name that isn't. Useful in a :doc:`xonsh RC <xonshrc>` that is shared across machines
where only a subset of xontribs is installed.

The same can be done in Python as well

.. code-block:: python

    from xonsh.xontribs import xontribs_load
    xontribs_load(['myext', 'mpl', 'mypkg.show'])

A xontrib can be unloaded from the current session using ``xontrib unload``

.. code-block:: xonsh

    xontrib unload myext mpl mypkg.show

Xontribs can use `setuptools entrypoints <https://setuptools.pypa.io/en/latest/userguide/entry_point.html?highlight=entrypoints>`_
to mark themselves available for autoloading using the below format.

.. code-block:: ini

    [options.entry_points]
    xonsh.xontribs =
        xontrib_name = path.to.the.module

Here the module should contain ``_load_xontrib_`` function as described above.

.. note::

    Please make sure that importing the xontrib module and calling ``_load_xontrib_`` is fast enough.
    Otherwise it will affect the shell's startup time.
    Any other imports or heavy computations should be done in lazy manner whenever possible.


Authoring Xontribs
==================
The fastest way to start a new xontrib is the
`xontrib-template <https://github.com/xonsh/xontrib-template>`_ repository —
a ready-to-publish skeleton, packaging metadata, and the entry point pre-wired for autoloading.

Structure
================
Xontribs are modules with some special functions written
in either xonsh (``*.xsh``) or Python (``*.py``).

Here is a template:

.. code-block:: python

    from xonsh.built_ins import XonshSession

    def _load_xontrib_(xsh: XonshSession, **kwargs) -> dict:
        """
        this function will be called when loading/reloading the xontrib.

        Args:
            xsh: the current xonsh session instance, serves as the interface to manipulate the session.
                 This allows you to register new aliases, history backends, event listeners ...
            **kwargs: it is empty as of now. Kept for future proofing.
        Returns:
            dict: this will get loaded into the current execution context
        """

    def _unload_xontrib_(xsh: XonshSession, **kwargs) -> dict:
        """If you want your extension to be unloadable, put that logic here"""

.. warning::

    The xontrib must implement ``_unload_xontrib_`` itself. If this function
    is not provided, any registered event handlers, environment variables,
    aliases, and completers will remain active after ``xontribs unload/reload``.

This _load_xontrib_() function is called after your extension is imported,
and the currently active :py:class:`xonsh.built_ins.XonshSession` instance is passed as the argument.

.. note::

    Xontribs without ``_load_xontrib_`` are still supported.
    But when such xontrib is loaded, variables listed
    in ``__all__`` are placed in the current
    execution context if defined.

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


You can also use the `xontrib template <https://github.com/xonsh/xontrib-cookiecutter>`_ to easily
create the layout for your xontrib package.


Tell Us About Your Xontrib!
===========================

To register a xontrib, create a ``PullRequest`` at
`awesome-xontribs <https://github.com/xonsh/awesome-xontribs>`_
repository. Also, if you use Github to host your code,
please add `xonsh <https://github.com/topics/xonsh>`_ and `xontrib <https://github.com/topics/xontrib>`_
to the topics.

All of this let's users know that your xontrib is out there, ready to be used.
Of course, you're under no obligation to register your xontrib.  Users will
still be able to load your xontrib, as long as they have it installed.

See also
========

* :doc:`events_tutorial` -- using events in xontribs
* :doc:`env` -- registering environment variables for your xontrib
* :doc:`completers` -- writing custom completers
* `Awesome-xontribs <https://github.com/xonsh/awesome-xontribs>`_ -- registry of community xontribs
* `Xontrib template <https://github.com/xonsh/xontrib-template>`_ -- quickstart template
