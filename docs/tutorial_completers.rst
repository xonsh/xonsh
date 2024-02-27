.. _tutorial_completers:

*************************************
Tutorial: Programmable Tab-Completion
*************************************

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

.. code-block:: python

    # Helper decorators for completers:
    from xonsh.completers.tools import *

    @contextual_completer
    def dummy_completer(context):
        '''
        Completes everything with options "lou" and "carcolh",
        regardless of the value of prefix.
        '''
        return {"lou", "carcolh"}

    @non_exclusive_completer
    @contextual_completer
    def nx_dummy_completer(context):
        '''
        Like dummy_completer but its results are ADDED to the other completions.
        '''
        return {"lou", "carcolh"}

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

    >>> $XONSH_TRACE_COMPLETIONS = True
    >>> pip c<TAB>
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
