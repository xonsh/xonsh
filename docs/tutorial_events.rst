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

While xonsh has its own event system, it is not dissimilar to other event systems. If you do know
events, this should be easy to understand. If not, then this document is extra for you.

Show me the code!
=================
Fine, fine!

This will add a line to a file every time the current directory changes (due to ``cd``, ``pushd``,
or several other commands)::

    @events.on_chdir
    def add_to_file(olddir, newdir, **kw):
        with open(g`~/.dirhist`[0], 'a') as dh:
            print(newdir, file=dh)

The exact arguments passed and returns expected vary from event to event; see the
`event list <events.html>`_ for the details.

Note that the event system is keyword only. Event handlers must match argument names and must have a
``**kw`` as protection against future changes.

Can I use this, too?
====================

Yes! It's even easy! In your xontrib, you just have to do something like::

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

.. code-block:: console

    @events.on_precommand
    def my_handler(cmd, **_):
        pass

    print(events)

This will produce output similar to the following:

.. code-block:: text

    on_lscolors_change:
      - xonsh.pyghooks.on_lscolors_change
    on_pre_spec_run_ls:
      - xonsh.environ.ensure_ls_colors_in_env
    on_precommand:
      - __main__.my_handler

To get this information programmatically, you can use the ``events.handlers()`` method,
which returns a dictionary mapping event names to a list of handler strings.

.. code-block:: console

    events.handlers()
    # {'on_lscolors_change': ['xonsh.pyghooks.on_lscolors_change'], ...}

Further Reading
===============

For a complete list of available events, see `the events reference <events.html>`_.

If you want to know more about the gory details of what makes events tick, see
`Advanced Events <advanced_events.html>`_.
