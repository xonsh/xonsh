.. _tutorial_ptk:

***********************************************
Tutorial: ``prompt_toolkit`` custom keybindings
***********************************************

Are you really jonesing for some special keybindings? We can help you out with
that. The first time is free and so is every other time!

.. warning:: This tutorial will let you hook directly into the
             ``prompt_toolkit`` keybinding manager. It will not stop you from
             rendering your prompt completely unusable, so tread lightly.


Overview
========

The ``prompt_toolkit`` shell has a registry for handling custom keybindings. You
may not like the default keybindings in xonsh, or you may want to add a new key
binding.

We'll walk you though how to do this using ``prompt_toolkit`` tools to define
keybindings and warn you about potential pitfalls.

All of the code below can be entered into your `xonshrc <xonshrc.html>`_

Control characters
==================

We can't and won't stop you from doing what you want, but in the interest of a
functioning shell, you probably shouldn't mess with the following keystrokes.
Some of them are `ASCII control characters
<https://en.wikipedia.org/wiki/Control_character#In_ASCII>`_ and *really*
shouldn't be used. The others are used by xonsh and will result in some loss of
functionality (in less you take the time to rebind them elsewhere).

.. list-table::
    :widths: 2 2 2
    :header-rows: 1

    * - Keystroke
      - ASCII control representation
      - Default command
    * - ``Control J``
      - ``<Enter>``
      - Run command
    * - ``Control I``
      - ``<Tab>``
      - Indent, autocomplete
    * - ``Control R``
      -
      - Backwards history search
    * - ``Control Z``
      -
      - SIGSTOP current job
    * - ``Control C``
      -
      - SIGINT current job


Useful imports
==============

There are a few useful ``prompt_toolkit`` tools that will help us create better
bindings::

    from prompt_toolkit.keys import Keys
    from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode

Custom keyload function
=======================

We need our additional keybindings to load after the shell is initialized, so we
define a function that contains all of the custom keybindings and decorate it
with the appropriate event, in this case ``on_ptk_create``.

We'll start with a toy example that just inserts the text "hi" into the current line of the prompt::

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add(Keys.ControlW)
        def say_hi(event):
            event.current_buffer.insert_text('hi')

Put that in your `xonshrc <xonshrc.html>`_, restart xonsh and then see if
pressing ``Ctrl-w`` does anything (it should!)

.. note:: It is also possible to write ``Keys.ControlW`` like ``c-w``.


What commands can keybindings run?
==================================

Pretty much anything! Since we're defining these commands after xonsh has
started up, we can create keybinding events that run subprocess commands with
hardly any effort at all. If we wanted to, say, have a command that runs ``ls
-l`` in the current directory::

    @handler(Keys.ControlP)
    def run_ls(event):
        ls -l
        event.cli.renderer.erase()


.. note:: The ``event.cli.renderer.erase()`` is required to redraw the prompt
          after asking for a separate command to send information to ``STDOUT``

Restrict actions with filters
=============================

Often we want a key command to only work if certain conditions are met. For
instance, the ``<TAB>`` key in xonsh brings up the completions menu, but then it
also cycles through the available completions. We use filters to create this
behavior.

A few helpful filters are included with ``prompt_toolkit``, like
``ViInsertMode`` and ``EmacsInsertMode``, which return ``True`` when the
respective insert mode is active.

But it's also easy to create our own filters that take advantage of xonsh's
beautiful strangeness. Suppose we want a filter to restrict a given command to
run only when there are fewer than ten files in a given directory. We just need a function that returns a Bool that matches that requirement and then we decorate it! And remember, those functions can be in xonsh-language, not just pure Python::

    @Condition
    def lt_ten_files(cli):
        return len(g`*`) < 10

.. note:: See `the tutorial section on globbing
          <tutorial.html#normal-globbing>`_ for more globbing options.

Now that the condition is defined, we can pass it as a ``filter`` keyword to a keybinding definition::

    @handler(Keys.ControlL, filter=lt_ten_files)
    def ls_if_lt_ten(event):
        ls -l
        event.cli.renderer.erase()

With both of those in your ``.xonshrc``, pressing ``Control L`` will list the
contents of your current directory if there are fewer than 10 items in it.
Useful? Debatable. Powerful? Yes.
