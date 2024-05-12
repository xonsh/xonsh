**Added:**

* Added ``$XONSH_SUBPROC_OUTPUT_FORMAT`` to switch the way to return the output lines.
  Default ``stream_lines`` to return text. Alternative ``list_lines`` to return
  the list of lines. Now you can run ``du $(ls)`` without additional stripping.
  Also supported custom lambda function to process lines (if you're looking for
  alternative to bash IFS).

**Changed:**

* Now the ending new line symbol ``\n`` will be stripped from the single line output.
  For ``$(whoami)`` you will get ``'user'`` instead of ``'user\n'``.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
