**Added:**

* <news item>

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Some of the bash completions scripts can change path starting with '~/' to `/home/user/` during autocompletion.
  xonsh `bash_completions` does not expect that, so it breaks autocompletion by producing paths like `~/f/home/user/foo`.
  After the fix if bash returns changed paths then `/home/user` prefix will be replaced with `~/`.

**Security:**

* <news item>
