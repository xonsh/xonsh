**Added:**

* $LS_COLORS code 'mh' now recognized for (multi) hard-linked files.
* $LS_COLORS code 'ca' now recognized for files with security capabilities (linux only).

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* $LS_COLORS code 'fi' now used for "regular files", as it should have been all along. (was 'rs') 
  See (#3608)[https://github.com/xonsh/xonsh/issues/3608].
* pyghooks.color_files now follows implememntation of ls --color very closely.  Thanks @qwenger!
  Precedence of color for file with multiple matches improved; now follows only next symlink in a chain.

**Security:**

* <news item>