**Added:**

* Note: all these fixes require changes in ``prompt-toolkit`` which have not been released.
  For now, merge `prompt-toolkit/python-prompt-toolkit#1259 <https://github.com/prompt-toolkit/python-prompt-toolkit/pull/1259>`_ for yourself,
  or install private build https://github.com/bobhy/python-prompt-toolkit/tree/space-for-menu.

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* Code in ``ptk_shell/completer.py`` that was attempting to enforce ``$COMPLETION_MENU_ROWS`` via
  internal hacks.

**Fixed:**

* ``$COMPLETION_MENU_ROWS`` now works as expected, even at bottom of screen.
* Multi-column completion menu no longer displays an empty line at the bottom of the menu.
  This row is used to display metadata about the selected completion and should not be
  displayed if none of the completions has metadata.
* ``$RIGHT_PROMPT, $BOTTOM_TOOLBAR`` and ``$PROMPT`` can now be cleared, once set in a session.
  To clear, set to ``""``, not ``None``.  (``None`` means leave the prior value unchanged to PTK.
  and ``""`` is consistant with new registered defaults for these environment variables, anyway.)

**Security:**

* <news item>
