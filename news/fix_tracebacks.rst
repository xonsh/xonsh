**Added:**

* Support for pythons sys.last_type, sys.last_value, sys.last_traceback.

**Changed:**

* Made stacktraces behave like in python, i.e. when something in user-provided code fails (both interactively and non-interactively), only that part is shown, and the (static) part of the stacktrace showing the location where the user code was called in xonsh remains hidden. When an unexpected exception occurs inside xonsh, everything is shown like before.
* run_compiled_code, run_script_with_cache, run_code_with_cache now return sys.exc_info() triples instead of throwing errors
* SyntaxError tracebacks now by default hide the internal parser state (like in python); set XONSH_DEBUG >= 1 to enable it again in interactive mode.
* run_code_with_cache takes a new parameter display_filename to override the filename shown in exceptions (this is independent of caching)

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* SyntaxErrors now get initialized with all available fields so that the error message can be formatted properly.
* Raising BaseException no longer causes Xonsh to crash (fix #4567)
* Exceptions in user code when using xonsh non-interactively no longer simply crash xonsh, rather a proper stacktrace is printed and also postmain() is called.
* Tracebacks will now show the correct filename (i.e. as in python) for interactive use "<stdin>", scripts read by stdin "<stdin>" and -c commands "<string>". (Instead of MD5 hashes as filenames or "<xonsh-code>")

**Security:**

* <news item>
