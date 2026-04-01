.. _keyboard_shortcuts:

******************
Keyboard Shortcuts
******************
Xonsh comes pre-baked with a few keyboard shortcuts. The following is only available under the prompt-toolkit shell.

Editing
-------

.. list-table::
    :widths: 40 60
    :header-rows: 1

    * - Shortcut
      - Description
    * - ``Shift-Left`` or ``Shift-Right``
      - Select one character in either direction.
    * - ``Ctrl-Shift-Left`` or ``Ctrl-Shift-Right``
      - Select one word in either direction.
    * - ``Ctrl-X + Ctrl-C``
      - Copy highlighted section.
    * - ``Ctrl-X + Ctrl-X``
      - Cut highlighted section.
    * - ``Ctrl-V``
      - Paste clipboard contents.
    * - ``Ctrl-Backspace`` or ``Ctrl-H``
      - Delete a single word (like ``Alt-Backspace``).
    * - ``Ctrl-X + Ctrl-E``
      - Open the current buffer in your default text editor.
    * - ``Ctrl-Right``
      - Complete a single auto-suggestion word.


Indentation
-----------

After selecting text with ``Shift`` and the arrow keys,
you can press ``Tab`` or ``Shift+Tab`` to add or remove indentation.

Execution
---------

.. list-table::
    :widths: 40 60
    :header-rows: 1

    * - Shortcut
      - Description
    * - ``Ctrl-J``
      - | Similar to enter in a few respects:
        | 1. Execute the current buffer.
        | 2. End and execute a multiline statement.
    * - ``Ctrl-M``
      - Same as ``Ctrl-J``.


Exit
----

Press ``Ctrl-D`` to exit xonsh and return to original terminal.
If not called by another terminal, then exit current terminal window.
Similar to ``exit``.
