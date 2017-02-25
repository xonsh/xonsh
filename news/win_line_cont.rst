**Added:** 

* Line continuation backslashes are respected on Windows in PTK shell if
  the backspace is is preceded by a space. 

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** 

* Fixed bug where trailing backspaces on windows paths could be interpreted 
  as line continuations characters. Now line continuation characters must be
  preceeded by a space on Windows. This only applies to interactive to ensure 
  xonsh scripts are portable. 

**Security:** None
