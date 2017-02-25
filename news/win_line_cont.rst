**Added:** 

* Line continuation backslashes are respected on Windows in the PTK shell if
  the backspace is is preceded by a space. 

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** 

* Fixed bug where trailing backspaces on Windows paths could be interpreted
  as line continuations characters. Now line continuation characters must be
  preceded by a space on Windows. This only applies to xonsh in interactive
  mode to ensure  scripts are portable. 

**Security:** None
