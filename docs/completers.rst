.. _completers:

***************************
Programmable Tab-Completion
***************************

Overview
================================

As with many other shells, xonsh ships with the ability to complete
partially-specified arguments upon hitting the "tab" key.

In Python-mode, pressing the "tab" key will complete based on the variable
names in the current builtins, globals, and locals, as well as xonsh language
keywords & operators, files & directories, and environment variable names. In
subprocess-mode, xonsh additionally completes based on the names of any
executable files on your $PATH, alias keys, and full Bash completion for the
commands themselves.

xonsh also provides a mechanism by which the results of a tab completion can be
customized (i.e., new completions can be generated, or a subset of the built-in
completions can be ignored).

This page details the internal structure of xonsh's completion system and
includes instructions for implementing new tab completion functions.


Structure
==========

xonsh's built-in completers live in the ``xonsh.completers`` package, and they
are managed through an instance of ``OrderedDict`` (``__xonsh__.completers``)
that maps unique identifiers to completion functions.

The completers are divided to **exclusive** completers and **non-exclusive** completers.
Non-exclusive completers are used for completions that are relevant but don't cover the whole completions needed
(e.g. completions for the built-in commands ``and``/``or``).

When the "tab" key is pressed, xonsh loops over the completion functions in
order, calling each one in turn and collecting its output until it reaches an **exclusive** one that returns a non-empty
set of completions for the current line. The collected completions are then displayed to the
user.


Listing Active Completers
=========================

A list of the active completers can be viewed by running the
``completer list`` command.  This command will display names and descriptions
of the currently-active completers, in the order in which they will be
checked.


Writing a New Completer
=======================

Completers are implemented as Python functions that take a :class:`Completion Context <xonsh.parsers.completion_context.CompletionContext>` object.
Examples for the context object:

.. code-block:: python

    # ls /tmp/<TAB>
    CompletionContext(
        command=CommandContext(
            args=(CommandArg(value='ls'),),
            arg_index=1, prefix='/tmp/',
            ),
        python=PythonContext(multiline_code="ls /tmp/", cursor_index=8, ctx={...})
    )

    # ls $(whic<TAB> "python") -l
    CompletionContext(
        command=CommandContext(
            args=(CommandArg(value='python', opening_quote='"', closing_quote='"'),),
            arg_index=0, prefix='whic', subcmd_opening='$(',
        ),
        python=None
    )

    # echo @(sys.exe<TAB>)
    CompletionContext(
        command=None,
        python=PythonContext(
            multiline_code="sys.exe", cursor_index=7,
            is_sub_expression=True, ctx={...},
        )
    )

.. note::
    Xonsh still supports legacy completers - see `Legacy Completers Support`_.
    For backwards-compatibility, contextual completers need to be marked (as seen in the examples).

This function should return a python set of possible completions for ``command.prefix``
in the current context.  If the completer should not be used in this case, it
should return ``None`` or an empty set, which will cause xonsh to move on and
try to use the next completer.

Occasionally, completers will need to return a match that does not actually
start with ``prefix``.  In this case, a completer should instead return a tuple
``(completions, prefixlength)``, where ``completions`` is the set of
appropriate completions, and ``prefixlength`` is the number of characters in
``line`` that should be treated as part of the completion.

.. note::
    Further completion customizations can be made using the ``RichCompletion`` object - see `Advanced Completions`_.

The docstring of a completer should contain a brief description of its
functionality, which will be displayed by ``completer list``.

Some simple examples follow.  For more examples, see the source code of the completers
xonsh actually uses, in the ``xonsh.completers`` module.

.. code-block:: xonshcon

    @ from xonsh.completers.tools import *

    @ @contextual_completer
      def dummy_completer(context):
          '''
          Completes everything with options "lou" and "carcolh",
          regardless of the value of prefix.
          '''
          return {"lou", "carcolh"}

    @ completer add dummy dummy_completer
    @ xzecze<TAB>   # → lou, carcolh

    @ @non_exclusive_completer
      @contextual_completer
      def nx_dummy_completer(context):
          '''
          Like dummy_completer but its results are ADDED to the other completions.
          '''
          return {"lou", "carcolh"}

    @ completer add nx_dummy nx_dummy_completer

.. code-block:: python

    @contextual_completer
    def python_context_completer(context):
        '''
        Completes based on the names in the current Python environment
        '''
        if context.python:
            last_name = context.python.prefix.split()[-1]
            return {i for i in context.python.ctx if i.startswith(last_name)}

    @contextual_completer
    def unbeliever_completer(context):
        '''
        Replaces "lou carcolh" with "snail" if tab is pressed after at least
        typing the "lou " part.
        '''
        if (
            # We're completing a command
            context.command and
            # We're completing the second argument
            context.command.arg_index == 1 and
            # The first argument is 'lou'
            context.command.args[0].value == 'lou' and
            # The prefix startswith 'carcolh' (may be empty)
            'carcolh'.startswith(context.command.prefix)
        ):
            return {'snail'}, len('lou ') + len(context.command.prefix)

    # Save boilerplate with this helper decorator:

    @contextual_command_completer_for("lou")
    def better_unbeliever_completer(command):
        """Like unbeliever_completer but with less boilerplate"""
        if command.arg_index == 1 and 'carcolh'.startswith(command.prefix):
            return {'snail'}, len('lou ') + len(command.prefix)

To understand how xonsh uses completers and their return values try
to set :ref:`$XONSH_TRACE_COMPLETIONS <xonsh_trace_completions>` to ``True``:

.. code-block:: console

    @ $XONSH_TRACE_COMPLETIONS = True
    @ pip c<TAB>
    TRACE COMPLETIONS: Getting completions with context:
    CompletionContext(command=CommandContext(args=(CommandArg(value='pip', opening_quote='', closing_quote=''),), arg_index=1, prefix='c', suffix='', opening_quote='', closing_quote='', is_after_closing_quote=False, subcmd_opening=''), python=PythonContext('pip c', 5, is_sub_expression=False))
    TRACE COMPLETIONS: Got 3 results from exclusive completer 'pip':
    {RichCompletion('cache', append_space=True),
     RichCompletion('check', append_space=True),
     RichCompletion('config', append_space=True)}



Registering a Completer
=======================

Once you have created a completion function, you can add it to the list of
active completers via the ``completer add`` command or ``xonsh.completers.completer.add_one_completer`` function::

    Usage:
        completer add NAME FUNC [POS]

``NAME`` is a unique name to use in the listing

``FUNC`` is the name of a completer function to use.

``POS`` (optional) is a position into the list of completers at which the new completer should be added.  It can be one of the following values:

* ``"start"`` indicates that the completer should be added to the start of the list of completers (
    it should be run before all other exclusive completers)
* ``"end"`` indicates that the completer should be added to the end of the list of completers (it should be run after all others)
* ``">KEY"``, where ``KEY`` is a pre-existing name, indicates that this should be added after the completer named ``KEY``
* ``"<KEY"``, where ``KEY`` is a pre-existing name, indicates that this should be added before the completer named ``KEY``

If ``POS`` is not provided, it defaults to ``"end"``.

.. note:: It is also possible to manipulate ``__xonsh__.completers`` directly,
          but this is the preferred method.

Removing a Completer
====================

To remove a completer from the list of active completers, run
``completer remove NAME``, where ``NAME`` is the unique identifier associated
with the completer you wish to remove.

Advanced Completions
====================

To provide further control over the completion, a completer can return a :class:`RichCompletion <xonsh.completers.tools.RichCompletion>` object.
Using this class, you can:

* Provide a specific prefix length per completion (via ``prefix_len``)
* Control how the completion looks in prompt-toolkit (via ``display``, ``description`` and ``style``) -
    use the ``jedi`` xontrib to see it in action.
* Append a space after the completion (``append_space=True``)


Completing Closed String Literals
---------------------------------
When the cursor is appending to a closed string literal (i.e. cursor at the end of ``ls "/usr/"``), the following happens:

1. The closing quote will be appended to all completions.
    I.e the completion ``/usr/bin`` will turn into ``/usr/bin"``.
    To prevent this behavior, a completer can return a ``RichCompletion`` with ``append_closing_quote=False``.
2. If not specified, lprefix will cover the closing prefix.
    I.e for ``ls "/usr/"``, the default lprefix will be 6 to include the closing quote.
    To prevent this behavior, a completer can return a different lprefix or specify it inside ``RichCompletion``.

So if you want to change/remove the quotes from a string, the following completer can be written:

.. code-block:: python

    @contextual_command_completer
    def remove_quotes(command):
        """
        Return a completer that will remove the quotes, i.e:
        which "python"<TAB> -> which python
        echo "hi<TAB> -> echo hi
        ls "file with spaces"<TAB> -> ls file with spaces
        """
        raw_prefix_len = len(command.raw_prefix)  # this includes the closing quote if it exists
        return {RichCompletion(command.prefix, prefix_len=raw_prefix_len, append_closing_quote=False)}


Completing Aliases
==================

You can attach a custom completer to a function alias using the
``@aliases.completer`` decorator:

.. code-block:: python

    def _complete_hello(command, alias):
        return {'world', 'there', 'xonsh'}

    @aliases.register
    @aliases.completer(_complete_hello)
    def _hello(args):
        echo @(args)

Now ``hello <TAB>`` will suggest ``world``, ``there``, and ``xonsh``.

You can also set the ``xonsh_complete`` attribute manually:

.. code-block:: python

    def _hello(args):
        echo @(args)

    _hello.xonsh_complete = lambda *a, **kw: {'world', 'there', 'xonsh'}
    aliases['hello'] = _hello

The completer function receives two keyword arguments:

* ``command``: the :class:`CommandContext <xonsh.parsers.completion_context.CommandContext>` for the current completion
* ``alias``: the resolved alias object

Command Completers (xompletions)
================================

xonsh includes a package called ``xompletions`` that provides tab-completions for
specific commands like ``pip``, ``gh``, ``cd``, etc. Each command gets its own Python
module inside the ``xompletions/`` directory.

How it works:

1. When the user presses TAB, the ``xompleter`` completer (registered as ``complete_xompletions``)
   extracts the command name from ``args[0]``.
2. It looks for a matching module in ``xompletions/`` — first by exact name, then by regex patterns.
3. If found, it calls the module's ``xonsh_complete(ctx)`` function.
4. The function returns completions or ``None`` (to let the next completer handle it).

Creating a command completer
----------------------------

To create a completer for a command, place a Python file named after the command
in any directory listed in ``$XONSH_COMPLETER_DIRS``. The file must contain
a ``xonsh_complete`` function:

.. code-block:: python

    # ~/.config/xonsh/completers/mycmd.py
    from xonsh.parsers.completion_context import CommandContext

    def xonsh_complete(ctx: CommandContext):
        """Completes mycmd subcommands."""
        if ctx.arg_index == 1:
            return {'start', 'stop', 'status'}

.. code-block:: xonsh

    $XONSH_COMPLETER_DIRS = ["~/.config/xonsh/completers"]

Now ``mycmd <TAB>`` will suggest ``start``, ``stop``, and ``status``.

xonsh also ships built-in completers in the ``xompletions/`` package (for ``pip``, ``gh``, ``cd``, etc.).

Handling command name variants with ``wrap``
--------------------------------------------

The file name must match the command name exactly (``gh.py`` for ``gh``).
On Windows, extensions like ``.exe`` are stripped automatically via ``$PATHEXT``,
so ``gh.exe`` will find ``gh.py``.

However, if a command has other name variants (e.g. ``pip3.11``, ``python3.12``),
the exact file name won't match. For these cases, you can register regex patterns
from your ``xonshrc`` or xontrib:

.. code-block:: python

    from xonsh.completers.commands import complete_xompletions as xmp
    xmp.wrap(r"\bmycmd(?:\d)*$", "mycmd")

This maps ``mycmd``, ``mycmd2``, ``mycmd3`` etc. to the ``mycmd`` completer module.

xonsh ships with built-in patterns for ``pip`` (covers ``xpip``, ``pip3.11``, ``pip.exe``)
and ``python`` (covers ``python3``, ``python3.12``, ``python.exe``).

Completing ``python -m <module>``
---------------------------------

When an alias resolves to ``python -m <module>`` (e.g. ``xpip`` → ``python -m pip``),
xonsh uses the ``xompletions/python.py`` completer to delegate to the module's completer.

The mapping is stored in ``PYTHON_MODULE_COMPLETERS`` and can be extended from xonshrc:

.. code-block:: python

    from xompletions.python import PYTHON_MODULE_COMPLETERS

    # Simple completer with static options
    def _complete_mytool(ctx, module_arg_index):
        return {'start', 'stop', 'status'}

    PYTHON_MODULE_COMPLETERS['mytool'] = _complete_mytool

Now ``python -m mytool <TAB>`` will suggest ``start``, ``stop``, and ``status``.
This also works through aliases:

.. code-block:: xonsh

    aliases['mt'] = ['python', '-m', 'mytool']
    mt <TAB>  # completes with start, stop, status

For modules that use the `argcomplete <https://github.com/kislyuk/argcomplete>`_ protocol,
a ready-made helper is available:

.. code-block:: python

    from xompletions.python import PYTHON_MODULE_COMPLETERS, _complete_argcomplete

    PYTHON_MODULE_COMPLETERS['my_argcomplete_tool'] = _complete_argcomplete


Emoji & Symbols
================

Need a 🐈 in your commit message? xonsh has a built-in emoji completer.
It is disabled by default. To enable, set the trigger prefixes:

.. code-block:: xonshcon

    @ $XONSH_COMPLETER_EMOJI_PREFIX = '::'
    @ $XONSH_COMPLETER_SYMBOLS_PREFIX = ':::'

Then type ``::`` followed by a keyword and press TAB to search for colorful
emoji::

    echo "great job ::fire<TAB>"   →  echo "great job 🔥"
    echo "::cat<TAB>"              →  echo "🐈"

For classic unicode symbols (arrows, math, stars), use ``:::``::

    echo ":::arrow<TAB>"  →  echo "→"
    echo ":::star<TAB>"   →  echo "★"

Set ``$XONSH_COMPLETER_EMOJI_PREFIX`` or ``$XONSH_COMPLETER_SYMBOLS_PREFIX``
to ``None`` to disable the corresponding completer.


Legacy Completers Support
=========================

Before completion context was introduced, xonsh had a different readline-like completion API.
While this legacy API is not recommended, xonsh still supports it.

.. warning::
    The legacy completers are less robust than the contextual system in many situations, for example:

    * ``ls $(which<TAB>`` completes with the prefix ``$(which``

    * ``ls 'a file<TAB>`` completes with the prefix ``file`` (instead of ``a file``)

    See `Completion Context PR <https://github.com/xonsh/xonsh/pull/4017>`_ for more information.

Legacy completers are python functions that aren't marked by ``@contextual_completer`` and receive the following arguments:

* ``prefix``: the string to be matched (the last whitespace-separated token in the current line)
* ``line``: a string representing the entire current line
* ``begidx``: the index at which ``prefix`` starts in ``line``
* ``endidx``: the length of the ``prefix`` in ``line``
* ``ctx``: the current Python environment, as a dictionary mapping names to values

Their return value can be any of the variations of the contextual completers'.
