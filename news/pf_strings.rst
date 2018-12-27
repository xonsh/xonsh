**Added:**

* New xonsh syntax ``pf`` strings -- combining path strings with f-strings.

  Usage:

  .. code-block:: bash
       gil@bad_cat ~ $ repos = 'github.com'
       gil@bad_cat ~ $ pf"~/{repos}"
       PosixPath('/home/gil/github.com')
       gil@bad_cat ~ $ pf"{$HOME}"
       PosixPath('/home/gil')
       gil@bad_cat ~ $ pf"/home/${'US' + 'ER'}"
       PosixPath('/home/gil')

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
