.. _tutorial_events:

************************************
Tutorial: Events
************************************
What's the best way to keep informed in xonsh? Subscribe to an event!

Overview
========
Simply, events are a way for various pieces of xonsh to tell each other what's going on. They're
fired when something of note happens, eg the current directory changes or just before a command is
executed.

See the `event list <events.html>`_ for the core xonsh events.

Show me the code!
=================

This will add a line to a file every time the current directory changes (due to ``cd``, ``pushd``,
or several other commands):

.. code-block:: python

    @events.on_chdir
    def _add_to_file(olddir, newdir, **kw):
        with open('/tmp/.dirhist', 'a') as dh:
            print(newdir, file=dh)


Note that the event system is keyword only. Event handlers must match argument names and must have a
``**kw`` as protection against future changes.

Can I use this in my xontrib?
=============================

Yes! It's even easy! In your xontrib, you just have to do something like:

.. code-block:: python

    events.doc('myxontrib_on_spam', """
    myxontrib_on_spam(can: Spam) -> bool?

    Fired in case of spam. Return ``True`` if it's been eaten.
    """)

This will enable users to call ``help(events.myxontrib_on_spam)`` and get useful output.

Listing Registered Handlers
===========================

You can easily inspect which handlers are registered for each event by simply
printing the ``events`` object. This is useful for debugging and understanding
which xontribs are active.

.. code-block:: python

    @events.on_precommand
    def my_handler(cmd, **_):
        pass

    print(events)

This will produce output similar to the following:

.. code-block:: yaml

    on_lscolors_change:
      - xonsh.pyghooks.on_lscolors_change
    on_pre_spec_run_ls:
      - xonsh.environ.ensure_ls_colors_in_env
    on_precommand:
      - __main__.my_handler

To get this information programmatically, you can use the ``events.handlers()`` method,
which returns a dictionary mapping event names to a list of handler strings.

.. code-block:: python

    events.handlers()
    # {'on_lscolors_change': ['xonsh.pyghooks.on_lscolors_change'], ...}

Notes for developers
====================

- Handler call order is not guaranteed now.

- ``Event.fire()`` returns a list of the returns from the handlers. You should merge this list if it's needed.

- In xonsh, events come in species. Each one may look like an event and quack like an event, but they
  behave differently. This was done because load hooks look like events and quack like events, but they have different
  semantics. See `LoadEvents <api/events.html#xonsh.events.LoadEvent>`_ for details. In order to turn an event from
  the default ``Event``, you must transmogrify it, using ``events.transmogrify()``. The class the event is turned
  in to must be a subclass of ``AbstractEvent``. Under the hood, transmogrify creates a new instance and copies
  the handlers and docstring from the old instance to the new one.


Further Reading
===============

For a complete list of available events, see `the events reference <events.html>`_.

