**Fixed:**

* Subprocess-based completions like
  `xontrib-fish-completer <https://github.com/xonsh/xontrib-fish-completer>`_
  no longer append a space if the single available completion ends with
  a directory separator. This is consistent with the behavior of the
  default completer.