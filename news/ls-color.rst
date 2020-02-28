**Added:**

* event on_lscolors_changed which fires when an item in $LS_COLORS changed.
* dict pyghooks.file_color_tokens containing color tokens for file types defined in $LS_COLORS.
* file pyproject.toml containing config rules for black formatter consistent with flake8

**Changed:**

* the feature list: subprocess mode colorizes files per $LS_COLORS, when they appear as arguments in the command line.
  Yet another approximation of ls -c file coloring behavior.
* file setup.cfg to declare flake8 rules for all tools (not just pytest)

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Modified base_shell._TeeStdBuf to feed bytes not str to console window under VS Code.

**Security:**

* <news item>
