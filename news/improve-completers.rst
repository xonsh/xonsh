**Added:**

* RichCompletion for completions with different display value, description and prefix_len.
* Allow completer access to multiline document when available via ``xonsh.completers.tools.get_ptk_completer().current_document``.

**Changed:**

* Major improvements to Jedi xontrib completer:
    * Use new Jedi API
    * Replace the existing python completer
    * Create rich completions with extra info
    * Use entire multiline document if available
    * Complete xonsh special tokens
    * Be aware of _ (last result)
    * Only show dunder attrs when prefix ends with '_'

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Typo in 'source' alias.
* Crash in 'completer' completer.
* Don't complete unnecessarily in 'base' completer

**Security:**

* <news item>
