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

When the "tab" key is pressed, xonsh loops over the completion functions in
order, calling each one in turn until it reaches one that returns a non-empty
set of completion for the current line.  This set is then displayed to the
user.


Listing Active Completers
=========================

A list of the active completers can be viewed by running the
``completer list`` command.  This command will display names and descriptions
of the currently-active completers, in the order in which they will be
checked.


Writing a New Completer
=======================

Completers are implemented as Python functions that take five arguments:

* ``prefix``: the string to be matched (the last whitespace-separated token in the current line)
* ``line``: a string representing the entire current line
* ``begidx``: the index at which ``prefix`` starts in ``line``
* ``endidx``: the index at which ``prefix`` ends in ``line``
* ``ctx``: the current Python environment, as a dictionary mapping names to values

This function should return a Python set of possible completions for ``prefix``
in the current context.  If the completer should not be used in this case, it
should return ``None`` or an empty set, which will cause xonsh to move on and
try to use the next completer.

Occasionally, completers will need to return a match that does not actually
start with ``prefix``.  In this case, a completer should instead return a tuple
``(completions, prefixlength)``, where ``completions`` is the set of
appropriate completions, and ``prefixlength`` is the number of characters in
``line`` that should be treated as part of the completion.

The docstring of a completer should contain a brief description of its
functionality, which will be displayed by ``completer list``.

Three examples follow.  For more examples, see the source code of the completers
xonsh actually uses, in the ``xonsh.completers`` module.

.. code-block:: python

    def dummy_completer(prefix, line, begidx, endidx, ctx):
        '''
        Completes everything with options "lou" and "carcolh",
        regardless of the value of prefix.
        '''
        return {"lou", "carcolh"}
    
    def python_context_completer(prefix, line, begidx, endidx, ctx):
        '''
        Completes based on the names in the current Python environment
        '''
        return {i for i in ctx if i.startswith(prefix)}

    def unbeliever_completer(prefix, line, begidx, endidx, ctx):
        '''
        Replaces "lou carcolh" with "snail" if tab is pressed after typing
        "lou" and when typing "carcolh"
        '''
        if 'carcolh'.startswith(prefix) and line[:begidx].split()[-1] == 'lou':
            return ({'snail'}, len('lou ') + len(prefix))


Registering a Completer
=======================

Once you have created a completion function, you can add it to the list of
active completers via the ``completer add`` command::

    Usage:
        completer add NAME FUNC [POS]

``NAME`` is a unique name to use in the listing

``FUNC`` is the name of a completer function to use.

``POS`` (optional) is a position into the list of completers at which the new completer should be added.  It can be one of the following values:

* ``"start"`` indicates that the completer should be added to the start of the list of completers (it should be run before all others)
* ``"end"`` indicates that the completer should be added to the end of the list of completers (it should be run after all others)
* ``">KEY"``, where ``KEY`` is a pre-existing name, indicates that this should be added after the completer named ``KEY``
* ``"<KEY"``, where ``KEY`` is a pre-existing name, indicates that this should be added before the completer named ``KEY``

If ``POS`` is not provided, it defaults to ``"start"``.

.. note:: It is also possible to manipulate ``__xonsh__.completers`` directly,
          but this is the preferred method.

Removing a Completer
====================

To remove a completer from the list of active completers, run
``completer remove NAME``, where ``NAME`` is the unique identifier associated
with the completer you wish to remove.
