**Added:**

* New ``color_tools.KNOWN_XONSH_COLORS`` frozenset.
* New ``pyghooks.PYGMENTS_MODIFIERS`` mapping from color modifier names to
  pygments colors.
* New ``pyghooks.color_name_to_pygments_code()`` function for converting
  color names into pygments color codes.

**Changed:**

* Pygments styles only define the standard set of colors, by default.
  Additional colors are computed as needed.

**Deprecated:**

* <news item>

**Removed:**

* ``pyghooks.KNOWN_COLORS`` is no longer needed or useful as pygments colors
  are computed automatically.
* ``style_tools.KNOWN_COLORS`` was never used, redundant with
  ``pyghooks.KNOWN_COLORS`` and has thus been removed.

**Fixed:**

* <news item>

**Security:**

* <news item>
