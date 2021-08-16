.. _keyboard_shortcuts:

******************
Keyboard Shortcuts
******************
Xonsh comes pre-baked with a few keyboard shortcuts. The following is only available under the prompt-toolkit shell.

.. list-table::
    :widths: 40 60
    :header-rows: 1

    * - Shortcut
      - Description
    * - Ctrl-Backspace (or Ctrl-H)
      - Delete a single word (like Alt-Backspace)
    * - Ctrl-X + Ctrl-E
      - Open the current buffer in your default text editor.
    * - Ctrl-D
      - Exit xonsh and return to original terminal. If not called by another terminal, then exit current terminal window. Similar to ``exit``.
    * - Ctrl-J
      - | Similar to enter in a few respects:
        | 1. Execute the current buffer.
        | 2. End and execute a multiline statement.
    * - Ctrl-M
      - Same as Ctrl-J
    * - Shift-Left OR Shift-Right
      - Highlight one character in either direction
    * - Ctrl-Shift-Left OR Ctrl-Shift-Right
      - Highlight one word in either direction
    * - Ctrl-X + Ctrl-C
      - Copy highlighted section
    * - Ctrl-X + Ctrl-X
      - Cut highlighted section
    * - Ctrl-V
      - Paste clipboard contents
    * - Ctrl-Right
      - Complete a single auto-suggestion word

