**Added:**

* Support for more ANSI escape sequece modifers allowed in color names.
  The current modifiers now allowed are: BOLD, FAINT, ITALIC, UNDERLINE,
  SLOWBLINK, FASTBLINK, INVERT, CONCEAL, and STRIKETHROUGH.
* New ``ansi_tools.ansi_color_name_to_escape_code()`` function for
  converting a color name to an ANSI escape code.
* ``color_tools.RE_XONSH_COLOR`` is a regular expression for matching
  xonsh color names.
* ``color_tools.iscolor()`` is a simple function for testing whether a
  string is a valid color name or not.
* The ``tools.all_permutations()`` function yeilds all possible permutations
  of an iterable, including removals.

**Changed:**

* ANSI color styles may now defined simply by their plain and intense colors.
* ``SET_FOREGROUND_3INTS_`` renamed to ``SET_FOREGROUND_FAINT_``,
  ``SET_BACKGROUND_3INTS_`` renamed to ``SET_BACKGROUND_FAINT_``,
  ``SET_FOREGROUND_SHORT_`` renamed to ``SET_FOREGROUND_SLOWBLINK_``, and
  ``SET_BACKGROUND_SHORT_`` renamed to ``SET_BACKGROUND_SLOWBLINK_``.

**Deprecated:**

* <news item>

**Removed:**

* ``ansi_tools.ANSI_REVERSE_COLOR_NAME_TRANSLATIONS`` removed, as it is
  no longer needed.

**Fixed:**

* Fixed issues where ``$LS_COLORS`` could not convert valid ANSI colors.

**Security:**

* <news item>
