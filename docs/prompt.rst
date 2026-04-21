.. _prompt:

******
Prompt
******

Xonsh ships with two REPL engines. Historically, they have been referred to in xonsh
as “shells” or “prompts”, but they will likely be renamed in the future, as they are in fact
REPL (read–eval–print loop) engines that power all user interaction with the terminal. These are:

* **prompt-toolkit** or **ptk** (``$SHELL_TYPE='prompt_toolkit'``) — the recommended, full-featured
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
    @ $PROMPT = lambda: '{user}@{hostname}:{cwd} @> '
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

.. code-block:: python

    snail@home ~ @ $PROMPT_FIELDS['test'] = "hey"
    snail@home ~ @ $PROMPT = "{test} {cwd} @ "
    hey ~ @
    hey ~ @ import random
    hey ~ @ $PROMPT_FIELDS['test'] = lambda: random.randint(1,9)
    3 ~ @
    5 ~ @
    2 ~ @
    8 ~ @

Here is an example — a random emoji before the prompt character:

.. code-block:: python

    from xonsh.completers.emoji import get_emoji_cache
    $PROMPT_FIELDS['random_emoji'] = lambda: @.imp.random.choice(get_emoji_cache())[0]
    $PROMPT = $PROMPT.replace("{prompt_end}", "{random_emoji}{prompt_end}")

    snail@home ~ 🥗 @  # It helps to visually
    snail@home ~ 🍎 @  # identify lines
    snail@home ~ 🧀 @  # in your scrollback history

Environment variables and functions are also available with the ``$``
prefix.  For example:

.. code-block:: python

    snail@home ~ @ $PROMPT = "{$LANG} >"
    en_US.utf8 >

Note that some entries of the ``$PROMPT_FIELDS`` are not always applicable, for
example, ``curr_branch`` returns ``None`` if the current directory is not in a
repository. The ``None`` will be interpreted as an empty string.

But let's consider a problem:

.. code-block:: python

    snail@home ~/xonsh @ $PROMPT = "{cwd_base} [{curr_branch}] @ "
    xonsh [main] @ cd ..
    ~ [] @

We want the branch to be displayed in square brackets, but we also don't want
the brackets (and the extra space) to be displayed when there is no branch. The
solution is to add a nested format string (separated with a colon) that will be
invoked only if the value is not ``None``:

.. code-block:: python

    snail@home ~/xonsh @ $PROMPT = "{cwd_base}{curr_branch: [{}]} @ "
    xonsh [main] @ cd ..
    ~ @

The curly brackets act as a placeholder, because the additional part is an
ordinary format string. What we're doing here is equivalent to this expression:

.. code-block:: python

    " [{}]".format(curr_branch()) if curr_branch() is not None else ""


Multiline Prompt
================

When you enter a multi-line statement (``for`` loop, ``if`` block, etc.),
xonsh displays a continuation prompt on each subsequent line.  The pattern
is controlled by ``$MULTILINE_PROMPT`` (default ``" "``).

The value is repeated to fill the width of the main prompt.  It can be a
plain string, a string with color markup, or a callable:

.. code-block:: python

    prompt @ $MULTILINE_PROMPT = '~*'
    prompt @ for i in range(3):
    ~*~*~*~*     print(i)
    ~*~*~*~*

Both xonsh color keywords (``{RED}``) and ANSI escape codes (``\033[31m``)
are supported.


Callable with ``line_number`` and ``width``
-------------------------------------------

When ``$MULTILINE_PROMPT`` is a callable, it receives two keyword arguments:

* ``line_number`` — the line number of the continuation line.
  The main prompt is line 1, so the first continuation is ``line_number=2``.
* ``width`` — the visible width (in columns) of the main prompt.

This lets you render unique content per line, for example line numbers:

.. code-block:: python

    _ml_colors = ['{CYAN}', '{GREEN}', '{YELLOW}', '{BLUE}', '{PURPLE}', '{RED}']

    def _multiline(line_number, width):
        c = _ml_colors[line_number % len(_ml_colors)]
        return f'{c}{line_number:>{width - 2}}|{{RESET}} '

    $MULTILINE_PROMPT = _multiline

Result (each line is a different color)::

    prompt @
          2|    for i in range(5):
          3|        if i > 2:
          4|            print(i)
          5|

Existing callables that accept no arguments continue to work.


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

This will let you hook directly into the ``prompt_toolkit`` keybinding manager. It will not stop you from rendering your
prompt completely unusable, so tread lightly.

Control characters
------------------

Some `ASCII control characters <https://en.wikipedia.org/wiki/Control_character#In_ASCII>`_ are widely used,
and it is generally not recommended to override them. Additionally, certain keybindings are used by xonsh
and may affect functionality if changed.

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
bindings:

.. code-block:: python

    from prompt_toolkit.keys import Keys
    from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode

Custom keyload function
-----------------------

We need our additional keybindings to load after the shell is initialized, so we
define a function that contains all of the custom keybindings and decorate it
with the appropriate event, in this case ``on_ptk_create``.

We'll start with a toy example that just inserts the text "hi" into the current line of the prompt:

.. code-block:: python

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add(Keys.ControlW)  # or just "c-w" string
        def say_hi(event):
            event.current_buffer.insert_text('hi')

Put that in your :doc:`xonshrc`, restart xonsh and then see if
pressing ``Ctrl-w`` does anything (it should!)

What commands can keybindings run?
----------------------------------

Pretty much anything! Since we're defining these commands after xonsh has
started up, we can create keybinding events that run subprocess commands with
hardly any effort at all. If we wanted to, say, have a command that runs ``ls
-l`` in the current directory:

.. code-block:: python

    from prompt_toolkit.application import run_in_terminal

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add(Keys.ControlP)
        def run_ls(event):
            def _task():
                ls -l
            run_in_terminal(_task)


``run_in_terminal(func)`` (imported from ``prompt_toolkit.application``)
is the canonical ``prompt_toolkit`` idiom for running code that writes
to ``STDOUT`` from a keybinding. It temporarily hides the prompt, runs
your function (which can freely ``print`` or launch subprocesses), then
redraws the prompt — including ``$RIGHT_PROMPT`` and ``$BOTTOM_TOOLBAR``
— above the captured output. Do **not** use ``event.cli.renderer.erase()``
for this purpose: it resets the renderer's height bookkeeping and
``$BOTTOM_TOOLBAR`` (and sometimes ``$RIGHT_PROMPT``) will disappear
until the next keypress.

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
run only when there are fewer than ten files in a given directory. We just need a function that returns a Bool that matches that requirement and then we decorate it! And remember, those functions can be in xonsh-language, not just pure Python:

.. code-block:: python

    from prompt_toolkit.filters import Condition

    @Condition
    def lt_ten_files():
        return len(g`*`) < 10

.. note:: See `the tutorial section on globbing
          <tutorial.html#normal-globbing>`_ for more globbing options.

Now that the condition is defined, we can pass it as a ``filter`` keyword to a keybinding definition:

.. code-block:: python

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

Edit-mode filter
~~~~~~~~~~~~~~~~

A common use of filters is restricting a binding to a specific editing
mode — Emacs insert, Vi insert, or Vi navigation. ``prompt_toolkit``
ships ready-made filters for each; pass them as ``filter`` to
``bindings.add``:

.. code-block:: python

    from prompt_toolkit.filters import (
        EmacsInsertMode, ViInsertMode, ViNavigationMode,
    )

    @events.on_ptk_create
    def custom_keybindings(bindings, **kw):

        @bindings.add('c-l', filter=EmacsInsertMode())
        def ls_in_emacs_insert(event):
            def _task():
                ls -l
            run_in_terminal(_task)

        @bindings.add('c-l', filter=ViInsertMode() | ViNavigationMode())
        def ls_in_any_vi_mode(event):
            def _task():
                ls -l
            run_in_terminal(_task)

The same key (``Ctrl-L``) can be bound to different actions per mode —
``prompt_toolkit`` picks the binding whose ``filter`` is currently
true. Combine with custom ``Condition`` filters using ``&``, ``|``, ``~``
(as in ``ViInsertMode() & lt_ten_files``) for finer-grained rules.


Pre-filling the next command
============================

xonsh can pre-fill the prompt input for the next command using two environment
variables. This is useful for building interactive workflows, wizards, or
keybindings that prepare a command for the user to review and edit before running.

``$XONSH_PROMPT_NEXT_CMD``
--------------------------

Sets the text that will appear in the next prompt as editable input:

.. code-block:: python

    $XONSH_PROMPT_NEXT_CMD = 'git commit -m ""'

The next time the prompt appears, ``git commit -m ""`` will be pre-filled
and the user can edit it before pressing Enter.

**Cursor positioning:** Use the ``<cursor>`` marker to place the cursor at a
specific position:

.. code-block:: python

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
The user can accept it by pressing the right arrow key:

.. code-block:: xonshcon

    @ $XONSH_PROMPT_NEXT_CMD_SUGGESTION = 'git push origin main'

Unlike ``$XONSH_PROMPT_NEXT_CMD``, this does not pre-fill the input — it only
shows a suggestion that the user can accept or ignore.

Both variables are cleared automatically after being consumed by the prompt.


Virtual Environment in Prompt
-----------------------------

xonsh obeys the ``$VIRTUAL_ENV_DISABLE_PROMPT`` environment variable
`as defined by virtualenv <https://virtualenv.pypa.io/en/latest/how-to/usage.html#customize-prompt>`__.
If this variable is truthy, xonsh will *always* substitute an empty string
for ``{env_name}``. Note that unlike other shells,
``$VIRTUAL_ENV_DISABLE_PROMPT`` takes effect *immediately* after being set
--- it is not necessary to re-activate the environment.

xonsh also allows for an explicit override of the rendering of ``{env_name}``,
via the ``$VIRTUAL_ENV_PROMPT`` environment variable. If this variable is
set to a non-empty value, ``{env_name}`` will *always* render as its value,
regardless of whether a virtual environment is active. The value is used
as-is, without the usual ``{env_prefix}`` / ``{env_postfix}`` wrapping ---
*except* when it matches the name derived from ``$VIRTUAL_ENV`` (the
``prompt = ...`` field in ``<venv>/pyvenv.cfg`` or the venv directory
basename). In that case it is treated as an auto-populated value from
``activate.xsh`` and wrapped like the other sources, so the prompt reads
``(venv) user@host`` instead of ``venvuser@host``.
``$VIRTUAL_ENV_PROMPT`` is overridden by ``$VIRTUAL_ENV_DISABLE_PROMPT``.

When neither variable is set, ``{env_name}`` falls back to the active
environment's name --- determined, in order, from the ``prompt = ...`` field
in ``<venv>/pyvenv.cfg``, from the venv directory name, or from
``$CONDA_DEFAULT_ENV``. The detected name is wrapped in ``{env_prefix}`` and
``{env_postfix}`` (``(`` and ``) `` by default).

For example:

.. code-block:: python

    @ $PROMPT = '{env_name}@ '
    @ source env/bin/activate.xsh
    (env) @ $VIRTUAL_ENV_PROMPT = '~~ACTIVE~~ '
    ~~ACTIVE~~ @ $VIRTUAL_ENV_DISABLE_PROMPT = 1
    @ del $VIRTUAL_ENV_PROMPT
    @ del $VIRTUAL_ENV_DISABLE_PROMPT
    (env) @


.. _change_theme:

Color theme
===========

You can view the available styles by typing

.. code-block:: xonshcon

   @ xonfig styles                      # list styles
   @ xonfig colors paraiso-dark         # review how it looks
   @ $XONSH_COLOR_STYLE='paraiso-dark'  # set a new theme

Registering custom styles
-------------------------

If you aren't happy with the styles provided by us (and ``pygments``), you can create and register custom styles.

To do so, add something similar to your ``.xonshrc``:

.. code-block:: python

   from xonsh.tools import register_custom_style
   mystyle = {
       "Literal.String.Single": "#ff88aa",
       "Literal.String.Double": "#ff4488",
       "RED": "#008800",
   }
   register_custom_style("mystyle", mystyle, base="monokai")
   $XONSH_COLOR_STYLE = "mystyle"

You can check ``xonfig colors`` for the token names. The ``base`` style will be used as a fallback for styles you don't set - pick one from ``xonfig styles`` (``default`` is used if omitted).


OSC 7 — Working directory reporting
====================================

Xonsh automatically emits `OSC 7 <https://gitlab.freedesktop.org/terminal-wg/specifications/-/merge_requests/7>`_
escape sequences on every directory change and at shell startup. This is an
invisible signal that tells the terminal emulator what the current working
directory is.

Terminals use it for:

* Opening new tabs/splits in the same directory
* macOS Terminal.app session restoration after reboot
* Showing the path in the terminal title bar or tab

This works out of the box on most modern terminals including macOS Terminal.app,
iTerm2, GNOME Terminal, Windows Terminal, WezTerm, and Kitty. No configuration
is needed.


See also
========

* :doc:`envvars` -- prompt-related environment variables
* :doc:`events` -- prompt lifecycle events (``on_pre_prompt``, ``on_post_prompt``)
