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
* pyghooks.color_files now follows implememntation of ls --color closely.  Thanks @qwenger!
  However, a few documented differences remain due to use in Xonsh.
  Precedence of color for file with multiple matches improved; now follows only next symlink in a chain.
* $LS_COLORS['ln'] = 'target' now works.  Also fixes #3578.

**Security:**

* <news item>
