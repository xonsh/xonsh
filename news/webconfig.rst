**Added:**

* New ``xonfig web`` command that launches a web UI (in your browser) that
  allows users to configure their ``$XONSH_COLOR_STYLE``, ``$PROMPT``, and
  loaded xontribs in an interactive way. This is the prefered way to initialize
  the ``~/.xonshrc`` file on a new system or for new users.  It supersedes the
  old ``xonfig wizard`` command.
* New ``xonsh.webconfig`` subpackage for creating and launching ``xonfig web``.
* Added ``localtime`` entry to the ``$PROMPT_FIELDS`` dictionary, allowing users
  to easily place the current time in their prompt. This can be formatted with
  the ``time_format`` entry of ``$PROMPT_FIELDS``, which defaults to ``"%H:%M:%S"``.
  These are implemented in the new ``xonsh.prompt.times`` module.
* The ``html`` module in ``xonsh.lazyimps`` was added to lazily import
  ``pygments.formatters.html``.
* New ``xonsh.pyghooks.XonshHtmlFormatter`` class that enables HTML formatting of
  xonsh color strings.

**Changed:**

* The ``xonsh.pyghooks.XonshLexer`` now inherits from ``Python3Lexer``,
  rather than ``PythonLexer``.
* ``xonsh.pyghooks.XonshStyle`` now presents the ``highlight_color`` and
  ``background_color`` from the underlying style correctly.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Minor typo fixes to xontrib descriptions.

**Security:**

* <news item>
