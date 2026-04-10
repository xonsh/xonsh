.. _prompt:

******
Prompt
******

xonsh ships with two prompt engines:

* **ptk** (``$SHELL_TYPE='prompt_toolkit'``) — the recommended, full-featured
  engine built on `prompt_toolkit <https://python-prompt-toolkit.readthedocs.io/>`_.
  It provides syntax highlighting, multi-line editing, completion menus, custom
  key bindings, and more. It is included when installing the full package
  (``pip install 'xonsh[full]'``).
* **readline** (``$SHELL_TYPE='readline'``) — a minimal fallback used when
  ptk cannot be started for some reason (for example, when ``prompt_toolkit``
  is not installed).

This page describes features and customization options of the
**ptk** engine. For the underlying library reference, see the
`prompt_toolkit official docs <https://python-prompt-toolkit.readthedocs.io/>`_.


.. _customprompt_ref:

Customizing the Prompt
======================

Customizing the prompt by modifying ``$PROMPT``, ``$RIGHT_PROMPT`` or
``$BOTTOM_TOOLBAR`` is probably the most common reason for altering an
environment variable.

The ``$PROMPT`` variable can be a string, or it can be a function (of no
arguments) that returns a string.  The result can contain keyword arguments,
which will be replaced automatically:

.. code-block:: xonshcon

    @ $PROMPT = '{user}@{hostname}:{cwd} @ '
    snail@home:~ @ # it works!
    snail@home:~ @ $PROMPT = lambda: '{user}@{hostname}:{cwd} @> '
    snail@home:~ @> # so does that!

By default, the following variables are available for use:

* ``user``: The username of the current user
* ``hostname``: The name of the host computer
* ``cwd``: The current working directory. Use ``$DYNAMIC_CWD_WIDTH`` to
  set a maximum width and ``$DYNAMIC_CWD_ELISION_CHAR`` for the elision character.
* ``short_cwd``: A shortened form of the current working directory; e.g.,
  ``/path/to/xonsh`` becomes ``/p/t/xonsh``
* ``cwd_dir``: The dirname of the current working directory, e.g. ``/path/to/``
* ``cwd_base``: The basename of the current working directory, e.g. ``xonsh``
* ``env_name``: The name of active virtual environment, if any.
* ``env_prefix``: Prefix characters for active virtual environment (default ``"("``).
* ``env_postfix``: Postfix characters for active virtual environment (default ``") "``).
* ``curr_branch``: The name of the current git branch, if any.
* ``branch_color``: ``{BOLD_GREEN}`` if the current git branch is clean,
  otherwise ``{BOLD_RED}``. Yellow if undetermined.
* ``branch_bg_color``: Like ``{branch_color}``, but sets a background color.
* ``prompt_end``: ``@#`` if the user has root/admin permissions, ``@`` otherwise.
* ``current_job``: The name of the command currently running in the foreground.
* ``gitstatus``: Informative git status, like ``[main|MERGING|+1…2]``.
  See :py:mod:`xonsh.prompt.gitstatus` for customization options.
* ``localtime``: The current local time, formatted with ``time_format``.
* ``time_format``: A time format string, defaulting to ``"%H:%M:%S"``.
* ``last_return_code``: The return code of the last issued command.
* ``last_return_code_if_nonzero``: The return code if non-zero, otherwise ``None``.

Colors
======

Xonsh supports colored output in prompts, ``print_color``, and ``printx``.
Color keywords such as ``{GREEN}`` or ``{BOLD_BLUE}`` can be used in prompt
strings and with color printing functions.

Color Names
-----------

* ``RESET``: Resets any previously used styling.
* ``COLORNAME``: Inserts a color code for the following basic colors,
  which come in regular (dark) and intense (light) forms:

    - ``BLACK`` or ``INTENSE_BLACK``
    - ``RED`` or ``INTENSE_RED``
    - ``GREEN`` or ``INTENSE_GREEN``
    - ``YELLOW`` or ``INTENSE_YELLOW``
    - ``BLUE`` or ``INTENSE_BLUE``
    - ``PURPLE`` or ``INTENSE_PURPLE``
    - ``CYAN`` or ``INTENSE_CYAN``
    - ``WHITE`` or ``INTENSE_WHITE``

* ``DEFAULT``: The color code for the terminal's default foreground color.
* ``#HEX``: A ``#`` before a len-3 or len-6 hex code will use that
  hex color, or the nearest approximation that that is supported by
  the shell and terminal.  For example, ``#fff`` and ``#fafad2`` are
  both valid.
* ``BACKGROUND_`` may be added to the beginning of a color name or hex
  color to set a background color.  For example, ``BACKGROUND_INTENSE_RED``
  and ``BACKGROUND_#123456`` can both be used.
* ``bg#HEX`` or ``BG#HEX`` are shortcuts for setting a background hex color.
  Thus you can set ``bg#0012ab`` or the uppercase version.

Color Modifiers
---------------

* ``BOLD_`` — increases font intensity. E.g. ``BOLD_RED``, ``BOLD_#112233``.
* ``FAINT_`` — decreases font intensity. E.g. ``FAINT_YELLOW``.
* ``ITALIC_`` — switches to italic. E.g. ``ITALIC_BLUE``.
* ``UNDERLINE_`` — adds underline. E.g. ``UNDERLINE_GREEN``.
* ``SLOWBLINK_`` — slow blinking text. E.g. ``SLOWBLINK_PURPLE``.
* ``FASTBLINK_`` — fast blinking text. E.g. ``FASTBLINK_CYAN``.
* ``INVERT_`` — swaps foreground and background. E.g. ``INVERT_WHITE``.
* ``CONCEAL_`` — hides text (may not be widely supported). E.g. ``CONCEAL_BLACK``.
* ``STRIKETHROUGH_`` — draws a line through text. E.g. ``STRIKETHROUGH_RED``.

Each modifier has an ``OFF`` variant to disable it: ``BOLDOFF_``, ``FAINTOFF_``,
``ITALICOFF_``, ``UNDERLINEOFF_``, ``BLINKOFF_``, ``INVERTOFF_``, ``CONCEALOFF_``,
``STRIKETHROUGHOFF_``.

Modifiers can be combined: ``BOLD_UNDERLINE_INTENSE_BLACK``.


Additional Prompt Variables
===========================

You can make use of additional variables beyond the defaults by adding them to
the ``PROMPT_FIELDS`` environment variable. The values in this dictionary should
be strings (which will be inserted into the prompt verbatim), or functions
(which will be called each time the prompt is generated, and the results
of those calls will be inserted into the prompt). For example:

.. code-block:: console

    snail@home ~ @ $PROMPT_FIELDS['test'] = "hey"
    snail@home ~ @ $PROMPT = "{test} {cwd} @ "
    hey ~ @
    hey ~ @ import random
    hey ~ @ $PROMPT_FIELDS['test'] = lambda: random.randint(1,9)
    3 ~ @
    5 ~ @
    2 ~ @
    8 ~ @

Here is an example — a random emoji before the prompt character::

    from xonsh.completers.emoji import _get_color_cache
    $PROMPT_FIELDS['random_emoji'] = lambda: @.imp.random.choice(_get_color_cache())[0]
    $PROMPT = $PROMPT.replace("{prompt_end}", "{random_emoji}{prompt_end}")

    snail@home ~ 🥗 @  # It helps to visually
    snail@home ~ 🍎 @  # identify lines
    snail@home ~ 🧀 @  # in your scrollback history

Environment variables and functions are also available with the ``$``
prefix.  For example:

.. code-block:: console

    snail@home ~ @ $PROMPT = "{$LANG} >"
    en_US.utf8 >

Note that some entries of the ``$PROMPT_FIELDS`` are not always applicable, for
example, ``curr_branch`` returns ``None`` if the current directory is not in a
repository. The ``None`` will be interpreted as an empty string.

But let's consider a problem:

.. code-block:: console

    snail@home ~/xonsh @ $PROMPT = "{cwd_base} [{curr_branch}] @ "
    xonsh [main] @ cd ..
    ~ [] @

We want the branch to be displayed in square brackets, but we also don't want
the brackets (and the extra space) to be displayed when there is no branch. The
solution is to add a nested format string (separated with a colon) that will be
invoked only if the value is not ``None``:

.. code-block:: console

    snail@home ~/xonsh @ $PROMPT = "{cwd_base}{curr_branch: [{}]} @ "
    xonsh [main] @ cd ..
    ~ @

The curly brackets act as a placeholder, because the additional part is an
ordinary format string. What we're doing here is equivalent to this expression:

.. code-block:: python

    " [{}]".format(curr_branch()) if curr_branch() is not None else ""


Custom Keybindings
==================

For the list of default key bindings shipped with xonsh, see
:doc:`keyboard_shortcuts`.

The ``prompt_toolkit`` shell has a registry for handling custom keybindings. You
may not like the default keybindings in xonsh, or you may want to add a new key
binding.

This section walks you through how to do this using ``prompt_toolkit`` tools to
define keybindings and warns you about potential pitfalls.

All of the code below can be entered into your :doc:`xonshrc`.

.. warning:: This will let you hook directly into the ``prompt_toolkit``
             keybinding manager. It will not stop you from rendering your
             prompt completely unusable, so tread lightly.

Control characters
------------------

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
--------------

There are a few useful ``prompt_toolkit`` tools that will help us create better
bindings::

    from prompt_toolkit.keys import Keys
    from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode

Custom keyload function
-----------------------

We need our additional keybindings to load after the shell is initialized, so we
define a function that contains all of the custom keybindings and decorate it
with the appropriate event, in this case ``on_ptk_create``.

We'll start with a toy example that just inserts the text "hi" into the current line of the prompt::

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add(Keys.ControlW)
        def say_hi(event):
            event.current_buffer.insert_text('hi')

Put that in your :doc:`xonshrc`, restart xonsh and then see if
pressing ``Ctrl-w`` does anything (it should!)

.. note:: It is also possible to write ``Keys.ControlW`` like ``c-w``.


What commands can keybindings run?
----------------------------------

Pretty much anything! Since we're defining these commands after xonsh has
started up, we can create keybinding events that run subprocess commands with
hardly any effort at all. If we wanted to, say, have a command that runs ``ls
-l`` in the current directory::

    from prompt_toolkit.application import run_in_terminal

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add(Keys.ControlP)
        def run_ls(event):
            def _task():
                ls -l
            run_in_terminal(_task)


.. note:: ``run_in_terminal(func)`` (imported from
          ``prompt_toolkit.application``) is the canonical
          ``prompt_toolkit`` idiom for running code that writes to
          ``STDOUT`` from a keybinding.  It temporarily hides the
          prompt, runs your function (which can freely ``print`` or
          launch subprocesses), then redraws the prompt — including
          ``$RIGHT_PROMPT`` and ``$BOTTOM_TOOLBAR`` — above the
          captured output.

          Do **not** use ``event.cli.renderer.erase()`` for this
          purpose: it resets the renderer's height bookkeeping and
          ``$BOTTOM_TOOLBAR`` (and sometimes ``$RIGHT_PROMPT``) will
          disappear until the next keypress.  See
          `xonsh/xonsh#5084
          <https://github.com/xonsh/xonsh/issues/5084>`_ for the
          underlying ``prompt_toolkit`` quirk.

Restrict actions with filters
-----------------------------

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

    from prompt_toolkit.filters import Condition

    @Condition
    def lt_ten_files():
        return len(g`*`) < 10

.. note:: See `the tutorial section on globbing
          <tutorial.html#normal-globbing>`_ for more globbing options.

Now that the condition is defined, we can pass it as a ``filter`` keyword to a keybinding definition::

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add(Keys.ControlL, filter=lt_ten_files)
        def ls_if_lt_ten(event):
            def _task():
                ls -l
            run_in_terminal(_task)

With both of those in your ``.xonshrc``, pressing ``Control L`` will list the
contents of your current directory if there are fewer than 10 items in it.
Useful? Debatable. Powerful? Yes.


Pre-filling the next command
============================

xonsh can pre-fill the prompt input for the next command using two environment
variables. This is useful for building interactive workflows, wizards, or
keybindings that prepare a command for the user to review and edit before running.

``$XONSH_PROMPT_NEXT_CMD``
--------------------------

Sets the text that will appear in the next prompt as editable input::

    $XONSH_PROMPT_NEXT_CMD = 'git commit -m ""'

The next time the prompt appears, ``git commit -m ""`` will be pre-filled
and the user can edit it before pressing Enter.

**Cursor positioning:** Use the ``<cursor>`` marker to place the cursor at a
specific position::

    $XONSH_PROMPT_NEXT_CMD = 'git commit -m "<cursor>"'

The marker is removed from the text and the cursor is placed at its position —
in this case, between the quotes.

**Example — a keybinding that prepares a git commit:**

.. code-block:: python

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add('c-g')
        def prepare_commit(event):
            $XONSH_PROMPT_NEXT_CMD = 'git commit -m "<cursor>"'

Now pressing ``Ctrl-G`` will pre-fill the next prompt with ``git commit -m ""``
and place the cursor between the quotes.

``$XONSH_PROMPT_NEXT_CMD_SUGGESTION``
-------------------------------------

Sets a greyed-out suggestion (like auto-suggest from history) for the next prompt.
The user can accept it by pressing the right arrow key::

    $XONSH_PROMPT_NEXT_CMD_SUGGESTION = 'git push origin main'

Unlike ``$XONSH_PROMPT_NEXT_CMD``, this does not pre-fill the input — it only
shows a suggestion that the user can accept or ignore.

Both variables are cleared automatically after being consumed by the prompt.




Virtual Environment in Prompt
-----------------------------

xonsh obeys the ``$VIRTUAL_ENV_DISABLE_PROMPT`` environment variable
`as defined by virtualenv <https://virtualenv.pypa.io/en/latest/reference/
#envvar-VIRTUAL_ENV_DISABLE_PROMPT>`__. If this variable is truthy, xonsh
will *always* substitute an empty string for ``{env_name}``. Note that unlike
other shells, ``$VIRTUAL_ENV_DISABLE_PROMPT`` takes effect *immediately*
after being set --- it is not necessary to re-activate the environment.

xonsh also allows for an explicit override of the rendering of ``{env_name}``,
via the ``$VIRTUAL_ENV_PROMPT`` environment variable. If this variable is
defined and has any value other than ``None``, ``{env_name}`` will *always*
render as ``str($VIRTUAL_ENV_PROMPT)`` when an environment is activated.
It will still render as an empty string when no environment is active.
``$VIRTUAL_ENV_PROMPT`` is overridden by ``$VIRTUAL_ENV_DISABLE_PROMPT``.

For example:

.. code-block:: xonshcon

    @ $PROMPT = '{env_name}@ '
    @ source env/bin/activate.xsh
    (env) @ $VIRTUAL_ENV_PROMPT = '~~ACTIVE~~ '
    ~~ACTIVE~~ @ $VIRTUAL_ENV_DISABLE_PROMPT = 1
    @ del $VIRTUAL_ENV_PROMPT
    @ del $VIRTUAL_ENV_DISABLE_PROMPT
    (env) @


