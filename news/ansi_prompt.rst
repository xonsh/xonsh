**Added:**

* Support for ANSI escape codes in ``$PROMPT``/``$RIGHT_PROMPT``. In this way 3rd party prompt generators like ``powerline`` or ``starship`` can be used to set the prompt. ANSI escape codes cannot be mixed with the normal formatting (like ``{BOLD_GREEN}``) but *prompt variables* (like ``{user}``) should work. 
  For example:
  ::

    $PROMPT=lambda: $(starship prompt)
    $RIGHT_PROMPT="\x1b[33m{hostname}"
  

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
