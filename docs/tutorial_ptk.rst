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
command.

We'll walk you though how to do this using ``prompt_toolkit`` tools to define
keybindings and warn you about potential pitfalls.

All of the code below can be entered into your `xonshrc <xonshrc.html>`_

The danger keys
===============

We can't and won't stop you from doing what you want, but in the interest of a
functioning shell, you probably shouldn't mess with the following keystrokes as
they have some important functions already assigned to them.

.. list-table::
    :widths: 2 2
    :header-rows: 1

    * - Keystroke
      - Default commmand
    * - Control J
      - <Enter>

Useful imports
==============

The first thing we need is a xonsh `event <events.html>`_. The `xonshrc
<xonshrc.html>`_ is loaded before the shell is fully initialized so we need to
delay the loading of our custom keybindings until after loading is finished.::

    from builtins import events

We also need a few ``prompt_toolkit`` tools::

    from prompt_toolkit.keys import Keys
    from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode

Custom keyload function
=======================

To load the keybindings after the shell is initialized, we define a function
that contains all of our custom keybindings and decorate it with the appropriate
event, in our case ``on_post_init``.

We'll start with a toy example that just inserts the text "hi" into the current line of the prompt::

    @events.on_post_init
    def custom_keybindings():
        handler = __xonsh_shell__.shell.key_bindings_manager.registry.add_binding

        @handler(Keys.ControlW)
        def say_hi(event):
            event.current_buffer.insert_text('hi')

Put that in your `xonshrc <xonshrc.html>`_, restart xonsh and then see if
pressing ``Ctrl-w`` does anything (it should!)

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
instance, the <TAB> key in xonsh brings up the completions menu, but then it
also cycles through the available completions. We use filters to create this
behavior.
