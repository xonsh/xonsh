**Added:**

* PTK style rules can be defined in custom styles using the ``Token.PTK`` token prefix.
  For example ``custom_style["Token.PTK.CompletionMenu.Completion.Current"] = "bg:#ff0000 #fff"`` sets the ``completion-menu.completion.current`` PTK style to white on red.
* Added new environment variable ``XONSH_STYLE_OVERRIDES``. It's a dictionary containing pygments/ptk style definitions that overrides the styles defined by ``XONSH_COLOR_STYLE``.
  For example::

    $XONSH_STYLE_OVERRIDES["Token.Literal.String.Single"] = "#00ff00"  # green 'strings' (pygments)
    $XONSH_STYLE_OVERRIDES["completion-menu"] = "bg:#ffff00 #000"  # black on yellow completion (ptk)
    $XONSH_STYLE_OVERRIDES["Token.PTK.CompletionMenu.Completion.Current"] = "bg:#ff0000 #fff" # current completion is white on red (ptk via pygments)


**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* ``PTK_STYLE_OVERRIDES`` has been removed, its function replaced by ``XONSH_STYLE_OVERRIDES``

**Fixed:**

* <news item>

**Security:**

* <news item>
