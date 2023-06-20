====================
Xonsh Change Log
====================

.. current developments

v0.14.0
====================

**Added:**

* key_bindings: map `escape-f` as another word completer for macOS
* Added ``history pull`` command to SQLite history backend to pull the history from parallel sessions and add to the current session.
* Add support for `Semantic Prompt <https://gitlab.freedesktop.org/Per_Bothner/specifications/blob/master/proposals/semantic-prompts.md>`_ for line continuations in multiline prompts via two environment variables: ``$MULTILINE_PROMPT_PRE`` (e.g., ``\x01\x1b]133;P;k=c\x07\x02``), and ``$MULTILINE_PROMPT_POS`` (e.g., ``\x01\x1b]133;B\x07\x02``) that are inserted before/after each continuation line 'dots' block to mark input
* Wheels for Python 3.11 are part of the automated release action
* Added ``chdir`` to ``xonsh.tools``. This allows to use ``with chdir("dir"):`` to run commands block in the certain directory without manually cd-ing.
* Display the current branch of Fossil VCS checkouts in the prompt,
  similar to git and hg.
* Added link to xonsh on Mastodon - https://mastodon.online/@xonsh
* xontrib load: added option ``-s`` to skip warning about not installed xontribs.

**Changed:**

* Altered documentation for xonshrc to remove Python REPL prompts so that you can copy the code without having to edit it.
* xonsh AppImage - bumped python to 3.11
* The prompt end character switched to ``@``.
* The `command not found` error will show the ``repr(cmd)`` to uncover the cases when the command name has ``\n``, ``\t`` or not visible color codes and raises the error.
* ``abbrevs`` xontrib transferred to `xontrib-abbrevs <https://github.com/xonsh/xontrib-abbrevs>`_.
* ``bashisms`` xontrib transferred to `xontrib-bashisms <https://github.com/xonsh/xontrib-bashisms>`_.
* ``free_cwd`` xontrib transferred to `xontrib-free-cwd <https://github.com/xonsh/xontrib-free-cwd>`_.
* ``whole_word_jumping`` xontrib transferred to `xontrib-whole-word-jumping <https://github.com/xonsh/xontrib-whole-word-jumping>`_.
* ``fish_completer`` xontrib transferred to `xontrib-fish-completer <https://github.com/xonsh/xontrib-fish-completer>`_.
* ``vox``, ``autovox``, ``voxapi`` xontribs transferred to `xontrib-vox <https://github.com/xonsh/xontrib-vox>`_.
* ``pdb``, ``xog`` xontribs transferred to `xontrib-debug-tools <https://github.com/xonsh/xontrib-debug-tools>`_.

**Fixed:**

* Fixed xpip alias for xonsh AppImage.
* Fixed missing ``webconfig/js/xonsh_sticker.svg`` in ``xonfig web``.
* update load_xontrib pytest fixture to handle auto-loaded xontribs
* Suppress subprocess traceback on exception in case ``$XONSH_SHOW_TRACEBACK=False`` with ``$RAISE_SUBPROC_ERROR=True``.
* Improve the error message when ``$RAISE_SUBPROC_ERROR`` is set to True.
* Fixed xontrib-jupyter to work in JupyterLab and terminal-based `Euporie <https://github.com/joouha/euporie>`_ environment.

**Authors:**

* Gil Forsyth
* Noortheen Raja
* anki-code
* pre-commit-ci[bot]
* Evgeny
* Mark Bestley
* Samuel Dion-Girardeau
* doronz88
* Ivan Ogasawara
* Tobias Becker
* AkshayWarrier
* Thomas Hess
* kouhe3



v0.13.4
====================

**Added:**

* tests for methods changed in tools.py (is_tok_color_dict)
* ``$XDG_CACHE_HOME``, ``$XONSH_CACHE_DIR`` are now available inside ``Xonsh``
* #2455 Add `on_command_not_found` event, fired when a command is not found.

**Changed:**

* is_str_str_dict changed to check for Token:style dict

**Removed:**

* ``$COMMANDS_CACHE_SIZE_WARNING`` is removed. When ``$COMMANDS_CACHE_SAVE_INTERMEDIATE`` is enabled,
  the cache file size is optimized.

**Fixed:**

* #4668 Fix ptk completion stacking when auto-suggest is on and no normal completions are generated.
* $XONSH_STYLE_OVERRIDES cannot be assigned dict of {Token: str} #4375
* commands_cache: add a configurable value to disable cache. useful for running scripts
* fixed stale results when ``$COMMANDS_CACHE_SAVE_INTERMEDIATE`` is enabled.
*  #4951 Fix gitstatus prompt when rebasing
* fixed using aliases to override commands without the file extension on Windows
* #3279 Add `XONSH_HISTORY_IGNORE_REGEX` support. You can specify a regular
  expression in the environment variable `XONSH_HISTORY_IGNORE_REGEX` and any
  command that matches the expression will not be added to the history.

**Authors:**

* Noortheen Raja
* pre-commit-ci[bot]
* Vasilis Gerakaris
* Lie Ryan
* Blake Ramsdell
* Justin
* yotamolenik
* austin-yang
* Marco Rubin
* Qyriad



v0.13.3
====================

**Fixed:**

* ``pygments`` startup crash when incorrect prepending ``bg:`` to ``noinherit``
  style directives

**Authors:**

* Gil Forsyth



v0.13.2
====================

**Changed:**

* When there is no git repository, the values of all ``gitstatus`` prompt fields are now ``None``.
* With ``$THREAD_SUBPROCS=False``: When a callable alias is executed with ``![]``, its standard output and standard error are no longer captured. This is because a separate thread is required in order to both capture the output and stream it to the terminal while the alias is running.

**Fixed:**

* Fixed timeit syntax error
* When there is no git repository, ``$PROMPT`` format strings like ``{gitstatus: hello {}}`` now work as expected.
* With ``$THREAD_SUBPROCS=False``: When ``cd`` is used with an invalid directory, the error message is now correctly displayed.
* Fixed case when xpip returns None instead of command.

**Authors:**

* anki-code
* Peter Ye
* pre-commit-ci[bot]
* Lie Ryan
* amukher3
* Ashish Kurmi



v0.13.1
====================

**Added:**

* The ujson (faster version of json) added to xonsh[full] package.

**Changed:**

* Bumped Python version in `xonsh.AppImage` to 3.10
* The terminal's title is updated with the current command's name even if the command is a captured command or a callable alias

**Fixed:**

* Warn and continue if a user without ``pygments`` tries to load an unknown style
* Fixed a bash completion bug when prefixing a file path with '<' or '>' (for redirecting stdin/stdout/stderr)
* Fixed a bash completion bug when completing a git branch name when deleting a remote branch (e.g. `git push origin :dev-branch`)
* A callable alias containing subprocess commands no longer freezes when piped to another command
* ``less`` no longer stops when a callable alias containing subprocess commands is piped into it
* ``gitstatus`` Prompt-field would be empty on paths without git setup.
* When using the sway window manager, ``swaymsg -t get_inputs`` no longer fails with the error "Unable to receive IPC response"
* The ``current_job`` variable now works as expected when used in ``$TITLE``

**Security:**

* ``xpip`` will never add ``sudo`` under any circumstances and will instead append ``--user`` as needed

**Authors:**

* Gil Forsyth
* Noortheen Raja
* anki-code
* Peter Ye
* pre-commit-ci[bot]
* Stefano Rivera
* jbw3
* jgart
* Michael Panitz (at Cascadia College)
* Tim Gates



v0.13.0
====================

**Removed:**

* The ``xonsh`` code-base is no longer amalgamated, so tracebacks should be
  human-readable without intervention.  This may have (minor) impacts on startup
  speed.

**Fixed:**

* Fix xontrib loading for `free_cwd`
* Fixed `whole_word_jumping` xontrib failing on Linux, conditional import of ``ptk_win32`` → Windows only
* Fixed error caused by unintialized Xonsh session env when using Xonsh as a library just for its Pygments lexer plugin.

**Authors:**

* Gil Forsyth
* Noortheen Raja
* anki-code
* Eddie Peters
* cmidkiff87
* Hannes Römer



v0.12.6
====================

**Fixed:**

* String literal concatenation now works with f-strings and path literals
* A SyntaxError is raised when string literal concatenation is attempted with literals of different types (e.g. str and bytes)

**Authors:**

* Gil Forsyth
* Noortheen Raja
* Peter Ye



v0.12.5
====================

**Added:**

* Support for f-glob strings (e.g. ``fg`{prefix}*```)
* Now xontribs support `loading and unloading <https://github.com/xonsh/xonsh/issues/4541>`_
  with functions ``_load_xontrib_(xsh: XonshSession, **kwargs) -> dict``,
  ``_unload_xontrib_(xsh: XonshSession, **kwargs) -> None`` defined in their module.
  `Updated doc <https://xon.sh/tutorial_xontrib.html>`_
* Added a special '$LAST_RETURN_CODE' environment variable to access the return code of the last issued command. (Only set during interactive use).
* New prompt-customization fields: 'last_return_code_if_nonzero', 'last_return_code'.
* Documented the HISTCONTROL ignorespace option

**Changed:**

* ![] now returns a HiddenCommandPipeline when run with a background command (e.g. `![sleep 10 &]`)
* Extended `whole_word_jumping` xontrib with matching bindings for
  `delete` and `backspace`. The `XONSH_WHOLE_WORD_CTRL_BKSP` environment
  variable can be set to `False` to avoid binding `control+backspace` in
  incompatible terminals.
* The default prompt (on unix-systems) now includes a red [<errorcode>] field in case a command failed.
* New docs theme ``furo``
* completions from fish are now filter based on the current prefix.

**Removed:**

* xontrib ``prompt_ret_code`` is now removed.
  Now the default prompt already shows the last-return-code when the previous command fails.
  Please use the new prompt fields ``last_return_code``, ``last_return_code_if_nonzero`` from
  the `PR <https://github.com/xonsh/xonsh/pull/4798>`_

**Fixed:**

* Using `fg` for commands started in the background (e.g. `![sleep 10 &]`) now works
* SIGHUP (instead of SIGKILL) is sent to unfinished jobs when exiting the shell. This allows the `nohup` command to work properly.
* `bg` now properly resumes jobs in the background
* ExecAlias now sets the returncode of a command correctly
* Empty/comment-only commands no longer get added to the history
* On prompt-toolkit, when there is a job like `sleep 500 &` running in the background, pressing Ctrl+D twice to force quit now works properly
* Environment Variables are now completed correctly when in quotes
* Silence spurious errors on exit due to out-of-order cleanup

**Authors:**

* Gil Forsyth
* Noortheen Raja
* Peter Ye
* dev2718
* dependabot[bot]
* Stefano Rivera
* Naveen
* jbw3
* Italo Cunha
* Timmy Welch



v0.12.4
====================

**Authors:**

* Gil Forsyth



v0.12.3
====================

**Changed:**

* fix: remove os.path.basename from _get_git_branch()
* now 3rd party xontrib list is maintained at `Awesome Xontribs <https://github.com/xonsh/awesome-xontribs/>`_ page.
  Going forward, new contributions will be updated here, making it not depending on `the xonsh release <https://github.com/xonsh/xonsh/issues/4679>`_.

**Removed:**

* Removed Python 3.7 support following `NEP0029 <https://numpy.org/neps/nep-0029-deprecation_policy.html>`_

**Fixed:**

* Dictionaries are now pretty-printed with their items in the correct order

**Authors:**

* Gil Forsyth
* Noortheen Raja
* Peter Ye
* doronz88
* Stefano Rivera



v0.12.2
====================

**Fixed:**

* Fixed completions for command argument paths after equal signs
* A trailing space no longer gets appended when tab-completing command arguments that involve equals signs. For example `dd sta` gets completed to `dd status=`, without a space space after the equals sign.
* regression on `gitstatus <https://github.com/xonsh/xonsh/pull/4771>`_ prompt is fixed now. It will display the value now instead of the name.
* `fixed <https://github.com/xonsh/xonsh/pull/4763>`_ ``vox rm`` crashing when user input is required

**Authors:**

* Gil Forsyth
* Noortheen Raja
* Peter Ye



v0.12.1
====================

**Fixed:**

* fixed regression issue in loading `xontrib-abbrevs <https://github.com/xonsh/xonsh/pull/4757>`_
* Allow xonsh to start gracefully even if modal cursors aren't in the available
  prompt_toolkit version

**Authors:**

* Gil Forsyth
* Noortheen Raja



v0.12.0
====================

**Added:**

* Added interface to complete any alias that has ``xonsh_complete`` attribute. It is a function with ``fn(**kwargs) -> Iterator[RichCompletion | str]`` signature.
* added ``$ALIAS_COMPLETIONS_OPTIONS_LONGEST`` to control showing options in completions
* added ``$CMD_COMPLETIONS_SHOW_DESC`` environment variable to control showing command completions with a description part.
* `completer complete` command is added to test current completions
* completions from man page will now show the description for the options if available.
* ``$XONSH_COMPLETER_DIRS`` to put command completers
* ``Aliases.register`` to register an alias function.
* Tracebacks are now printed in color if available (interactive session with shell that supports colors with pygments installed and $COLOR_RESULTS enabled)
* Added python's match statement for python >=3.10.
* Added support for the $SHLVL environment variable, typed as int, using bash's semantics.
* Python files with command completions can be put inside ``xompletions`` namespace package,
  they will get loaded lazily.
* `xontrib.fish_completer` is available to complete using `fish` shell.
* Support for pythons sys.last_type, sys.last_value, sys.last_traceback.
* added ``xonsh-uname`` command to ``xoreutils``
* auto-completion support for commands : ``source-foreign``, ``source-bash``, ``source-zsh``, ``source-cmd``
* added ``history transfer`` command to transfer history entries between backends.
* now ``$PROMPT_FIELDS`` is a custom class with method ``pick(field_name)`` to get the field value efficiently.
  The results are cached within the same prompt call.
* new class ``xonsh.prompt.base.PromptField`` to ease creating/extending prompt-fields
* **Sublime Text 4** extension to the Editors page.
* Support for the `virtualenv <https://virtualenv.pypa.io/en/20.0.1/extend.html#activation-scripts>`_ ``activate.xsh`` script is back! Ensure you create the virtualenv from the same python where xonsh is installed.
* vox new/create accepts a new ``--prompt`` argument, which is passed through to ``python -m venv``
* New set of commands and options to manage virtualenvs inspired from ``pew``

    * runin
    * runinall
    * new

        * ``--link`` : to associate venv with project directory
        * ``--temp`` : to create temporary virtualenvs

    * activate

        * now will cd into project directory if the venv is associated

    * toggle-ssp - toggle system site packages
    * project - manage project path associations
    * wipe - to quickly remove all user installed packages
* ``prompt.env.env_name`` is now aware of the "prompt" key in ``pyvenv.cfg`` - search order from first to last is: ``$VIRTUAL_ENV_PROMPT``, ``pyvenv.cfg``, ``$VIRTUAL_ENV``, $``CONDA_DEFAULT_ENV``
* new command ``vox upgrade``
* ``xonfig web`` can now update ``abbrevs/aliases/env-variables``.
* Added `xontrib-default-command <https://github.com/oh-my-xonsh/xontrib-default-command>` to xontrib list.
* new `xontrib-django <https://github.com/jnoortheen/xontrib-django>`_ for django management completions
* Added `xontrib-gruvbox <https://github.com/rpdelaney/xontrib-gruvbox>` to xontrib list.
* Added `xontrib-up <https://github.com/oh-my-xonsh/xontrib-up>` to xontrib list.

**Changed:**

* BREAKING CHANGE: ``/etc/xonshrc`` location for run control file has been deprecated in favor of ``/etc/xonsh/xonshrc``.
* Both ``*.xsh`` and ``*.py`` files inside ``$XONSHRC_DIR`` will get loaded now.
* Environment-variables of no predefined type or path environment variables are now represented as strings via the empty string.
* Made stacktraces behave like in python, i.e. when something in user-provided code fails (both interactively and non-interactively), only that part is shown, and the (static) part of the stacktrace showing the location where the user code was called in xonsh remains hidden. When an unexpected exception occurs inside xonsh, everything is shown like before.
* run_compiled_code, run_script_with_cache, run_code_with_cache now return sys.exc_info() triples instead of throwing errors
* SyntaxError tracebacks now by default hide the internal parser state (like in python); set XONSH_DEBUG >= 1 to enable it again.
* XonshError tracebacks now by default hide xonshs internal state; set XONSH_DEBUG >= 1 to enable it again.
* run_code_with_cache takes a new parameter display_filename to override the filename shown in exceptions (this is independent of caching)
* Update uptime lib by the last one from Pypi
* ``umask``, ``ulimit`` commands will not override the system's commands unless requested
* Xontribs that require other third party packages are moved to its own packages.
  The following xontribs are moved and can be loaded after install as usual

  * mpl
  * distributed
  * jupyter-kernel
  * jedi
* Xonsh adopts `NEP-0029 <https://numpy.org/neps/nep-0029-deprecation_policy.html>`_ in supporting Python versions.
* Privatise certain attributes of lexer/parser to minimise API surface
* Make `XSH.load` calls explicit (not in Execer)
* Make import hooks require Execer
* Simplified foreign functions
* Updated tutorial.rst to clarify use of time_format
* ``vox new`` will use default python version of the system rather than the one vox is run with
* ``xonfig web`` now shows latest xontribs available from ``xonsh.xontribs_meta``

**Removed:**

* ``$XONSH_GITSTATUS_*`` is removed
  since the prompt fields can be customized easily now individually.
* ``$XONSH_GITSTATUS_FIELDS_HIDDEN`` is removed.
  Please set hidden fields in ``$PROMPT_FIELDS['gitstatus'].hidden = (...)``
* Removed ``xonsh.ptk2`` module whcih was kept for some old packages sake. Now xonsh requires atleast ptk3 version.

**Fixed:**

* Some of the bash completions scripts can change path starting with '~/' to `/home/user/` during autocompletion.
  xonsh `bash_completions` does not expect that, so it breaks autocompletion by producing paths like `~/f/home/user/foo`.
  After the fix if bash returns changed paths then `/home/user` prefix will be replaced with `~/`.
* ``pip`` completer now handles path completions correctly
* SyntaxErrors thrown during compilation (i.e. not during parsing) now include the offending source line.
* If a .xsh file is imported, the resulting module will now always have an absolute \_\_file\_\_ attribute to be consistent with pythons behavior since python 3.4.
* ``$CONDA_DEFAULT_ENV`` is now respected when xonsh is run outside of conda.
* Fixed unpacking of dictionaries inside a dictionary
* Empty or comments only .xsh files can now be imported to align with pythons behavior.
* Fixed regex globbing for file paths that contain special regex characters (e.g. "test*1/model")
* Fixed list comprehension in return statement incorrectly being parsed as a subprocess command.
* Fixed the expansion of $XONSH_TRACEBACK_LOGFILE user paths (e.g. "~/log")
* Fixed DeprecationWarning when providing autocompletion for a non-callable type with ``(``
* OSC codes in ``$PROMPT`` is no longer removed when using ptk shell.
  These codes need to be escaped with ``\001..\002`` instead.
* Attempt to show a modal cursor in vi_mode (ie. block in cmd, bar in ins)
* Xonsh can now be used in VIM (e.g. by ":read !ls" if VIM is configured to use xonsh. This may be the case when xonsh is the default shell.)
* Fixed OSError on Windows when GnuWin32 is installed in the PATH.
* Do not show welcome message when any ``$XONSHRC_DIR`` directory entry exists.
* SyntaxErrors now get initialized with all available fields so that the error message can be formatted properly.
* Raising BaseException no longer causes Xonsh to crash (fix #4567)
* Exceptions in user code when using xonsh non-interactively no longer simply crash xonsh, rather a proper stacktrace is printed and also postmain() is called.
* Tracebacks will now show the correct filename (i.e. as in python) for interactive use "<stdin>", scripts read by stdin "<stdin>" and -c commands "<string>". (Instead of MD5 hashes as filenames or "<xonsh-code>")
* Default ZSH FUNCSCMD was not working in ZSH 5.8 (and possibly other versions)
* Passing multiple files to be sourced to source-foreign was broken
* prompt field ``current_branch`` will now work empty git repository.

**Authors:**

* Gil Forsyth
* Noortheen Raja
* anki-code
* Daniel Shimon
* Peter Ye
* Jason R. Coombs
* dev2718
* Evgeny
* Angus Hollands
* omjadas
* Oliver Bestwalter
* Samuel Dion-Girardeau
* Ryan Delaney
* E Pluribus Unum
* ylmrx
* Hierosme
* Kyllingene
* zzj
* Daniel
* Ganer
* mattmc3
* Evan Hubinger



v0.11.0
====================



v0.11.0
====================

**Added:**

* added new utility classes ``xonsh.cli_utils.ArgParserAlias``, ``xonsh.cli_utils.ArgCompleter``.
  These are helper classes, that add coloring and auto-completion support to the alias-commands.
* when ``$ENABLE_ASYNC_PROMPT=True`` lazy load ``prompt-toolkit``'s color-input support.
* Add ``CTRL-Right`` key binding to complete a single auto-suggestion word.
* Show environment variables' type and descriptions when completing them.
* Add ``CTRL-Backspace`` key binding to delete a single word via ``$XONSH_CTRL_BKSPC_DELETION``.
* Improved ``pip``/``xpip`` completer.
* Separator used by gitstatus can now be styled using ``XONSH_GITSTATUS_SEPARATOR``.
* Complete 'import' statements with modules that aren't loaded.
* Complete multiple modules/objects in 'import' statements.
* Multiple new metadata fields in ``setup.py``
* Pure Python control files are now supported when named ``*.py``.
  Using python files may lower the startup time by a bit.
* new environment variable ``$XONSH_TRACE_SUBPROC_FUNC``
  to handle ``$XONSH_TRACE_SUBPROC`` output
* Added `xontrib-pyrtn <https://github.com/dyuri/xontrib-pyrtn>` to xontrib list.

**Changed:**

* Display error message when running `xonfig colors` in a non-interactive shell
* Using ``ArgparserAlias`` for ``dirs``, ``popd``, ``pushd``
* use ``ArgparserAlias`` for ``disown`` alias with completion support
* ``history`` alias now has colored help message and completion support when running interactively.
* using ``ArgparserAlias`` for ``trace`` alias with completion support
* improve ``vox`` CLI completions
* use ArgparserAlias for ``xexec``. Now it supports completions.
* ``xonfig`` now has colored help message when ran interactively.
* Using ``ArgparserAlias`` to improve ``xontrib`` completions
* Changed !() to also capture background subprocesses
* Suggested commands are cached for better performance.
* Improved pipelines performance by using a mutable buffer.
* Curly braces { } in directory names are now escaped in the prompt
* The ``--rc`` argument is extended to support directories as well as files.
  Passing a directory will result in all ``*.xsh`` files in the directory being
  sorted and loaded at startup (equivalent to using the environment variable
  ``XONSHRC_DIR``).
* The environment variables ``XONSHRC`` and ``XONSHRC_DIR`` are no longer updated by xonsh on
  startup according to which files were actually loaded. This caused problems if xonsh is called
  recursively, as the child shells would inherit the modified startup environment of the parent.
  These variables will now be left untouched, and the actual RC files loaded (according to those
  variables and command line arguments) can be seen in the output of ``xonfig``.
* Replaced `xontrib-linuxbrew <https://github.com/eugenesvk/xontrib-linuxbrew>`_ with `xontrib-homebrew <https://github.com/eugenesvk/xontrib-homebrew>`_, which also supports Homebrew on macOS

**Removed:**

* Completely dropped the deprecated ``--config-path`` argument, which no longer
  did anything.
* The environment variable ``LOADED_RC_FILES`` is no longer set. It contained a list of booleans
  as to which RC files had been successfully loaded, but it required knowledge of the RC loading
  internals to interpret which status corresponded to which file. As above, the (successfully)
  loaded RC files are now shown in ``xonfig``.

**Fixed:**

* Add quotes in autocomplete when filename contains brackets
* Handle ``None`` value on XSH.env if ``$UPDATE_OS_ENVIRON`` is set to ``True``
* Implemented `__hash__` method to Env, so that it can be used in `lru_cache` without crashing.
* Make sure aliases are always captured regardless of ``$XONSH_CAPTURE_ALWAYS``
* ``fromdircolors`` doesn't crash if output from subprocess call to ``dircolors`` returns
  nothing (usually due to permission errors)
* Fixed issue with environment not being iterable on session objects.
* Fixed issue where environment is None in commands cache.
* ``${...}.swap()`` can be called from multiple threads safetly.
* Piping multiple function aliases doesn't raise a recursion error anymore.
* Fixed detection of App Execution Alias for latest 3.8 and 3.9 releases
* ``Jedi`` completer doesn't complete paths with ``~``.
* Sometimes the completion menu doesn't take space when cursor is at the bottom of the screen.
* vox now passes system-site-packages option
* Fix Duplicate paths left over when add paths to Path via xonsh.tools.EnvPath
* Fix  Crash with FileNotFoundError when current working directory is deleted #4467
* Completing a single-arg python code segment (e.g. ``@(/etc/hos<TAB>)``).
* Fixed pipelines in WSL2
* Newline symbols in Prompt-toolkit's completions are replaced by <space>
* Fix launching processes on Windows by using full paths (https://bugs.python.org/issue8557)



v0.10.1
====================

**Fixed:**

* ``execx`` and ``xonsh -c`` previously exposed xonsh-internal code in global scope. They also did not support defining variables and then referring to them in comprehensions, generators, functions, or lambdas. - https://github.com/xonsh/xonsh/issues/4363
* Short color token names can be used in ``register_custom_style()`` (#4339)

**Authors:**

* Gyuri Horak
* Jeremy Schlatter



v0.10.0
====================

**Added:**

* Added ability to set XONSH_HISTORY_FILE before loading the history backend.
* Added ability to get the arguments list in ExecAlias using ``$args`` and ``$arg<n>`` environment variables.
* Added instruction how to run xonsh AppImage on Alpine
* Xonsh now supports generators as completer functions.
* Completion Context - Allow completers to access a parsed representation of the current commandline context.
* Added casting CommandPipeline to int, hash and str.
* Ability to call the tool by the name from callable alias with the same name without the infinite loop error.
* ``on wsl`` field when running xonfig (when linux is detected)
* Help and superhelp (``obj?`` and ``obj??``) now use the ``__name__`` if available.
* added ``$XONSH_GITSTATUS_FIELDS_TO_HIDE`` to hide unwanted fields from ``{gitstatus}`` prompt field.
* Added number of lines added and removed to gitstatus
* Saving current working directory (cwd) to the history.
* Added XONSH_HISTORY_SAVE_CWD environment variable.
* Added environment variable ``$COMPLETE_DOTS`` to specify how current and previous directories should be tab completed in cd  ('./', '../'):
    - ``always`` Always complete paths with ./ and ../
    - ``never`` Never complete paths with ./ and ../
    - ``matching`` Complete if path starts with . or ..
* Complete ``import`` keyword in ``from ... import`` statements.
* Enabled case-insensitive completions for the ``jedi`` xontrib.
* Non-exclusive completers that enable aggregating multiple completer results.
* New ``$XONSH_CAPTURE_ALWAYS`` variable for opt-in interactive capturing.
  Since this capturing breaks background jobs and some interactive programs (like ``git`` invoking an editor),
  This behavior is now opt-in using this variable.
  See https://github.com/xonsh/xonsh/pull/4283 and linked issues.
* Wrap selection with quote/parens when ``$XONSH_AUTOPAIR=True``.
* Now xonsh will work with Python 3.10. (Match statement is not supported).
* In addition to reading single rc files at startup (``/etc/xonshrc``, ``~/.config/xonsh/rc.xsh``),
  xonsh now also supports rc.d-style config directories, from which all files are sourced. This is
  designed to support drop-in style configuration where you could, for example, have a common config
  file shared across multiple machines and a separate machine specific file.

  This is controlled by the environment variable ``XONSHRC_DIR``, which defaults to
  ``["/etc/xonsh/rc.d", "~/.config/xonsh/rc.d"]``. If those directories exist, then any ``xsh`` files
  contained within are sorted and then sourced.
* Added xontrib-prompt-starship - Starship prompt in xonsh shell.
* Added XONSH_SUBPROC_CAPTURED_PRINT_STDERR (default False) environment variable to hide unwanted printing the stderr when using captured object.
* A ``$XONSH_TRACE_COMPLETIONS`` variable for completions debugging.
* Added warning about prompt-toolkit in the welcome message.
* Added history backend name to the xonfig.
* `xontrib-linuxbrew <https://github.com/eugenesvk/xontrib-linuxbrew>`_ to add Homebrew's shell environment to xonsh shell on Linux
* Added xontrib-macro-lib - the library of the useful macros for the xonsh shell: https://github.com/anki-code/xontrib-macro-lib

**Changed:**

* update imphooks encoding regex to match the newer version at PEP 263
* Enabled bracketed paste mode for readline to protect against paste jacking
* The group of environment variables around history moved to the "Interactive Prompt History" section.
* Disabled completing subpaths for commands in ``jedi``.
* Improved ``which`` output for non-simple aliases
* New json history will be in XONSH_DATA_DIR/history_json directory.
* Completers for ``and/or``, ``&&/||/|`` and environment variables are now non-exclusive.
* Disabled ptk copying words/lines to clipboard on deletion (can be re-enabled with ``$XONSH_COPY_ON_DELETE``).
* Separated between ``XONSH_DEBUG`` and ``XONSH_NO_AMALGAMATE``. Setting ``XONSH_DEBUG=1`` now acts like ``XONSH_DEBUG=2`` before (basic information like input transformation, command replacement) and ``XONSH_DEBUG=2`` like ``XONSH_DEBUG=1`` before (more debugging information presented, like PLY parsing messages).
* Cleaned up available aliases for ``shell_type``
* Speedup commands-cache by saving results between runs and use the last run's result
* The ``completer add`` command after the non-exclusive completers.
  This means it will not block them from adding their completions.
* Updated the tab-completion tutorial.

**Fixed:**

* handle importing/decoding user modules with a 'UTF-8 with BOM' encoding (#4160)
* Fixed XONSH_HISTORY_FILE that has the actual path from the history backend now
* Annotated assignments (``x: int = 42``, ``x: int``).
* Fixed xpip sudo behavior in xonsh AppImage.
* Prevent cancelled future errors for async prompt ($ENABLE_ASYNC_PROMPT) fields from bubbling up (and destroying the prompt's formatting)
* $() no longer silently captures stderr
* Added catching callable argument and raising appropriate exception
* Crashing command-not-found output for bad file names on linux.
* Fixed error message when an empty command is run
* Fixed @$ crash when no output is sent out by the command
* Fixed xonsh crash when launched using `xonsh -c '$("")'`
* now abbrevs callback will not remove word from ``buffer.text``. See https://github.com/xonsh/xonsh/issues/3642#issuecomment-793789741
* Fixed the incorrect SyntaxError that was thrown when a subprocess command was preceded by a comment ending with a colon
* Fixed the missing auto-indentation in readline and prompt_toolkit when a statement ending with a colon was followed by a comment
* Fixed the incorrect auto-indentation in prompt_toolkit when a comment ended with a colon
* Fixed JSON history garbage collection for XONSH_HISTORY_SIZE in seconds.
* Fixed ``skip`` completer (completes ``sudo``, ``which`` and other commands).
* In a subprocess command, having whitespace in between the left bracket and the command no longer raises a SyntaxError.
* Reduced history reading when run script or command. Potential speed increasing.
* Fixed crash on statup if XONSH_COLOR_STYLE is set to something invalid.
* Fixed the colorize and/or keywords.
* Functions can be used for $TITLE, the same way as for $PROMPT. (#4148)
* wsl detection works on archlinux wsl2 now (and hopefully everywhere)
* Fixed an exception when run xonfig wizard in no RC mode.
* Bash completions now handle quoted and space-containing arguments better.
* ``import`` completions always work.
* Test consistent RC loading behaviour in a variety of startup scenarios
* Absolute paths to executables don't break bash completions anymore
* Fix colors and text in the welcome message.

**Authors:**

* Gil Forsyth
* anki-code
* Noortheen Raja
* Gyuri Horak
* Daniel Shimon
* Matthias Bussonnier
* Gordon Ball
* cryzed
* Peter Ye
* Evgeny
* Jeremy Schlatter
* jmoranos
* Walter A. Boring IV
* bhawkins
* JackofSpades707
* Luiz Antonio Lazoti
* francium



v0.9.27
====================

**Added:**

* Add new internal command "disown" to remove background jobs from the shell's job list
* Python3.9 issues with subscriptor forms fixed.
* added `xontrib-cd <https://github.com/eugenesvk/xontrib-cd>`_
* Added **xontrib-history-encrypt** - new history backend that encrypt the xonsh shell commands history to prevent leaking sensitive data. If you like the idea give a star to the repository https://github.com/anki-code/xontrib-history-encrypt

**Changed:**

* New awesome landing on https://xon.sh - feel free to share and tweet!
* History files (json, sqlite) now have 600 (rw only for user) permission by default.
* PTK(python-prompt-toolkit) is no longer vendored with xonsh.

**Fixed:**

* Fixed a bug where "cd" and "rmdir" would return non-directory completions
* SQLite History Backend: show message instead of exiting when disk is full.

**Authors:**

* Gil Forsyth
* anki-code
* Noortheen Raja
* Tejasvi S Tomar
* Evgeny
* Adam Schwalm
* Nate Simon



v0.9.26
====================

**Added:**

* abbrevs now support callbacks
* Added a new xontrib ``tcg``

**Fixed:**

* now xonsh stdout delegates ``isatty`` to wrapped io stream.

**Authors:**

* Gil Forsyth
* anki-code
* Noortheen Raja
* Gao, Xiang



v0.9.25
====================

**Added:**

* VC_GIT_INCLUDE_UNTRACKED environment variable if untracked file changes are desired to show a dirty working directory
* added `xontrib-powerline2 <https://github.com/vaaaaanquish/xontrib-powerline2>`_
* Add '``|``' and '``|=``' operators to the ``Aliases`` class.
* Add tests to the merging functionality.
* Add "back2dir" xontrib (https://github.com/anki-code/xontrib-back2dir) - back to the latest used directory when starting xonsh shell.
* show code-coverage for PRs
* Added ``CommandPipeline.raw_out`` and ``CommandPipeline.raw_err`` to get stdout/err as raw bytes.
* The ``@()`` operator now supports ``bytes`` objects.
* index for history's sqlite-DB
* support passing style from RichCompleter to PTK's Completer
* ``xonsh.cli_utils`` to create cli from functions easily.
* Python API for completer command with ``xonsh.completer`` module functions.
* Added new environment variable ``$PROMPT_TOKENS_FORMATTER``.
    That can be used to set a callable that receives all tokens in the prompt template.
    It gives option to format the prompt with different prefix based on other tokens values.
    Enables users to implement something like [powerline](https://github.com/vaaaaanquish/xontrib-powerline2)
    without resorting to separate $PROMPT_FIELDS. Works with ``ASYNC_PROMPT`` as well.
    Check the `PR <https://github.com/xonsh/xonsh/pull/3922>`_ for a snippet implementing powerline
* PTK style rules can be defined in custom styles using the ``Token.PTK`` token prefix.
  For example ``custom_style["Token.PTK.CompletionMenu.Completion.Current"] = "bg:#ff0000 #fff"`` sets the ``completion-menu.completion.current`` PTK style to white on red.
* Added new environment variable ``XONSH_STYLE_OVERRIDES``. It's a dictionary containing pygments/ptk style definitions that overrides the styles defined by ``XONSH_COLOR_STYLE``.
  For example::

    $XONSH_STYLE_OVERRIDES["Token.Literal.String.Single"] = "#00ff00"  # green 'strings' (pygments)
    $XONSH_STYLE_OVERRIDES["completion-menu"] = "bg:#ffff00 #000"  # black on yellow completion (ptk)
    $XONSH_STYLE_OVERRIDES["Token.PTK.CompletionMenu.Completion.Current"] = "bg:#ff0000 #fff" # current completion is white on red (ptk via pygments)
* support PTK's clipboard integration if pyperclip is installed.
    So that some common emacs like
    `cut/copy <https://github.com/prompt-toolkit/python-prompt-toolkit/blob/master/examples/prompts/system-clipboard-integration.py>`_
    will work out of the box.
* Added Python 3.9 to continuous integration.
* ``open in google cloud shell`` button 🤩
* Respect ignorespace present in $HISTCONTROL
* ``_get_normalized_pstring_quote`` returns a consistent set of prefixes, and the quote, for all path-string variants e.g. inputs ``pr'`` and ``rp'`` both produce the tuple ``("pr", "'")``. This function is used by ``xonsh.completers.complete_path`` and ``xonsh.completers._path_from_partial_string``.
* Added warning about huge amount of commands in CommandsCache that could affect on start speed.
* New ``xonsh.procs`` subpackage for handling subprocess mode.
* Environment variable ``$COMPLETION_MODE`` controls kind of TAB completion used with prompt-toolkit shell.
  ``default``, the default, retains prior Xonsh behavior: first TAB displays the common prefix of matching completions,
  next TAB selects the first or next available completion.
  ``menu-complete`` enables TAB behavior like ``readline`` command ``menu-complete``.  First TAB selects the first matching
  completion, subsequent TABs cycle through available completions till the last one.  Next TAB after that displays
  the common prefix, then the cycle repeats.
* Added timing probes for prompt tokens, lexer and before prompt.
* improve github actions by adding cache
* ``xog`` xontrib - a simple command to establish and print temporary traceback
  log file.
* Added ``xontribs`` section to the ``xonfig``.
* added xontrib-avox-poetry(http://github.com/jnoortheen/xontrib-avox-poetry)
* added xontrib-broot(http://github.com/jnoortheen/xontrib-broot)
* added `xontrib-long-cmd-durations <https://github.com/jnoortheen/xontrib-cmd-durations>`_
* added `xontrib-commands <https://github.com/jnoortheen/xontrib-commands>`_
* added xontrib-powerline3(http://github.com/jnoortheen/xontrib-powerline3)
* Added ``xontrib-zoxide`` to the list of xontribs.
* Added ``xontrib-gitinfo`` to the list of xontribs.

**Changed:**

* ``CommandPipeline.__repr__`` now returns formatted output wherein its printed
  attributes are also repr strings. This improves the output of ``!()``.
* prompt-toolkit required version updated to >=3.0
* group environment variables into categories.
* The SQLite history backend now has the same logic of storing stdout to the memory like json history backend.
* Using ``ujson`` (if installed) in LazyJSON to loading json history 15% faster.
* use requirements.txt env in both CI/local/pre-commit checks
* add caching to CI jobs to improve speed
* The change that allows Nuitka build the xonsh binary.
* Remove ``p``, ``rp`` and ``pr`` prefix from partial p-string used in ``xonsh.completers._path_from_partial_string``, such that ``ast.literal_eval`` does not raise ``SyntaxError``. ``pr`` and ``rp`` strings are now treated internally as raw strings, but the p-string quote is correctly returned.
* Increment the prefix length when the prefix input to ``xonsh.completers.complete_path`` is a p-string. This preserves the length of the prefix for path-string variants.
* Pygments debug messages about cache will be shoen only in debug mode.
* ``ulimit`` builtin now operates on "soft" limits by default.
* tests for vc-branch should accept both master and main
* upgrade black formatter to version 20.8b1
* Use ``xontribs_meta.py`` instead of ``xontribs.json``
* Welcome message cosmetic changes.
* rewrite xontribs/jedi.xsh -> xontribs/jedi.py to take advantage of python tooling

**Deprecated:**

* ``PTK_STYLE_OVERRIDES`` has been deprecated, its function replaced by ``XONSH_STYLE_OVERRIDES``
* The ``xonsh.proc`` module has been deprecated. Please use the new
  ``xonsh.procs`` subpackage instead. Deprecation warnings related to this
  have been added.

**Removed:**

* The deprecated ``foreground`` decorator has been removed.
  Please use ``unthreadable`` instead.
* ``xonsh.proc.unthreadable`` and ``xonsh.proc.uncapturable``
  have been moved to ``xonsh.tools``. Please import from
  this module instead.

**Fixed:**

* Now the directory and the symlink to this directory will be read from PATH once. Increasing the startup speed on Linux.
* Environment variable registration no longer fails to validate when the default
  is a callable.
* Default values created from callables are stored on in the evironment.
* Completers also recognize ``:`` as a valid split point for insertion for, e.g. pytest completions

  .. code
  pytest test_worker::<TAB>
* Colorize ``and``/``or`` operators correctly like ``&&``/``||``
* Speed of CommandsCache increased when aliases have multiple updates (i.e. init conda).
* Now when loading RC files, xonsh will not fail to import modules located on
  the same folder.
* Setting an alias with IO redirections (e.g ``ls | wc``) now works correctly.
* PTK shell: ``window has no childres`` error while completion is triggered - https://github.com/xonsh/xonsh/issues/3963
* make_xontrib - typerror - https://github.com/xonsh/xonsh/issues/3971
* Fix libc detection on FreeBSD
* Fix uptime functionality on FreeBSD
* Updated History Backend tutorial.
* enabled flake8 warning on ambiguous names. it is fun naming variables in coded words until oneday it looks like encrypted.
* Added ANSI fallback for ``xonsh.tools.print_color`` if shell is not yet initialized. Fixes #3840.
* ``./run-tests.xsh`` without arguments previously gave an esoteric error. It
  now prints help on how to run the tests.
* The git customisation example in the .xonshrc docs uses the right module name

**Authors:**

* Anthony Scopatz
* Jamie Bliss
* a
* David Strobach
* Bob Hyman
* anki-code
* Gyuri Horak
* Noortheen Raja
* Carmen Bianca Bakker
* Danny Sepler
* vaaaaanquish
* Daniel Shimon
* Jerzy Drozdz
* Faris A Chugthai
* Asaf Fisher
* Dominic Ward
* omjadas
* Leandro Emmanuel Reina Kiperman
* Henré Botha
* Aneesh Durg
* colons
* yggdr



v0.9.24
====================

**Added:**

* Ability to register custom styles via ``xonsh.pyghooks.register_custom_style``
* Add method of escaping an environment variable from expansion to the Bash to Xonsh Translation Guide.
* added mypy to the project. many of the errors are ignored. but it is a start.
* Added example of subproc calling to the tutorial.
* New xontrib-sh (https://github.com/anki-code/xontrib-sh) to paste and run snippets from bash, zsh, fish.

**Changed:**

* Now ``COMPLETIONS_CONFIRM`` is ``True`` by default.
* ``xonsh.AppImage`` python version pinned to 3.8.
* Cookiecutter template to creating new xontribs has many improvements (https://github.com/xonsh/xontrib-cookiecutter).
* Docs sections improvement.

**Removed:**

* Removed ``import random``.

**Fixed:**

* #1207 - custom color themes
* Webconfig updarted for the ``NO_COLOR`` to ``RESET`` change.
* async prompt field's returns from earlier data
* Async prompt will now support nested-format strings in prompts
* handle None value for ASYNC_PROMPT_THREAD_WORKERS
* Fixed f-strings parsing in Python 3.9
* Fixed reset color in ``xontrib list``.
* Fixed NO_COLOR to RESET in prompt_ret_code and mplhooks.

**Authors:**

* Anthony Scopatz
* David Strobach
* a
* anki-code
* Gyuri Horak
* Noortheen Raja
* Will Shanks



v0.9.23
====================

**Added:**

* add API docs for ptk_shell.updator module
* add flake8-docstrings to the project. it integrates pydocstyle to flake8.
* Support for ANSI OSC escape sequences in ``$PROMPT``, setting ``$TITLE`` for example. (#374, #1403)
* Now ptk_shell supports loading its sections in thread, speeding up the prompt. Enable it by setting ``$ENABLE_ASYNC_PROMPT=True``.
* Added ``unset``, ``export``, ``set -e``, ``set -x``, ``shopt``, ``complete`` to xontrib bashisms.
* Use command_cache when finding available commands, to speedup command-not-found suggestions
* Added Visual Studio Code (VSCode) extension and Vim syntax file to the Editors page.
* Added ``exit(exit_code)`` function by default in not interactive mode. Now importing ``exit`` from ``sys`` is not needed.
* Added Python syntax highlighting of xsh files on Github repo xonsh/xonsh
* history clear, history off and history on actions, for managing whether history in the current session is saved.
* ValueErrors from environ.register now report the name of the bad env var
* Add a new color ``DEFAULT`` that is used to designate the terminal's default color.
* Add a new special color token ``RESET`` used to reset all attributes.
* Add a new xonsh tool 'print_warning' that prints a traceback with a warning message.
* Added `xontrib-onepath <https://github.com/anki-code/xontrib-onepath>`_ to associate files with apps in xonsh shell like in graphical OS.
* Added ``print_color`` and ``printx`` functions to builtins as reference to ``xonsh.tools.print_color``.
* Added to xontrib whole_word_jumping: Shift+Delete hotkey to delete whole word.
* Added "Advanced String Literals" to the "Tutorial".
* ``xonfig jupyter-kernel`` new subcommand to generate xonsh kernel spec for jupyter.
  Installing a new xonsh kernel for jupyter automatically removes any other one registered with jupyter,
  otherwise the new one might not be used.
* Added xontrib ``powerline-binding`` (https://github.com/dyuri/xontrib-powerline-binding) - uses ``powerline`` to render the prompt.

**Changed:**

* Improved printing of xonsh ``--shell-type`` argument in help message.
* "Bash to Xonsh Translation Guide" improvements.
* More stable exception handling in the tab completer.
* Changed sections order in docs
* The ``path`` type in ``${...}.register`` was renamed to ``env_path`` as it should be and added
  new ``path`` type instead that represent ``pathlib.Path``. Now you can register typed environment
  variables that will be converted to ``Path``.
* xonsh/environ.py: new rule: for "registered" environment variables (in ``DEFAULT_VARS`` or via ``env.register()``),
  if default is set to ``DefaultNotGiven``, then variable has no default and raises ``KeyError`` if it is not
  actually defined in environment.  Likewise, ``"var" in __xonsh__.env`` will return False.
* Changed defaults for ANSICON, TERM and VIRTUAL_ENV to ``DefaultNotGiven``, so code can rationally test whether
  the expected external program has defined these variables.  No need to do this for variables that xonsh
  itself defines.
* Moved internal uses of ``NO_COLOR`` to ``RESET``.
* When retrieving the git status or other fields for building the prompt xonsh will run
  the git commands with ``$GIT_OPTIONAL_LOCKS=0``.  For details on what this entails see
  the git documentation for
  `GIT_OPTIONAL_LOCKS <https://git-scm.com/docs/git#Documentation/git.txt-codeGITOPTIONALLOCKScode/>`_.
* Minor improvements to the get prompt speed. (Mostly in git.)
* ptk key binding for TAB -- hitting TAB to start completion now automatically selects the first displayed completion (if any).
  hitting TAB when in insert mode inserts TAB, as heretofore.  This more exactly follows behavior of readline ``menu-complete``.
  There is no configuration option for tailoring this behavior.
* ``xonfig info`` displays whether jupyter detected in environment and
  also path of xonsh jupyter kernel spec, if any.
* xontrib-argcomplete and xontrib-pipeliner description improvement.

**Deprecated:**

* Deprecated the ``NO_COLOR`` color reset token in favor of ``RESET``.

**Removed:**

* Deprecated ``--config-path`` argument suppressed from help.
* setup no longer (tries to) install jupyter kernel automatically,
  user must run ``xonfig jupyter-kernel`` manually.

**Fixed:**

* cygwin needs full path to find exe; disable thread_subprocs as default for cygwin
* Fixed logic in git dirty working directory
* Fixed type registration for ``*DIRS`` environment variables.
* Fixed #3703 and #3739, recent code change made it impossible to tell whether a (registered) environment variable
  was missing from environment or present and set to its registered default value. The test for ANSICON was
  failing due to this.
* Fixed environment variables substitution: unknown variables stay unreplaced now (#3818).
* Fixed xpg xontrib link
* Fix crash when xonsh tries to run windows app execution aliases.
* Setup wasn't consistently detecting jupyter in environment; ``python setup.py install`` worked, but
  ``pip install .`` wouldn't (because pip mucks with ``sys.path``),
  nor would install from wheel (because it doesn't run ``setup.py``).
* ``xonfig info`` now displays actual value of ON_MSYS and ON_CYGWIN instead of lazy bool type.
  (maybe was happening only on Windows?)

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Morten Enemark Lund
* Bob Hyman
* a
* anki-code
* christopher
* Eadaen1
* Danny Sepler
* Gyuri Horak
* cafehaine
* Wendell Turner
* Noortheen Raja
* Marius van Niekerk
* Wendell CTR Turner



v0.9.22
====================

**Added:**

* Added xontrib-argcomplete to support kislyuk/argcomplete - tab completion for argparse.
* New ``tools.debian_command_not_found()`` function for finding commands in
  debian/ubuntu packages.
* New ``tools.conda_suggest_command_not_found()`` function for finding commands in
  conda packages.
* Borrow shift-selection from prompt-toolkit. Shift-arrow (selects a letter) and control-shift-arrow (selects a word) should now be supported.
* Documentation for keyboard shortcuts
* Xonsh now supports bash-style variable assignments preceding
  subprocess commands (e.g. ``$FOO="bar" bash -c r"echo $FOO"``).

**Changed:**

* Added the fastest way to run xonsh AppImage to the docs.
* ``command_not_found()`` is now a wrapper function that finds packages for missing
  commands in a variety of locations. This function now also takes an ``env`` argument
  for looking up values in the enviornment.
* The variable cwd_dir, used for prompts,
  now always has a slash at the end, so users can use the
  construct "{cwd_dir}{cwd_base}" in their custom prompt definitions.

**Fixed:**

* crash when starting wizard by ``xonfig wizard``
  xonsh.environ: ensure get_docs(name).doc_default is str when name is not registered.
* Fixed issue where xontribs were failing from ``AttributeError: '_MergedKeyBindings' object has no attribute 'add'``

**Authors:**

* Anthony Scopatz
* David Strobach
* Bob Hyman
* anki-code
* Danny Sepler
* Eadaen1



v0.9.21
====================

**Added:**

* ``xonsh-in-docker.py`` script now has ``--pytest`` parameter,
  that automates pytest installation into the Docker container.
* Setup extras tag '[full]' to install prompt-toolkit and pygments in one fell swoop.
  Full feature install can be ``pip install xonsh[full]``.
* Support for PEP 570 positional-only parameters.
* Support for starred expressions within return statement
  (``return x, *my_list``).
* Xonsh now runs in Python 3.9
* ``vox`` xontrib now supports ``new --activate`` and ``deactivate --remove``
  to create + activate and deactivate + remove virtual environments in a single
  command.

**Changed:**

* Rewrote Installation and Configuration sections of Getting Started doc
  to clarify install from packages, and generally improve flow.

**Fixed:**

* Fixed incorrect reference to XONSH_HIST_SIZE instead of XONSH_HISTORY_SIZE
* RST code-block:: xonshcon now works.
* Non-default parameters can not follow defaults anymore.
* Fixed parser not emmiting errors in some cases.

**Authors:**

* Anthony Scopatz
* Jamie Bliss
* David Strobach
* Bob Hyman
* Will S
* Danny Sepler
* Marius van Niekerk



v0.9.20
====================

**Added:**

* ``abbrevs`` expansion now allows for setting cursor to a specific
  position within the expanded abbrev. For instance
  ::

    abbrevs["eswap"] = "with ${...}.swap(<edit>):\n    "

  expands ``eswap`` as you type to environment context manager
  ``swap()`` syntax and places the cursor at the position of the
  ``<edit>`` mark removing the mark itself in the process.
* Support for ANSI escape codes in ``$PROMPT``/``$RIGHT_PROMPT``. In this way 3rd party prompt generators like ``powerline`` or ``starship`` can be used to set the prompt. ANSI escape codes might be mixed with the normal formatting (like ``{BOLD_GREEN}``) and *prompt variables* (like ``{user}``) should work as well.
  For example:
  ::

    $PROMPT=lambda: $(starship prompt)
    $RIGHT_PROMPT="\x1b[33m{hostname} {GREEN}> "
* Added ``$HOSTNAME`` and ``$HOSTTYPE`` environment variables.
* New ``Env.rawkeys()`` iterator for iterating over all keys in an environment,
  not just the string keys like with ``__iter__()``.
* New landing page for https://xon.sh
* Added xonsh AppImage to the GitHub release assets
* xonsh now comes with a bulitin version of prompt-toolkit (3.0.5) which will be used as fall back if prompt_toolkit is not installed.
* Support for Python 3.8 PEP 572 assignment expressions (walrus operator).

**Changed:**

* custom startup scripts replaced by setup.py -generated (console) entrypoint scripts for both xonsh and xonsh-cat.
  This means xonsh.bat and xonsh-cat.bat are replaced on Windows by xonsh.exe and xonsh-cat.exe, respectively.

**Fixed:**

* Iterating over ``${...}`` or ``__xonsh__.env`` yields only string
  values again.
* List comprehensions do not ignore the second and subsequent ``if`` clauses
  in multi-if comprehension expressions any more.
* Xonsh can now fully handle special Xonsh syntax within f-strings, including
  environmnent variables within ``${}`` operator and captured subprocess
  expansion within f-string expressions.
* Avoid startup error on Windows when py.exe chooses wrong python interpreter to run xonsh.
  When multiple interpreters are in PATH, 'py' will choose the first one (usually in the virtual environment),
  but 'py -3' finds the system-wide one, apparently by design.

* For xonsh-cat, avoid parsing and processing first (0'th) argument when invoked directly from OS shell.
* Run control files are now read in with ``$THREAD_SUBPROCS`` off.
  This prevents a weird error when starting xonsh from Bash (and
  possibly other shells) where the top-level xonsh process would
  be stopped and placed into the background during startup. It
  may be necessary to set ``$THREAD_SUBPROCS=False`` in downstream
  xonsh scripts and modules.
* Fixed installation issues where generated files (like the parser table and
  amalgamated modules) were not installed.
* The xonsh test suite has been cleaned up. So no more failing test. Hopefully.
* Addressed robustness issue with ``"locked"`` history key not
  being present at startup.
* ``vox`` xontrib works again with the new environment defaults.

**Authors:**

* Anthony Scopatz
* Morten Enemark Lund
* David Strobach
* Bob Hyman
* anki-code
* Raphael Das Gupta
* Gyuri Horak



v0.9.19
====================

**Added:**

* ``history`` command now supports ``flush`` action
* Added new items on "Bash to xsh" page
* JsonHistory: added ``history gc --force`` switch to allow user to override above warning.
* JsonHistoryGC: display following warning when garbage collection would delete "too" much data and don't delete anything.

  "Warning: History garbage collection would discard more history ({size_over} {units}) than it would keep ({limit_size}).\n"
  "Not removing any history for now. Either increase your limit ($XONSH_HISTORY_SIZE), or run ``history gc --force``.",

  It is displayed when the amount of history on disk is more than double the limit configured (or defaulted) for $XONSH_HISTORY_SIZE.
* $LS_COLORS code 'mh' now recognized for (multi) hard-linked files.
* $LS_COLORS code 'ca' now recognized for files with security capabilities (linux only).
* CI step to run flake8 after pytest.
* RichCompletion for completions with different display value, description and prefix_len.
* Allow completer access to multiline document when available via ``xonsh.completers.tools.get_ptk_completer().current_document``.
* ``abbrevs`` word expasion can now be reverted by pressing
  the space bar second time immediately after the previous
  word got expanded.
* ``ulimit`` command.
* ``pdb`` xontrib, that runs pdb debugger on reception of SIGUSR1 signal.
* xontrib-xpg is a xontrib for running or explaining sql queries for posgresql database.

**Changed:**

* Xonsh now launches subprocesses with their ``argv[0]`` argument containing
  the command exactly as inserted by the user instead of setting it to the
  resolved path of the executable. This is for consistency with bash and other
  shells.
* Added ability to register, deregister environment variables;
  centralized environment default variables
* Added exit to the "Bash to xsh" article.
* xonsh.main _failback_to_other_shells now tries user's login shell (in $SHELL) before trying system wide shells from /etc/shells.
* The current working directory is now correctly obtained in line 501 of xonsh/parsers/base.py
* Garbage collection avoids deleting history and issues a warning instead if existing history is more than double the comfigured limit.
  This protects active users who might have accumulated a lot of history while a bug was preventing garbage collection.  The warning
  will be displayed each time Xonsh is started until user takes action to reconcile the situation.
* ``tests\test_integrations.py`` no longer runs with XONSH_DEBUG=1 (because new, debug-only progress messages from history were breaking it).
* Updated pytest_plugin for pytest 5.4 API, pip requirements for pytest>= 5.4
* Major improvements to Jedi xontrib completer:
    * Use new Jedi API
    * Replace the existing python completer
    * Create rich completions with extra info
    * Use entire multiline document if available
    * Complete xonsh special tokens
    * Be aware of _ (last result)
    * Only show dunder attrs when prefix ends with '_'
* Many files are starting to be formatted using ``pyupgrade --py36-plus``, in order to automatically update to newer
  Python constructs.
* ``xontrib load`` does not stop loading modules on error any more.

**Deprecated:**

* ``pytest --flake8`` now exits with error message to use flake8 instead.
  Allows single list of lint exceptions to apply in CI and your IDE.

**Removed:**

* Removed history replay
* pytest-flake8 package from requirements\*.txt
* Xonsh now relies exclusively on Setuptools for install.
* Compatibility with Python 3.5 has been removed as well as all related code. In
  particular xonsh.inspector does not defined ``getouterframes`` anymore, use
  ``inspect.getouterframe`` directly.

**Fixed:**

* Unhandled exception triggered by unexpected return from callable alias.
* Fix path completer throwing exception sometimes
* Fixed help operator not displaying definition for callables.
* JsonHistory.files(): Now once again enumerates history files from the directory.  This has been broken for about 2 years.
* JsonHistory.run_gc(): Don't busy loop while waiting for history garbage collection to complete, sleep a bit instead.
  This does much to keep Xonsh ptk_shell responsive when dealing with very large history on disk.
* Fixed JSON history indexing error.
* Fixed syntax error in scripts containing line continuation syntax.
* $LS_COLORS code 'fi' now used for "regular files", as it should have been all along. (was 'rs')
  See (#3608)[https://github.com/xonsh/xonsh/issues/3608].
* pyghooks.color_files now follows implememntation of ls --color closely.  Thanks @qwenger!
  However, a few documented differences remain due to use in Xonsh.

* $LS_COLORS['ln'] = 'target' now works.  Also fixes #3578.
* Fixed exit code for commands executed via ``-c`` (#3402)
* Logical subprocess operators now work after long arguments (e.g. ``--version``).
* ``pip`` completer no longer erroneously fires for ``pipx``
* Updated development guide to reference flake8 instead of pylint
* Corrected flake8 config for allowed exceptions.
* various pytest warnings in a "clean" test run.
* The current Mercurial topic is shown.
* Fixed import problems due to modules using deprecated pkg_resources methods by proxying calls to the underlying loader.
* Typo in 'source' alias.
* Crash in 'completer' completer.
* Don't complete unnecessarily in 'base' completer
* Viewing mock objects in the shell
* Fixed formatting error in ``vox rm`` command.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Morten Enemark Lund
* Bob Hyman
* David Strobach
* Burak Yiğit Kaya
* Matthias Bussonnier
* anki-code
* David Dotson
* con-f-use
* Daniel Shimon
* Jason R. Coombs
* Gyuri Horak
* Achim Herwig
* Marduk Bolaños
* Stefane Fermigier
* swedneck
* Feng Tian
* cafehaine
* paugier



v0.9.18
====================

**Added:**

* external *xontrib-hist-navigator* to facilitate directory history navigation.
* Support package prompt-toolkit V3 as well as V2 in prompt_toolkit shell.
* New `xontrib-output-search <https://github.com/anki-code/xontrib-output-search>`_ to get identifiers, names, paths, URLs and words from the previous command output and use them for the next command.
* New `xontrib-pipeliner <https://github.com/anki-code/xontrib-pipeliner>`_ is to easily process the lines using pipes.
* New `xontrib-prompt-bar <https://github.com/anki-code/xontrib-prompt-bar>`_ with elegance bar style for prompt.

**Changed:**

* $SHELL_TYPE "prompt_toolkit" with any suffix creates the "prompt_toolkit" shell, requires package prompt-toolkit >= 2.0
* Moved code from package xonsh.ptk2 to xonsh.ptk_shell (because it's the only one now); package xonsh.ptk2 redirects thence.
* Added extremely simplified xonsh AppImage building process.
* Added examples of usage $XONSH_TRACE_SUBPROC to the docs
* Use UTF-8 encoding when writing .xonshrc with webconfig for Windows compatibility

**Deprecated:**

* prompt-toolkit versions before 2.0

**Removed:**

* package xonsh.ptk

**Fixed:**

* Fixed name autosuggestion in path completer (#3519)
* Flake8/black fixes to the whole code tree, in 3 steps.
  Devs should update their IDE to run both during file editing, to avoid a re-accumulation of arbitrary exceptions.
* tests/test_builtins.py, fix test case test_convert_macro_arg_eval(kind).

**Authors:**

* Gil Forsyth
* Jamie Bliss
* Bob Hyman
* anki-code
* Raphael Das Gupta
* Noortheen Raja
* Manor Askenazi
* Marduk Bolaños



v0.9.17
====================

**Changed:**

* ``@$()`` subprocess operator now properly strips newline characters off
  the lines of multiline output.

* ``@$()`` subprocess operator does not require leading and trailing whitespace
  anymore, so expansions like ``cd /lib/modules/@$(uname -r)/kernel`` or
  ``gdb --pid=@$(pidof crashme)`` are now possible.
* Moved most CI to github actions (OSX is still on travis)
* Replaced Repl.It with RunThis on the front page of the docs.

**Fixed:**

* autovox xontrib now works with Python 3.5
* It is now possible to pass ``"&"`` as the last argument in subprocess mode.
* Fixed a bug on Windows causing ``FileNotFoundError`` exception if path
  elements contain trailing spaces.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* David Strobach



v0.9.16
====================

**Added:**

* Added ``abbrevs`` xontrib.
* Added `xontrib-pyenv <https://github.com/dyuri/xontrib-pyenv>`_ to list of registered xontribs.

**Changed:**

* ``xdg-open`` now runs unthreaded.

**Fixed:**

* Return Token.Text when filesystem item's type not defined in LS_COLORS; avoid crashing Pygments.
* Fixed bug on Windows if Path elements has trailing spaces. Windows in general and ``os.path.isdir()``
  doesn't care about trailing spaces but ``os.scandir()`` does.

**Authors:**

* Morten Enemark Lund
* Bob Hyman
* David Strobach
* Gyuri Horak
* Chris Lasher



v0.9.15
====================

**Added:**

* Adds documentation for how to setup an emacs editing mode for xonsh.
* New ``$XONSH_TRACE_SUBPROC`` environment variable.
* Added ``-l``, ``-c`` and ``-a`` options to ``xexec``, works now like ``exec``
  in bash/zsh
* **$HISTCONTROL** - *errordups* support for history-sqlite backend

**Changed:**

* ``-l`` switch works like bash, loads environment in non-interactive shell
* The xonsh pytest plugin no longer messes up the test order for pytest. Xsh test
  are still executed first to avoid a bug were other tests would prevent ``test_*.xsh``
  files to run correctly.
* New repo name for xxh

**Fixed:**

* Correctly follow symlinks when using dot-dot paths with cd -P.
* ``execx`` does not require the input string to be newline-terminated.
* ``evalx`` accepts newline-terminated input string.
* Fixed issue where negative exit codes (such as those produced
  by core dumps) where treated as logical successes when chaining
  processes with other boolean expressions.
* Fixed XONSH_TRACE_SUBPROC for pipeline command.
* updated CONTRIBUTING.rst about running pylint for changed files

**Authors:**

* Anthony Scopatz
* Morten Enemark Lund
* David Strobach
* anki-code
* Samuel Lotz
* Gyuri Horak
* Noortheen Raja
* Gabriel Vogel
* anki
* Jerzy Drozdz



v0.9.14
====================

**Added:**

* Added building process of standalone rootless AppImage for xonsh.
* pyproject.toml -- so vscode can use black as python formatter interactively
* The ``xonsh/interactive`` container has been added, in addition to the previous ``xonsh/xonsh`` and ``xonsh/action`` containers. See https://hub.docker.com/u/xonsh
* New ``$THREAD_SUBPROCS`` environment variable allows you to
  specify whether threadable subprocesses should actually be
  run in a thread or not.  Default ``True``.
* event on_lscolors_changed which fires when an item in $LS_COLORS changed.
* dict pyghooks.file_color_tokens containing color tokens for file types defined in $LS_COLORS.
* file pyproject.toml containing config rules for black formatter consistent with flake8
* New ``umask`` utility to view or set the file creation mask
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

* the feature list: subprocess mode colorizes files per $LS_COLORS, when they appear as arguments in the command line.
  Yet another approximation of ls -c file coloring behavior.
* file setup.cfg to declare flake8 rules for all tools (not just pytest)
* Moved python 3.8 parsing out of base parser
* The ``xonsh.pyghooks.XonshLexer`` now inherits from ``Python3Lexer``,
  rather than ``PythonLexer``.
* ``xonsh.pyghooks.XonshStyle`` now presents the ``highlight_color`` and
  ``background_color`` from the underlying style correctly.

**Removed:**

* Removed deprecated ``xonda`` ``xontrib`` from list

**Fixed:**

-  `[color] in .gitconfig (#3427) <https://github.com/xonsh/xonsh/issues/3427>`_ now stripped from {curr\_branch}

  - `Before <https://i.imgur.com/EMhPdgU.png>`_
  - `After <https://i.imgur.com/sJiqgsb.png>`_

* The autovox xontrib now preserves activated environment on cd
* setup.cfg -- duplicated flake8 config so interactive use and test runs enforce same rules. (Implementation is arguably a regression.)
* Pressing ``Ctrl+Z`` no longer deadlocks the terminal,
  allowing further input from the user, even for threaded
  subprocesses.
* ``XonshImportHook.get_source()`` now takes a dotted module name instead of a file path, as it should
* Fixed documentation on environment variable ``$PROMPT_REFRESH_INTERVAL``.
* Using rmtree on windows no longer attempts to use invalid ``rm`` command
  and uses ``del`` instead.
* Avoid crash in SubprocessSpec._run_binary() when command line has 2 real subprocesses piped together.
* Fixed an issue on Windows where pressing ctrl-c could sometimes result
  in a traceback if the process had already quit before being killed by xonsh.
* Modified base_shell._TeeStdBuf to feed bytes not str to console window under VS Code.
* Command line with leading whitespace improperly formated (PTK2/PTK3).
* Fix Ctrl-C event causing Atribute error on Windows (for reals this time).
* Unit test failures in test_integrations under ubuntu 19.10 with Python 3.8.0
* .gitignore entries for venv under project root (as for autovox) and for VS Code.
* Minor typo fixes to xontrib descriptions.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Morten Enemark Lund
* Jamie Bliss
* Bob Hyman
* David Strobach
* Burak Yiğit Kaya
* anki-code
* adam j hartz
* Nickolay Bukreyev
* Edmund Miller
* Mike Crowe
* Sylvain Corlay
* Chris Lasher
* Marcio Mazza



v0.9.13
====================

**Changed:**

* The ``$LS_COLORS`` environment variable will no longer raise exceptions when trying
  to convert ANSI color sequences to xonsh color names.

**Removed:**

* Remove built in support for "win unicode console". Full unicode support on windows is now provided by
  using the new `Windows terminal <https://github.com/microsoft/terminal>`__.

**Fixed:**

* Fixed issue converting ANSI color codes that contained both slow blink and set foreground
  or set background sequences.
* Fix coreutils ``cat`` behaviour on empty input (e.g. ``cat -``).

* Fix Ctrl-C event causing Atribute error on Windows.
* Fix Added OpenBSD as a platform

* Fix Corrected aliases for OpenBSD to not include ``--color=auto`` and ``-v``
* Fixed a regession with xonsh superhelp ``??`` operator and ``which -v`` which showed Pythons builtin
  doc strings.

**Authors:**

* Anthony Scopatz
* Morten Enemark Lund
* David Kalliecharan



v0.9.12
====================

**Added:**

* Added ``autovox`` xontrib
* ``xonsh.lib.itertools.as_iterable`` for making sure that strings are turned into iterables
* The ``percol`` command no longer predicts as threadable.

**Changed:**

* The ``source`` alias is now unthreaded, enabling ``contextvars`` to be used
  correctly in sourced files.
* Changed the ``ExecAlias`` to only be applied when the logical operators
  (``and``, ``or``) are surrounded by whitespace.

**Fixed:**

* Fixed missing ANSI color modifiers which causes traceback when they were used by ``$LS_COLORS``.
* gray empty bottom bar when using $XONSH_UPDATE_PROMPT_ON_KEYPRESS
* ``xonsh.lib.subprocess.check_output()`` now properly captures output.
* Correct ANSI colors for the default color scheme to stop suppressing the bold / italic / underline modifiers.
* tab completion for cd correctly handles the CDPATH environment variable
* On Windows, send ``CTRL_C_EVENT`` to subprocesses instead of ``SIGINT``.
* ``xonsh`` will return a non-zero exit code if it is run in file mode and
  cannot find the file specified, e.g.

  .. code-block::

     $ xonsh thisfiledoesntexist.xsh
     xonsh: thisfiledoesntexist.xsh: No such file or directory.
     $ _.returncode
     1
* Fixed issue with Jedi xontrib incorrectly raising errors
  during tab completion.
* Defining functions inside of the shell no longer crashes on Python 3.8.
* The encoding for xonsh script are now always assumed to be utf-8, even on
  Windows where the default encoding can be different. This allows for writing
  real unicode characters in the xonsh script files.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Morten Enemark Lund
* Jamie Bliss
* christopher
* Carmen Bianca Bakker
* Caleb Hattingh
* Sean Farley
* Allan Crooks
* micimize
* nedsociety
* fanosta



v0.9.11
====================

**Changed:**

* ``vox activate`` will now prepend the absolute path of the virtualenv ``bin/`` directory (or ``Scripts/`` on Windows) to ``$PATH``; before this was a relative path.

**Fixed:**

* "lou carcolh" example and description of ``endidx`` in completer tutorial
* Logical operators in aliases are now executed as expected, e.g.
  ``aliases['echocat'] = 'echo "hi" and echo "there"'`` will, when run, return

  .. code-block::

     hi
     there

**Authors:**

* Gil Forsyth
* con-f-use
* Caleb Hattingh



v0.9.10
====================

**Added:**

* $PROMPT_REFRESH_INTERVAL: Automatically invalidate the PROMPT every so many seconds.
* Allow disabling individual items in gitstatus prompt

**Fixed:**

* Fix ``cat`` can't read pseudo files with zero size such as /proc/\* or /sys/\* (#3182, #3199)
* command-not-found: now works on non-Debian bansed distributions
* Implemented ``'target'`` psuedo-color in ``$LS_COLORS`` for link coloring based
  off of the link target. This was causing issues on some systems where this is
  the default.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Morten Enemark Lund
* virus
* vaaaaanquish
* K.-Michael Aye
* Alexander Steffen
* Jan Chren
* Sean Farley
* László Vaskó
* Nils ANDRÉ-CHANG
* chengxuncc



v0.9.9
====================

**Added:**

* $COMPLETION_IN_THREAD: When this is True, background theads is used for completion.
* Open man page when requesting help for subprocess commands, e.g. using ``sh?``
* Add several cmds/tools for predict list

**Changed:**

* Changed ``XonshSession.link_builtins`` to set a ``DynamicAccessProxy`` for each ``builtin`` link
* ``events`` is now unlinked from ``builtins``

**Removed:**

* Removed ``DeprecationWarningProxy``; no longer needed
* Removed ``load_proxies`` and ``unload_proxies``; moved functionality to ``XonshSession.link_builtins``, ``XonshSession.unlink_builtins``, respectively.
* Removed deprecated ``builtin.__xonsh_*__`` alises, please use ``builtins.__xonsh__.*`` instead.

**Fixed:**

* Added proxied ``__dir__`` method to ``DynamicAccessProxy`` to restore
  tab-completion for objects that use the proxy (especially ``events``)
* Avoid displaying finished tasks in title.
* ``inspect.getsource`` now works correctly and the ``__xonsh__.execer`` resets
  ``<filename>`` correctly.  This was causing several very strange buggy
  behaviors.
* Hitting ``Enter`` while ``$VI_MODE=True`` now executes the current code block
  irrespective of cursor position

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* David Dotson
* vaaaaanquish
* Alexander Steffen
* Ke Zhang
* Daniel Smith



v0.9.8
====================

**Fixed:**

* Fixed a bug in sourcing Bash functions, where ``delare -F`` contained
  newlines, meaning that the ``read`` command that followed it would only
  pick up the first function declaration. ``echo`` is used to normalize
  whitespace.

**Authors:**

* Anthony Scopatz



v0.9.7
====================

**Added:**

* add xontrib (xontrib-readable-traceback)
* Registered kitty xontrib.
* The zipapp extra was added to install the importlib.resources backport on <3.7

**Changed:**

* turn off warning on completer
* xontrib metadata loading is now zipapp safe when possible

**Fixed:**

* Updated py-bash-completion that is vended with xonsh to v0.2.6 which
  includes a fix completion which uses a subshell environment and a
  fix for string index error in stripped prefix.
* Removed obsolte "Alt+." keybinding in xontrib-bashisms that was causing built-in binding to malfunction.
* Fixed that occurs when type a command before rendering.

**Authors:**

* Anthony Scopatz
* Jamie Bliss
* con-f-use
* vaaaaanquish
* Gyuri Horak



v0.9.6
====================

**Fixed:**

* Fixed exception in help/version threadable predictor
* Fixed gitstatus prompt so that it also now reports deleted files
* Fixed issue where the prompt-toolkit2 shell could not display and
  would end up in an infinite error loop if ``$MULTILINE_PROMPT``
  was a suitably "false" value, such as ``None`` or an empty string.
* Fixed issue where setting ``$XONSH_STDERR_PREFIX`` and ``$XONSH_STDERR_POSTFIX``
  and running a command in the ``xonshrc`` file would throw an error.

**Authors:**

* Anthony Scopatz
* David Strobach
* virus
* shadow-light



v0.9.5
====================

**Fixed:**

* Style 'bw'. Background colors was added in the style description.
* Fix causing error in ``get_predictor_threadable`` on windows when try to run not exist command
* ``pip`` completer no longer fires when ``pip`` happens to appear within a word
  like ``bagpipes``
* Fixed issue with ``history gc`` command not running properly.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Jean-Benoist Leger
* virus
* con-f-use



v0.9.4
====================

**Added:**

* Add processing ``%d`` for avoid overwriting in ``run-tests.xsh``

**Changed:**

* Xonsh now does not attempt to expand raw strings, so now::

    $ echo "$HOME"
    /home/user
    $ echo r"$HOME"
    $HOME
* sudoedit now runs unthreaded

**Fixed:**

* threadable predictor for 'env' command based on predictor from the executed
  command. Fixes #2759 and #3103.
* An error in the 'xon.sh' executable that only popped up during testing has
  been fixed.  Specifically: It now directly calls 'python3' without invoking
  'env'.
* bashisms extension can be used again with prompt_toolkit v1
* Fix a crash when setting ``$INTENSIFY_COLORS_ON_WIN`` in certain situations.
* Fix issue with bashsisms xontrib causing syntax errors for some Python statements
* portable trick to pass args which replace '/usr/bin/env' is removed and
  '/usr/bin/env' is used. Fixes bug when a python3 used is outside the default
  'PATH'.

**Authors:**

* Anthony Scopatz
* Morten Enemark Lund
* Jean-Benoist Leger
* David Strobach
* virus
* Carmen Bianca Bakker
* con-f-use
* cclauss
* Eddie Peters



v0.9.3
====================

**Deprecated:**

* Python v3.4 has been fully, completely, and (hopefully) correctly
  deprecated. Please migrate to an officially supported version of Python.

**Authors:**

* Anthony Scopatz



v0.9.2
====================

**Changed:**

* For aliases, predictor is build with the predictor of original command, in
  place of default predictor.

**Fixed:**

* Updated setup.py to require Python 3.4 using the ``python_requires`` keyword.
  This rectifies issues with pip installing xonsh. Python 3.4 support will
  be removed on the following release.

**Authors:**

* Anthony Scopatz
* Jean-Benoist Leger



v0.9.1
====================

**Changed:**

* We no longer manually check the Python version in ``setup.py``,
  but instead use the setuptools ``python_requires`` feature.

**Fixed:**

* Updates for integrating with new colors styles in Pygments v2.4.0.

**Authors:**

* Anthony Scopatz



v0.9.0
====================

**Added:**

* Implemented the following "bang command" bashisms: ``!$``, ``$*``, ``!^``,
  and ``!<str>``.  These are in addition to ``!!``, which was already
  implemented.
* asciinema (terminal recorder) added in not threadable commands.
* tput added in not threadable commands.
* New ``color_tools.KNOWN_XONSH_COLORS`` frozenset.
* New ``pyghooks.PYGMENTS_MODIFIERS`` mapping from color modifier names to
  pygments colors.
* New ``pyghooks.color_name_to_pygments_code()`` function for converting
  color names into pygments color codes.

**Changed:**

* Circle now runs ``black`` checks on contents of bundled xontribs

* The ``black`` checks no longer skip some files buried deeper in the directory
  tree.
* Errors while formatting the prompt are highlighted for easier debugging.
* Pygments styles only define the standard set of colors, by default.
  Additional colors are computed as needed.
* PTYs created for running threadable command have now size set to same size
  than main terminal.
* Update documentation pointing to the minimal required version of
  Python (3.5).

**Deprecated:**

* Drop support for Python 3.4.

**Removed:**

* ``pyghooks.KNOWN_COLORS`` is no longer needed or useful as pygments colors
  are computed automatically.
* ``style_tools.KNOWN_COLORS`` was never used, redundant with
  ``pyghooks.KNOWN_COLORS`` and has thus been removed.

**Fixed:**

* Fixed a DeprecationWarning that would show up during an import of MutableSet.
* Fixed error with aliases composed of functions wrapped in functools.partial.
* ``black`` formatted all xontribs
* deleting a non existing environement variable with default value do nothing
  instead of raising a exception trying to deleting it in existing values dict.
* Fixed crash while converting ANSI color codes with leading zeroes
* Fixed crash while parsing invalid ANSI color code
* fix causing infinite loop when doing ``cat`` empty file
* Fixed issue which occurs when user doesn't have access to parent directory and
  xonsh scan all parents directory to find if we are in a Hg repository.
* Fixed issue with pygments-cache not properly generating a cache the first
  time when using prompt-toolkit when using ``ptk2``.
  This was due to a lingering lazy import of ``pkg_resources``
  that has been removed.
* Minor update for Python v3.8.
* Fixed a "'NoneType' object is not iterable" bug when looking up ``stty``
  in command cache.
* The release tarball now includes all test files.
* Arguments passed to python in 'scripts/xonsh' and in 'scripts/xonsh-cat' are
  now passed by a portable hack in sh, not anymore by /usr/bin/env.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Jean-Benoist Leger
* David Strobach
* virus
* Carmen Bianca Bakker
* Alexander Sosedkin
* Kale Kundert
* Andrés García García
* Samuel Dion-Girardeau
* Steven Kryskalla
* Rodrigo Oliveira



v0.8.12
====================

**Added:**

* Support for more ANSI escape sequence modifers allowed in color names.
  The current modifiers now allowed are: BOLD, FAINT, ITALIC, UNDERLINE,
  SLOWBLINK, FASTBLINK, INVERT, CONCEAL, and STRIKETHROUGH.
* New ``ansi_tools.ansi_color_name_to_escape_code()`` function for
  converting a color name to an ANSI escape code.
* ``color_tools.RE_XONSH_COLOR`` is a regular expression for matching
  xonsh color names.
* ``color_tools.iscolor()`` is a simple function for testing whether a
  string is a valid color name or not.
* The ``tools.all_permutations()`` function yields all possible permutations
  of an iterable, including removals.

**Changed:**

* change url of xontrib-autojump
* ANSI color styles may now be defined simply by their plain and intense colors.
* ``SET_FOREGROUND_3INTS_`` renamed to ``SET_FOREGROUND_FAINT_``,
  ``SET_BACKGROUND_3INTS_`` renamed to ``SET_BACKGROUND_FAINT_``,
  ``SET_FOREGROUND_SHORT_`` renamed to ``SET_FOREGROUND_SLOWBLINK_``, and
  ``SET_BACKGROUND_SHORT_`` renamed to ``SET_BACKGROUND_SLOWBLINK_``.

**Removed:**

* ``ansi_tools.ANSI_REVERSE_COLOR_NAME_TRANSLATIONS`` removed, as it is
  no longer needed.

**Fixed:**

* Fixed issues where ``$LS_COLORS`` could not convert valid ANSI colors.

**Authors:**

* Anthony Scopatz
* virus



v0.8.11
====================

**Added:**

* New ``xonsh.color_tools.short_to_ints()`` function for directly
  converting a short (0 - 256) color into a 3-tuple of ints
  representing its RGB value.
* New ``xonsh.ansi_colors.ansi_reverse_style()`` function for
  converting a mapping of color names to ANSI escape codes into
  a mapping from escape codes into color names. This is not a
  round-trippable operation.
* New ``xonsh.ansi_colors.ansi_color_escape_code_to_name()`` function
  for converting an ANSI color escape code into the closest xonsh
  color name for a given style.
* New ``xonsh.events.EventManager.exists()`` method enables checking
  whether events actually exist without making the event if it
  doesn't exist.
* New command-specific event categories called ``on_pre_spec_run_<cmd-name>``
  and ``on_post_spec_run_<cmd-name>`` will be fired before and after
  ``SubpocSpec.run()`` is called.  This allows for command specific
  events to be executed.  For example, ``on_pre_spec_run_ls`` would
  be run prior to an invocation of ``ls``.
* New ``xonsh.environ.LsColors`` class for managing the ``$LS_COLORS``
  environment variable. This ensures that the ``ls`` command respects the
  ``$XONSH_COLOR_STYLE`` setting. An instance of this class is added to the
  environment when either the ``$LS_COLORS`` class is first accessed or
  the ``ls`` command is executed.
* The ``on_pre_spec_run_ls`` event is initialized with a default handler
  that ensures that ``$LS_COLORS`` is set in the actual environment prior
  to running an ``ls`` command.
* New ``xonsh.tools.detype()`` function that simply calls an object's own
  ``detype()`` method in order to detype it.
* New ``xonsh.tools.always_none()`` function that simply returns ``None``.
* New ``Env.set_ensurer()`` method for setting an ensurer on an environment.

**Changed:**

* The black and white style ``bw`` now uses actual black and white
  ANSI colore codes for its colors, rather than just empty color
  sequences.
* An environment variable ``detype`` operation no longer needs to be a
  function, but may also be ``None``. If ``None``, this variable is
  considered not detypeable, and will not be exported to subprocess
  environments via the ``Env.detype()`` function.
* An environment variable ``detype`` function no longer needs to return
  a string, but may also return ``None``. If ``None`` is returned, this
  variable is  considered not detypeable, and will not be exported to
  subprocess environments via the ``Env.detype()`` function.
* The ``Env.detype()`` method has been updated to respect the new
  ``None`` types when detyping.
* The ``xonsh.tools.expandvars()`` function has been updated to respect
  the new ``None`` types when detyping.
* The ``xonsh.xonfig.make_xonfig_wizard()`` function has been updated to respect
  the new ``None`` types when detyping.
* Event handlers may now be added and discarded during event firing for
  normal events.  Such modifications will not be applied until the
  current firing operation is concluded. Thus you won't see newly added
  events fired.
* xonsh now uses its own vendored version of ply. Any installed versions will no longer be used. This reflects that ply is no
  longer distributed as an installable package.
* Updated to use ply version 3.11.
* Reverted change in ``give_to_terminal`` to restore working version of
  ``cmake``, ``rm -i``, etc.  This breaks ``pv | head``.

**Deprecated:**

* The ``xonsh.color_tools.make_pallete()`` function is no
  longer deprecated, as it is actually needed in other parts of
  xonsh still, such as ``pyghooks``.

**Removed:**

* All code references to ``$FORMATTER_DICT`` have been removed.

**Fixed:**

* Resolved issues where macro functions were not able to properly
  accept single-line statements in ``exec`` and ``single`` mode.
* Minor fixes to ``xonsh.events.debug_level()``.
* Fixed a regression where some interactive commands were not waited for
  properly for long enough.
* Fixed environments not showing in the prompt when using Anaconda Python.

* Fixed regression with anaconda activate/deactivate scripts not working on Windows.

**Authors:**

* Anthony Scopatz
* Morten Enemark Lund



v0.8.10
====================

**Added:**

* New ``xonsh.aliases.partial_eval_alias()`` function and related classes
  for dispatching and evaluating partial alias applications for callable
  aliases.

**Changed:**

* Subprocesses will no longer close file descriptors automatically.
  This was causing issues with other commands that expected file
  descriptors to remain open, such as ``make``.
* The ``xonsh.Aliases.eval_alias()`` method updated to use
  ``xonsh.aliases.partial_eval_alias()``.

**Fixed:**

* Fixed ``xonsh.completers.base.complete_base()`` to no longer throw an
  error caused by ``complete_python()`` sometimes returning a tuple.
  This fixes cases such as ``ls &&<TAB>``.
* Fixed regression with line continuations in implicit subprocess mode within
  indented blocks of code, such as if-statements.
* Resolved issue where setting empty signal masks was causing the
  terminal to close. This was problematic for certain command
  pipelines. For example, ``pv /dev/urandom | head`` now works.
* Prevents recursive errors from being raised when there is no child process
  in ``xonsh.jobs.wait_for_active_job()``.
* Tweaked ``xonsh.completers.commands.complete_skipper()`` to insert a space following
  certain tokens (``&&``, ``||``, ``|``, ``and``, ``or``) to avoid overwriting existing tokens
  with completer output.
* Fixed bug with evaluating recursive aliases that did not implement
  the full callable alias signature.

**Authors:**

* Anthony Scopatz
* Gil Forsyth
* Troy de Freitas



v0.8.9
====================

**Added:**

* New ``env_prefix`` & ``env_postfix`` prompt fields for rendering the pre- and
  post-fix characters of the an active virtual environment.
* ON_WSL attribute in platform.py
* Rendering of ``{env_name}`` in ``$PROMPT`` is now suppressed if
  the ``$VIRTUAL_ENV_DISABLE_PROMPT`` environment variable is
  defined and truthy.
* Rendering of ``{env_name}`` in ``$PROMPT`` is now overridden by
  the value of ``str($VIRTUAL_ENV_PROMPT)`` if that environment variable
  is defined and ``not None``. ``$VIRTUAL_ENV_DISABLE_PROMPT`` takes precedence
  over ``$VIRTUAL_ENV_PROMPT``.
* A xontrib which adds support for `direnv <https://direnv.net/>`_

**Changed:**

* ``env_name`` prompt field now looks up the pre- and post-fix characters,
  rather than relying on hard-coded values.
* Some minor ``history show`` efficiency improvements.
* If we are on wsl, avoid to use xonsh_preexec_fn when pipe.

**Fixed:**

* Made ``$PATH`` searching more robust to broken symlinks on Windows.
* undesirable SIGSTOP by putting in a SIGCONT
* Fixed issue with recursive aliases not being passed all keyword arguments
  that are part of the callable alias spec. This allows commands like
  ``aliases['hsa'] = "history show all"; hsa | head`` to no longer fail
  with strange errors.

**Authors:**

* Anthony Scopatz
* Sagar Tewari
* Brian Skinn
* Yohei Tamura
* anatoly techtonik
* 74th
* Chad Kennedy



v0.8.8
====================

**Added:**

* ``vox new`` has an added ``-p --interpreter`` flag for choosing the Python interpreter to use for virtualenv creation
* The default Python intrepreter vox uses to create virtual environments can be set using the ``$VOX_DEFAULT_INTERPRETER`` environment variable.


**Changed:**

* ``lib.ChainDB`` now resolves results to the type of the inputs if possible




v0.8.7
====================

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


**Fixed:**

* Set ``ls`` to ``predict_true`` in ``default_threadable_predictors``.  This prevents ``ls`` on OSX
  from being flagged on OSX as unthreadable (incorrectly) because it relies on ``ncurses``.




v0.8.6
====================

**Added:**

* Doco about how to update xonsh and how to set and unset environment variables


**Fixed:**

* Updated behavior of the ``cat`` coreutils function so that it properly
  handles as vareity of cases such as:

    * Exits after concatenating normal files which have a finite size
    * Continues to run for special files which do not have a size,
      such as ``/dev/random``
    * Is interruptable in all cases with Crtl-C.
* Callable aliases were not properly raising a ``CalledProcessError`` when they
  returned a non-zero exist status when ``$RAISE_SUBPROC_ERROR = True``. This has
  been fixed.
* Fixed interpretation of color names with PTK2 and Pygments 2.3.1.




v0.8.5
====================

**Added:**

* Add alias to `base16 shell <https://github.com/chriskempson/base16-shell>`_

* Installation / Usage
    1. To install use pip

       .. code-block:: bash

            python3 -m pip install xontrib-base16-shell

    2. Add on ``~/.xonshrc``

       .. code:: xonsh
            :number-lines:

            $BASE16_SHELL = $HOME + "/.config/base16-shell/"
            xontrib load base16_shell


    3. See image

       .. image:: https://raw.githubusercontent.com/ErickTucto/xontrib-base16-shell/master/docs/terminal.png
            :width: 600px
            :alt: terminal.png

* New ``DumbShell`` class that kicks in whenever ``$TERM == "dumb"``.
  This usually happens in emacs. Currently, this class inherits from
  the ``ReadlineShell`` but adds some light customization to make
  sure that xonsh looks good in the resultant terminal emulator.
* Aliases from foreign shells (e.g. Bash) that are more than single expressions,
  or contain sub-shell executions, are now evaluated and run in the foreign shell.
  Previously, xonsh would attempt to translate the alias from sh-lang into
  xonsh. These restrictions have been removed.  For example, the following now
  works:

  .. code-block:: sh

      $ source-bash 'alias eee="echo aaa \$(echo b)"'
      $ eee
      aaa b

* New ``ForeignShellBaseAlias``, ``ForeignShellFunctionAlias``, and
  ``ForeignShellExecAlias`` classes have been added which manage foreign shell
  alias execution.


**Changed:**

* String aliases will now first be checked to see if they contain sub-expressions
  that require evaluations, such as ``@(expr)``, ``$[cmd]``, etc. If they do,
  then an ``ExecAlias`` will be constructed, rather than a simple list-of-strs
  substitutiuon alias being used. For example:

  .. code-block:: sh

      $ aliases['uuu'] = "echo ccc $(echo ddd)"
      $ aliases['uuu']
      ExecAlias('echo ccc $(echo ddd)\n', filename='<exec-alias:uuu>')
      $ uuu
      ccc ddd

* The ``parse_aliases()`` function now requires the shell name.
* ``ForeignShellFunctionAlias`` now inherits from ``ForeignShellBaseAlias``
  rather than ``object``.


**Fixed:**

* Fixed issues where the prompt-toolkit v2 shell would print an extra newline
  after Python evaluations in interactive mode.




v0.8.4
====================

**Added:**

* Added the possibility of arbitrary paths to the help strings in ``vox activate`` and
  ``vox remove``; also updated the documentation accordingly.
* New ``xonsh.aliases.ExecAlias`` class enables multi-statement aliases.
* New ``xonsh.ast.isexpression()`` function will return a boolean of whether
  code is a simple xonsh expression or not.
* Added top-level ``run-tests.xsh`` script for safely running the test suite.


**Changed:**

* String aliases are no longer split with ``shlex.split()``, but instead use
  ``xonsh.lexer.Lexer.split()``.
* Update xonsh/prompt/cwd.py _collapsed_pwd to print 2 chars if a directory begins with "."
* test which determines whether a directory is a virtualenv

  previously it used to check the existence of 'pyvenv.cfg'
  now it checks if 'bin/python' is executable


**Fixed:**

* Fixed issue with ``and`` & ``or`` being incorrectly tokenized in implicit
  subprocesses. Auto-wrapping of certain subprocesses will now correctly work.
  For example::

      $ echo x-and-y
      x-and-y
* Fix EOFError when press `control+d`
* fix no candidates if no permission files in PATH
* Fixed interpretation of color names with PTK2 and Pygments 2.3.
* Several ResourceWarnings: unclosed file in tests
* AttributeError crash when using --timings flag
* issue #2929




v0.8.3
====================

**Added:**

* Dociumentation paragrapgh about gow to run xonsh in Emacs shell


**Changed:**

* Updated what pip requirements are needed to build the documnetaion
* ``$XONSH_TRACEBACK_LOGFILE`` now beside strings also accepts ``os.PathLike``
  objects.
* Updated vended version of ``ply`` to 3.11
* Deprecation warnings now print from stacklevel 3.


**Fixed:**

* Annotation assignment statements (e.g. ``x : int = 42``) are now supported.
* Fixed error output wording for fg and bg commands
* Flake8 errors
* xonsh can now properly parse import statements with trailing comma within
  parentheses, e.g.::

    from x import (y, z,)
* ResourceWarning: unclosed scandir iterator in imphooks.py
* Removed use of deprecated ``inspect.formatargspec()`` for ``inspect.signature()``
* ``Makefile`` directive that updates vended version of ``ply``




v0.8.2
====================

**Changed:**

* Now there is only a single instance of ``string.Formatter()`` in the
  code base, which is called ``xonsh.tools.FORMATTER``.


**Fixed:**

* f-strings (``f"{expr}"``) are now fully capable of executing xonsh expressions.
  The one exception to this is that ``![cmd]`` and ``!(cmd)`` don't work because
  the ``!`` character interferes with Python string formatting. If you need to
  run subprocesses inside of f-strings, use ``$[cmd]`` and ``$(cmd)`` instead.
* Fixed occasional "no attribute 'settitle' error"




v0.8.1
====================

**Added:**

* ``SubprocSpec`` has a new ``pipeline_index`` integer attribute that indicates
  the commands position in a pipeline. For example, in

  .. code-block:: sh

    p = ![ls -l | grep x]

  The ``ls`` command would have a pipeline index of 0
  (``p.specs[0].pipeline_index == 0``) and ``grep`` would have a pipeline index
  of 1 (``p.specs[1].pipeline_index == 1``).  This may be usefule in callable
  alaises which recieve the spec as an argument.


**Changed:**

* Removed ``fish`` from list of supported foreign shells in the wizard.
* Circle CI config updated to use a pinned version of ``black`` (18.9b0)
* Pytest plugin now uses ``xonsh.main.setup()`` to setup test environment.
* Linux platform discovery will no longer use ``platform.linux_distribution()``
  on Python >=3.6.6. due to pending deprecation warning.
* Updated Linux Guide as Xonsh is now available in Arch Linux official repositories.


**Fixed:**

* Builtin dynamic proxies and deprecation warning proxies were not deleting
  attributes and items properly.
* Fixed stdout/sdterr writing infinite recursion error that would occur in
  long pipelines of callable aliases.
* Fixed a bug which under very rare conditions could cause the shell
  to die with PermissionError exception while sending SIGSTOP signal
  to a child process.
* Fixed further raw string deprecation warnings thoughout the code base.




v0.8.0
====================

**Added:**

* Windows CI jobs on Azure Pipelines
* The ``cryptop`` command will no longer have its output captured
  by default.
* Added new env-var ``PTK_STYLE_OVERRIDES``. The variable is
  a dictionary containing custom prompt_toolkit style definitions.
  For instance::

    $PTK_STYLE_OVERRIDES['completion-menu'] = 'bg:#333333 #EEEEEE'

  will provide for more visually pleasing completion menu style whereas::

    $PTK_STYLE_OVERRIDES['bottom-toolbar'] = 'noreverse'

  will prevent prompt_toolkit from inverting the bottom toolbar colors
  (useful for powerline extension users)

  Note: This only works with prompt_toolkit 2 prompter.


**Changed:**

* All ``__xonsh_*__`` builtins have been migrated to a ``XonshSession`` instance at
  ``__xonsh__``. E.g. ``__xonsh_env__`` is now ``__xonsh__.env``.
* Other xonsh-specific builtins (such as ``XonshError``) have been proxied to
  the ``__xonsh__`` session object as well.


**Deprecated:**

* All ``__xonsh_*__`` builtins are deprected. Instead, the corresponding
  ``__xonsh__.*`` accessor should be used. The existing ``__xonsh_*__`` accessors
  still work, but issue annoying warnings.


**Fixed:**

* Fixed deprecation warnings from unallowed escape sequences as well as importing abstract base classes directly from ``collections``
* Fix for string index error in stripped prefix
* bash_completions to include special characters in lprefix

  Previously, glob expansion characters would not be included in lprefix for replacement

  .. code-block:: sh

    $ touch /tmp/abc
    $ python
    >>> from bash_completion import bash_completions
    >>>
    >>> def get_completions(line):
    ...     split = line.split()
    ...     if len(split) > 1 and not line.endswith(' '):
    ...         prefix = split[-1]
    ...         begidx = len(line.rsplit(prefix)[0])
    ...     else:
    ...         prefix = ''
    ...         begidx = len(line)
    ...     endidx = len(line)
    ...     return bash_completions(prefix, line, begidx, endidx)
    ...
    >>> get_completions('ls /tmp/a*')
    ({'/tmp/abc '}, 0)

  Now, lprefix begins at the first special character:

  .. code-block:: sh

    $ python
    >>> from bash_completion import bash_completions
    >>>
    >>> def get_completions(line):
    ...     split = line.split()
    ...     if len(split) > 1 and not line.endswith(' '):
    ...         prefix = split[-1]
    ...         begidx = len(line.rsplit(prefix)[0])
    ...     else:
    ...         prefix = ''
    ...         begidx = len(line)
    ...     endidx = len(line)
    ...     return bash_completions(prefix, line, begidx, endidx)
    ...
    >>> get_completions('ls /tmp/a*')
    ({'/tmp/abc '}, 7)
* The ``xonsh.main.setup()`` function now correctly passes the
  ``shell_type`` argument to the shell instance.
* try_subproc_toks now works for subprocs with trailing and leading whitespace

  Previously, non-greedy wrapping of commands would fail if they had leading and trailing whitespace:

  .. code-block:: sh

    $ true && false || echo a
    xonsh: For full traceback set: $XONSH_SHOW_TRACEBACK = True
    NameError: name 'false' is not defined

    $ echo; echo && echo a

    xonsh: For full traceback set: $XONSH_SHOW_TRACEBACK = True
    NameError: name 'echo' is not defined

  Now, the commands are parsed as expected:

  .. code-block:: sh

    $ true && false || echo a
    a

    $ echo; echo && echo a


    a




v0.7.10
====================

**Added:**

* 'off' can be passed as falsy value to all flags accepting boolean argument.
* DragonFly BSD support
* Format strings (f-strings) now allow environment variables to be looked up.
  For example, ``f"{$HOME}"`` will yield ``"/home/user"``. Note that this will
  look up and fill in the ``detype()``-ed version of the environment variable,
  i.e. it's native string representation.


**Changed:**

* Running ``aurman`` command will now be predicted to be unthreaded by default.


**Fixed:**

* The xonsh ``xonfig wizard`` would crash if an unknown foreign shell was
  provided. This has been fixed.
* The ``hg split`` command will now predict as unthreadable.
* Fixed path completer crash on attempted f-string completion




v0.7.9
====================

**Added:**

* The python-mode ``@(expr)`` syntax may now be used inside of subprocess
  arguments, not just as a stand-alone argument. For example:

  .. code-block:: sh

    $ x = 'hello'
    $ echo /path/to/@(x)
    /path/to/hello

  This syntax will even properly expand to the outer product if the ``expr``
  is a list (or other non-string iterable) of values:

  .. code-block:: sh

    $ echo /path/to/@(['hello', 'world'])
    /path/to/hello /path/to/world

    $ echo @(['a', 'b']):@('x', 'y')
    a:x a:y b:x b:y

  Previously this was not possible.
* New ``$DOTGLOB`` environment variable enables globs to match
  "hidden" files which start with a literal ``.``. Set this
  variable to ``True`` to get this matching behavior.
  Cooresponding API changes have been made to
  ``xonsh.tools.globpath()`` and ``xonsh.tools.iglobpath()``
* New environment variable ``$FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE``
  enables the removal of skipping foreign alias messages.
* New ``--suppress-skip-message`` command line option for skipping
  foreign alias messages when sourcing foreign shells.


**Fixed:**

* In Bash completions, if there are no files to source, a ``set()`` will
  no longer be inserted into the completion script.
* Fixed issue with TAB completion in readline not replacing values
  with spaces properly when the prefix was unquoted.




v0.7.8
====================

**Added:**

* ``xonsh.lib.collections.ChainDB``, a chain map which merges mergable fields


**Fixed:**

* Pass all params to voxapi.create
* PTK tab-completion now auto-accepts completion if only one option is present
  (note that fix is only for PTK2)




v0.7.7
====================

**Added:**

* A xontrib which adds support for autojump to xonsh
* Added new env-var ``XONSH_HISTORY_MATCH_ANYWHERE``. If set to ``True`` then
  up-arrow history matching will match existing history entries with the search
  term located anywhere, not just at the beginning of the line. Default value is
  ``False``


**Changed:**

* Improved iteration over virtual environments in ``Vox.__iter__``


**Fixed:**

* Fix for ``Enter`` not returning from Control-R search buffer
* Fixed automatic wrapping of many subprocesses that spanned multiple lines via
  line continuation characters with logical operators separating the commands.
  For example, the following now works:

  .. code-block:: sh

        echo 'a' \
        and echo 'b'
* Environment swapping would not properly reraise errors due to weird
  Python name binding issue.




v0.7.6
====================

**Added:**

* Callable aliases may now accept a ``stack`` argument. If they do, then the
  stack, as computed from the aliases call site, is provided as a list of
  ``FrameInfo`` objects (as detailed in the standard library ``inspect``
  module). Otherwise, the ``stack`` parameter is ``None``.
* ``SubprocSpec`` now has a ``stack`` attribute, for passing the call stack
  to callable aliases. This defaults to ``None`` if the spec does not
  need the stack. The ``resolve_stack()`` method computes the ``stack``
  attribute.


**Changed:**

* xonsh/environ.py
  Exceptions are caught in the code executed under Env.swap()


**Fixed:**

* Scripts are now cached by their realpath, not just abspath.
* Fixed a potential crash (``AssertionError: wrong color format``) on Python 3.5 and prompt_toolkit 1.
* The ``completer`` command now correctly finds completion functions
  when nested inside of other functions.
* Fixed a crash when using the ``$XONSH_STDERR_PREFIX/POSTFIX`` with
  prompt_toolkit and Pygments 2.2.




v0.7.5
====================

**Fixed:**

* Recent command history in ptk2 prompt now returns most recently executed
  commands first (as expected)
* Fixed a regression taat prevented the readline backend from beeing used. This
  regression was caused by the new ansi-color names, which are incompatible with
  pygments 2.2.




v0.7.4
====================

**Added:**

* New ``xonsh-cat`` command line utility, which is a xonsh replacement
  for the standard UNIX ``cat`` command.
* The new ``xonsh.xoreutils.cat.cat_main()`` enables the ``xonsh.xoreutils.cat``
  module to be run as a command line utility.
* New ``CommandsCache.is_only_functional_alias()`` and
  ``CommandsCache.lazy_is_only_functional_alias()`` methods for determining if
  if a command name is only implemented as a function, and thus has no
  underlying binary command to execute.
* ``xonsh.xontribs.xontribs_load()`` is a new first-class API for loading
  xontribs via a Python function.
* ``$COMPLETIONS_DISPLAY`` now supports readline-like behavior on
  prompt-toolkit v2.


**Changed:**

* The xonsh Jupyter kernel now will properly redirect the output of commands
  such as ``git log``, ``man``, ``less`` and other paged commands to the client.
  This is done by setting ``$PAGER = 'cat'``. If ``cat`` is not available
  on the system, ``xonsh-cat`` is used instead.
* The ``setup()`` function for starting up a working xonsh has ``aliases``,
  ``xontribs``, and ``threadable_predictors`` as new additional keyword
  arguments for customizing the loading of xonsh.


**Fixed:**

* Fixed a bug with converting new PTK2 colors names to old names when using PTK1 or Jupyter
    as the shell type.
* ``CommandsCache.locate_binary()`` will now properly return None when
  ``ignore_alias=False`` and the command is only a functional alias,
  such as with ``cd``. Previously, it would return the name of the
  command.
* Fixed issue with ``$COMPLETIONS_DISPLAY`` raising an error on
  prompt-toolkit v2 when the value was not set to ``multi``.
* ValueError when executing ``vox list``




v0.7.3
====================

**Added:**

* Add the ``PROMPT_TOOLKIT_COLOR_DEPTH`` environment to xonsh default environment.
  Possible values are ``DEPTH_1_BIT``/``MONOCHROME``,
  ``DEPTH_4_BIT``/``ANSI_COLORS_ONLY``, ``DEPTH_8_BIT``/``DEFAULT``, or ``DEPTH_24_BIT``/``TRUE_COLOR``.
  Note: not all terminals support all color depths.
* New way to fix unreadable default terminal colors on Windows 10. Windows 10
  now supports true color in the terminal, so if prompt toolkit 2 is
  installed Xonsh will use a style with hard coded colors instead of the
  default terminal colors. This will give the same color experience as on linux an mac.
  The behaviour can be disabled with ``$INTENSIFY_COLORS_ON_WIN``
  environment variable.
* New ``JupyterShell`` for interactive interfacing with Jupyter.


**Changed:**

* All ansicolor names used in styles have ben updated to the color names used by prompt_toolkit 2.
  The new names are are much easier to understand
  (e.g. ``ansicyan``/``ansibrightcyan`` vs. the old ``#ansiteal``/``#ansiturquoise``). The names are automatically
  translated back when using prompt_toolkit 1.


**Removed:**

* Removed support for pygments < 2.2.


**Fixed:**

* New ansi-color names fixes the problem with darker colors using prompt_toolkit 2 on windows.
* Fixed a problem with the color styles on prompt toolkit 2. The default pygment
  style is no longer merged into style selected in xonsh.
* The JupyterKernel has been fixed from a rather broken state.




v0.7.2
====================

**Added:**

* ``history show`` builtin now supports optional ``-0`` parameter that switches
  the output to null-delimited. Useful for piping history to external filters.


**Fixed:**

* If exception is raised in indir context manager, return to original directory
* Fixed issue that autocomplete menu does not display
  at terminal's maximum height




v0.7.1
====================

**Added:**

* Added feature to aliases.
* ``xonsh.lib.os.rmtree()`` an rmtree which works on windows properly (even with
  git)


**Changed:**

* set default value of ``$AUTO_SUGGEST_IN_COMPLETIONS=False``
* Use the ``pygments_cache.get_all_styles()`` function instead of
  interacting directly with pygments.


**Fixed:**

* Fixed issue with ``$ARG<N>`` varaibles not being passed to subprocesses correctly.
* Fixed issue with multiline string inside of ``@(expr)`` in
  unwrapped subprocesses. For example, the following now works::

    echo @("""hello
    mom""")
* ``CommandPipeline.output`` now does properly lazy, non-blocking creation of
  output string. ``CommandPipeline.out`` remains blocking.
* Fix regression in ``INTENSIFY_COLORS_ON_WIN`` functionality due to prompt_toolkit 2 update.
* Fixed issue that can't insert quotation marks and double quotes
  for completion.
* Fixed issue with ``SyntaxErrors`` being reported on the wrong line
  when a block of code contained multiple implicit subprocesses.
* ``prompt_toolkit >= 2`` will start up even if Pygments isn't present
* Fixed a regression with ``xonfig styles`` reporting ``AttributeError: module 'pygments' has no attribute 'styles'``
* ptk dependent xontribs (that use custom keybindings) now work with both ptk1
  and ptk2
* Fixed async tokenizing issue on Python v3.7.




v0.7.0
====================

**Added:**

* Added a hook for printing a spcial display method on an object.
* Support for ``prompt_toolkit 2.0``
* The ``--shell-type`` (``$SHELL_TYPE``) may now be specified using
  shortcuts, such as ``rl`` for ``readline`` and ``ptk2`` for
  ``prompt_toolkit2``. See ``xonsh --help`` for a full listing
  of available aliases.


**Fixed:**

- Restored AUGASSIGN_OPS definition, which was inadvertently removed.




v0.6.10
====================

**Added:**

* ``xonsh.lib.subprocess.check_output`` as a ``check_output`` drop in


**Fixed:**

* ``xonsh.lib.subprocess.run`` doesn't change dirs unless asked




v0.6.9
====================

**Added:**

* New xonsh standard library ``xonsh.lib`` subpackage
* ``xonsh.lib.os.indir`` a context manager for temporarily entering into a directory
* ``xonsh.lib.subprocess.run`` and ``xonsh.lib.subprocess.check_call``
  subprocess stubs using ``xonsh`` as the backend


**Fixed:**

* update xoreutils._which.which() for python 3.x support.
* Fixed issue with incorrect strip lengths for prefixes with quotes in them
* Fixed bash script to also consider leading double quotes and not just single
  quotes
* Launching xonsh with prompt_toolkit version 2.x no longer fails, and instead fallsback to readline shell. This is a patch for until prompt_toolkit 2.x support is fully implemented. See PR #2570




v0.6.8
====================

**Fixed:**

* completions relative to ``CDPATH`` only trigger when used with ``cd``
* Import of ``ctypes.util`` is now explictly performed, as needed.
  Python v3.7 no longer imports this module along with ``ctypes``.
* Fixed issue with pygments-cache not properly generating a cache the first
  time when using prompt-toolkit. This was due to a lingering lazy import
  of ``pkg_resources`` that has been removed.
* Removed duplicate ``pip`` completer
* ``bash_completion`` no longer returns invalid prefix lengths for directories
  containing escape file names
* Fixed error when using redirection (e.g., >) on Windows.




v0.6.7
====================

**Changed:**

* Xonsh live example has been re-added back to the documentation.


**Fixed:**

* Fixed issue where xonsh would fail to properly return the terminal prompt
  (and eat up 100% CPU) after a failed subprocess command in interactive mode
  if ``$RAISE_SUBPROC_ERROR = True``.
* ``xonsh.tokenize.tok_name`` no longer mutates the standard library ``tokenize.tok_name``.
  A copy is made on import instead.




v0.6.6
====================

**Added:**

* A multipurpose add method to EnvPath. For example:

  .. code-block:: xonshcon

    >>> $PATH
    EnvPath(
    ['/usr/bin', '/usr/local/bin', '/bin']
    )
    >>> $PATH.add('~/.local/bin', front=True); $PATH
    EnvPath(
    ['/home/user/.local/bin', '/usr/bin', '/usr/local/bin', '/bin']
    )
    >>> $PATH.add('/usr/bin', front=True, replace=True); $PATH
    EnvPath(
    ['/usr/bin', '/home/user/.local/bin', '/usr/local/bin', '/bin']
    )

* Added ``pygments-cache`` project in order to reduce startup time.


**Changed:**

* built_ins.py, corrected a typo.
* test/test_news.py
  It now uses regex to verify the format of rst files
* Mercurial (``hg``) will no longer run in a threadable subprocess when
  it is run in interactive mode.


**Fixed:**

* issue 2313




v0.6.5
====================

**Added:**

* Wizard ``FileInsterter`` node class now has ``dumps()`` method for
  converting a mapping to a string to insert in a file.


**Fixed:**

* Fixed issue with ``xonfig wizard`` writer failing to write valid run control
  files for environment variables that are containter types. In particular,
  the storage of ``$XONSH_HISTORY_SIZE`` has been fixed.




v0.6.4
====================

**Changed:**

* Error message improved for sourcing foreign shells, when file cannot be found
  or there is a syntax error.


**Fixed:**

* Fixed issues with readline completer tab completing entries
  with spaces.
* Fixed ``xonsh.tools.columnize()`` bug the prevented single-row
  input from being columnized correctly.
* Now honor ASYNC and AWAIT as keywords in tokenizer on
  Python 3.7.




v0.6.3
====================

**Added:**

* Docs for using ``@(<expr>)`` as a way to run commands and a gotcha about
  list of strings vs single string expressions.
* Ubuntu versions which xonsh is packaged for (with xonsh versions)


**Changed:**

* When reporting errors without a traceback (i.e. ``$XONSH_SHOW_TRACEBACK = False``) and the error is a ``XonshError``
  the exception type is not longer printed.
* ``CommandPipeline.proc`` may now be ``None``, to accomodate when the process
  fails to even start (i.e. a missing command or incorrect permisions).


**Fixed:**

* The ``curl`` command will now be run in a thread, which prevents documents that
  do not end in a newline from writing over the next prompt and vice versa.
* Fix bug on Windows when ``PATHEXT`` environment variable did not exist.
  This also fixes building the xonsh documentation on Windows.
* Fixed a bug in the `free_cwd <http://xon.sh/xontribs.html#free-cwd>`__ Windows Xontrib, which caused the prompt to error if the current directory is
  deleted/renamed from an other process.
* Fixed issue with ``$XONSH_SHOW_TRACEBACK`` not being respected in subprocess
  mode when the command could not be found or had incorrect permissions.




v0.6.2
====================

**Added:**

* Release tarballs now include licenses and minimal documentation for xonsh and ply
* Wizard now has a ``FileInserter`` node that allows blocks to be
  inserted and replaced inside of a file. This adheres to conversion
  rules fordumping as provided on this node.
* New ``xonsh.wizard.StateVisitor.flatten()`` method for flattening the
  current state.


**Changed:**

* The xonsh startup wizard will only be triggered if no xonshrc files exist
  and the file ``~/.local/config/xonsh/no-wizard`` is not present.
* The ``xonfig wizard`` command will now run write out to the xonshrc file.
* Wizard nodes ``Save`` and ``Load`` had their names changed to ``SaveJSON``
  and ``LoadJSON``.


**Removed:**

* Static configuration is dead (``config.json``), long live run control (``xonshrc``)!
* The following evironment variables have been removed as they are no longer needed:
  ``$LOADED_CONFIG`` and ``$XONSHCONFIG``.
* Many support functions for static configuration have also been removed.


**Fixed:**

* Files starting with ``#`` are auto-escaped by TAB completion




v0.6.1
====================

**Added:**

* Support for MSYS2.
* New ``xonsh.main.setup()`` function for starting up xonsh in 3rd party
  packages.


**Changed:**

* Updated CircleCI to use circle version 2.0
* Replaced StopIteration with return in CommandPipeline.iterraw.
* Xonsh run control now also looks for the XDG-compliant file
  ``~/.config/xonsh/rc.xsh`` at startup.


**Fixed:**

* Clean out ``$LINES`` and ``$COLUMNS`` if set, preventing some programs from drawing weirdly
* cat from xoreutils now outputs in configured encoding
* Fixed hanging issue with pipelines whose middle processes exit before the
  first or last process.
* Fixed issue where xonsh would deduplicate spaces from bash autocompletions.
* Fixed failing redirections from stderr to stdout when the command
  being executed was a callable alias.
* Ensure that the ``free_cwd`` contrib can only be active on pure Windows.
* Made an exceptional case in ``iglobpath()`` more robust when Python globbing
  fails for due to strange scrandir issue.
* Unexpected process suspension on Cygwin and MSYS2.
* ``$XONSH_APPEND_NEWLINE`` will now default to True when in interactive mode.
* Fixed issue with uncalled lambdas being run in subproc mode.
* Lambda nodes not have proper line and column numbers in AST.
* Properly throw ``SyntaxError`` when no kwargs are defined
  in a kwarg-only function. This used to throw a
  ``TypeError: 'NoneType' object is not iterable``.
* Addressed issue where encoding and errors were None when teeing output.
* Commands like ``git c`` would complete to ``git 'checkout '`` because git adds an extra space
  to the end of the completion, which was being captured in the completion. Xonsh now fixes the git issue
  while retaining all whitespace when there is other internal whitespace.




v0.6.0
====================

**Added:**

* Added an alias command, matching bash's implementation, available as part of bashisms.
* New ``$AUTO_SUGGEST_IN_COMPLETIONS`` environment variable that enables/disables
  whether the auto-suggestion result appears in the tab completions.
* Added ``__add__()`` and ``__radd__()`` methods to ``EnvPath``.
* Xonsh now supports f-strings, as in Python v3.6+.
* Added ``ipython`` as unthreadable in command cache threadabilty predictors.
* Added ``whole_word_jumping`` xontrib
* Added ``$XONSH_APPEND_NEWLINE`` environment variable
* Support for PEP 515: Underscores in Numeric Literals
*  ``xonsh.color_tools.make_palette()``

   Simple rename of the pre-existing
   ``xonsh.color_tools.make_pallete()`` function.

*  ``xonsh.tools.decorator()`` function/method decorator.

   This allows for an API function to be annotated with a
   decorator that documents deprecation, while also tying in
   functionality that will warn a user that the function has
   been deprecated, and, raise an ``AssertionError`` if the
   function has passed its expiry date.
* New xontrib ``schedule`` (Xonsh Task Scheduler)


**Changed:**

* ``on_pre_prompt`` is now fired before prompt calculations are made, allowing modifications to the prompt.
* ``emacsclient`` will now return false in the threadable predictors.
* Improved the autopair behavior to match that of popular code editors.
* Moved the lazy ``pkg_resources`` package back to its original
  place. The will hopefully address some of the slowdown issues
  experiances on some platforms.
* When xonsh is used to run an ``xsh`` script, the ``xonshrc`` is not loaded
* Change in the behavior of the default predictor with binary analysis. The pattern ``libgpm`` is use, assuming when ``gpm`` is used the program is not threadable. This change solves issues with programs as ``links``.
* Error messages added to the ``source`` command if it is used with a language
  that is not xonsh or Python.


**Deprecated:**

*  ``xonsh.color_tools.make_pallette()``

   Deprecated in release 0.5.10 and will be removed in release 0.6.0.


**Fixed:**

* Now f-strings can be used inside @() without explicit enclosing command in ![]
* Fix for ``x, y, *z = ...`` unpacking.
* Git branch detection now correctly passes the environment down to the subprocess
  call.  This allows for branch detection when git is installed into a non-standard
  location.
* Escape regex characters in ``path_complete`` to avoid regex parsing errors for
  certain combinations of characters in path completer
* gistatus: Fixed hash not being shown when in detaced HEAD and there are no tags
* Fix branch colorization when ``git`` or ``hg`` are aliases.
* Fixed leftover ``.git/index.lock`` in ``gitstatus``
* Made JSON history loading more robust to corrupt files.
* Starting a new command with an open parentheses will no longer
  throw a traceback when ``$UPDATE_COMPLETIONS_ON_KEYPRESS`` is
  ``True``.
* Automatically wrapping subprocess calls would sometimes include
  semincolons and other line-ending tokens, rather than stopping at them.
  This has been fixed.
*  Numerous spelling errors in documentation, docstrings/comments, text
   strings and local variable names.

*  Spelling error in the ``xonsh.color_tools.make_pallete()`` public
   function declaration. This was fixed by renaming the function to
   ``xonsh.color_tools.make_palette()`` while maintaining a binding
   of ``make_pallete()`` to the new ``make_palette()`` in case users
   are already used to this API.
* Fixed issue with starting triple quote strings being run as a command.
* Fixed a problem with escaping charet (^) character for cmd.exe in the source-cmd function.
* ``EOF in multi-line statement`` errors were misreported as being on line 0.
  Now they are correctly reported as being on the last line of the file.




v0.5.12
====================

**Fixed:**

* Fixed ``release.xsh`` to prevent it from dirtying the repo on release and
  leading to an unwanted ``.dev`` suffix on the version number




v0.5.11
====================

**Added:**

* ``release.xsh`` creates a github release with the merged news entries as the
  release body


**Fixed:**

* ``xonfig`` now displays the proper value for "on linux"


v0.5.10
====================

**Added:**

* Added ``xclip`` and ``repo`` to default threadable predictors (Issues #2355
  and #2348)
* Pretty printing of the $PATH variable
* Add "fzf-widgets" xontrib which provides fuzzy search productivity widgets
  with on custom keybindings to xontrib list.
* New ``free_cwd`` xontrib for Windows, which prevent the current directory from being locked when the prompt is shown.
  This allows the other programs or Windows explorer to delete the current or parent directory. This is accomplished by
  resetting the CWD to the users home directory temporarily while the prompt is displayed. The directory is still locked
  while any commands are processed so xonsh still can't remove it own working directory.


**Changed:**

* Codecov threshold to 2%


**Removed:**

* On Windows environments variables in wrapped like``%foo%`` are no longer expanded automatically.


**Fixed:**

* Fixed the ``--rc`` option so it now runs xonsh with the specified rc file
* ``@$`` operator now functions properly when returned command is an alias
* Correct line continuation would not work on Windows if the line continuations were used
  in the ``xonshrc`` file.
* Fixed a regression in the Windows ``sudo`` command, that allows users to run elevated commands in xonsh.
* Fix echo command from xoreutils.
* Fixed a bug on Windows which meant xonsh wasn't using PATH environment variable but instead relying on a default
  value from the windows registry.




v0.5.9
====================

**Added:**

* Add ``Alt .`` keybinding to ``bashisms-xontrib`` to insert last argument of
  previous command into current buffer


**Fixed:**

* Fix crash when openSSH version of bash is on PATH on Windows.
* Added missing ensurers to make sure that ``bool`` env_vars are bools and
  ``int`` env_vars are integers:

  * ``DIRSTACK_SIZE``
  * ``EXPAND_ENV_VARS``
  * ``PUSHD_MINUS``
  * ``PUSHD_SILENT``
  * ``SUGGEST_COMMANDS``
  * ``SUGGEST_MAX_NUM``
  * ``SUGGEST_THRESHOLD``




v0.5.8
====================

**Changed:**

* The ``xonsh.platform.os_environ`` wrapper is  now case-insensitive and
  case-preserving on Windows.
* The private ``_TeeStd`` class will no longer attempt to write to a
  standard buffer after the tee has been 'closed' and the standard
  buffer returned to the system.


**Fixed:**

* Fixed a bug on py34 where os.scandir was used by accident.
* Line continuations (``\\``) is subproc mode will no longer consume the
  surrounding whitespace.
* Fixed a bug if foreign_shell name was not written in lower case in
  the static configuration file ``config.json``
* Fixed a regression on Windows where caused ``which`` reported that the
  ``PATH`` environment variable could not be found.
* Fixed issue with foregrounding jobs that were started in the background.
* Fixed that ``Ctrl-C`` crashes xonsh after running an invalid command.
* Fixed an potential ``ProcessLookupError`` issue, see #2288.




v0.5.7
====================

**Added:**

* New ``color_tools`` module provides basic color tools for converting
  to and from various formats as well as creating palettes from color
  strings.
* Redirections may now be used in string and list-of-strings
  aliases.
* Subprocess redirection may now forego the whitespace between the
  redirection and a file name.  For example,
  ``echo hello world >/dev/null``.
* Add a ``-P`` flag to the ``cd`` function in order to change directory and
  following symlinks.
* ``xonfig tutorial`` command to launch the http://xon.sh/tutorial in the
  browser.
* ``@(...)`` syntax now supports generators and tuples without parentheses.
* Sourcing foreign shells now have the ``--show`` option, which
  lets you see when script will be run, and the ``--dryrun``
  option which prevents the source from actually taking place.
  Xonsh's foreign shell API also added these keyword arguments.
* Subprocess mode now supports subshells. Place any xonsh
  code between two parentheses, e.g. ``(cmd)``, to run
  this command in a separate xonsh subprocess.
* Foreign shell aliases now have the ability to take extra arguments,
  if needed.
* Xonsh will issue a warning message when the current working
  directory has been remove out from under it and not replaced
  prior to running the next command.
* Line continuation backslashes are respected on Windows in the PTK shell if
  the backspace is is preceded by a space.
* Added ``ponysay`` as a command which will usually not run in a
  threaded mode in the commands cache.
* New ``jsonutils`` module available for serializing special
  xonsh objects to JSON.


**Changed:**

* The literal tokens ``and`` and ``or`` must be surrounded by
  whitespace to delimit subprocess mode. If they do not have
  whitespace on both sides in subproc mode, they are considered
  to be part of a command argument.
* The ``xontrib`` command is now flagged as unthreadable and will be
  run on the main Python thread. This allows xontribs to set signal
  handlers and other operations that require the main thread.
* nvim (Neovim) has been flagged as unthreadable
* The interactive prompt will now catch ``SystemExit`` and, instead
  of exiting the session, will refresh the prompt. This is the same
  process as for keyboard interrupts.
* Xonsh no longer launches the wizard for new users. Instead a welcome screen is
  shown which says how to launch the wizard.
* Added Windows ``expanduser()``-like function which prevents
  the expansion of ``~`` that are not followed by a path
  separator.
* Collecting xonsh history files was reported to have random runtime
  OSError failures. This exception is now handled, just in case. The
  The exception will still be printed in debug mode.
* ``Shell.stype`` has been renamed to ``Shell.shell_type``.
* The configuration wizard now displays the proper control sequence to leave
  the wizard at the to start of the wizard itself. Note that this is Ctrl+D for
  readline and Ctrl+C for prompt-toolkit.
* Callable alias proxy functions are now more friendly to
  ``functools.partial()``.
* ``prompt.vc.get_hg_branch`` now uses ``os.scandir`` to walk up the filetree
  looking for a ``.hg`` directory. This results in (generally) faster branch
  resolution compared to the subprocess call to ``hg root``.
* Xonsh's script and code caches will are now invalidated whenever the
  xonsh version changes for a given Python version.
* Autowrapping of subprocess globs has been improved to cover
  more cases that are ambiguous with Python syntax.
* Job control info when foregrounding or backgrounding jobs will now
  only be displayed when xonsh is in interactive mode.
* Enabled virtual terminal processing in the prompt-toolkit shell for Windows.


**Fixed:**

* 3rd party pygments styles (like solorized or monokailight) are now
  able to be used in xonsh. These styles are dynamically created upon
  first use, rather than being lazily loaded by xonsh.
* On Windows, ``os.environ`` is case insensitive. This would potentially
  change the case of environment variables set into the environment.
  Xonsh now uses ``nt.environ``, the case sensitive counterpart, to avoid
  these issues on Windows.
* Fix how ``$PWD`` is managed in order to work with symlinks gracefully
* ``history replay`` no longer barfs on ``style_name`` when setting up the
  environment
* ``Shell.shell_type`` is now properly set to the same value as ``$SHELL_TYPE``.
* Fixed ``source-zsh`` to work with zsh v5.2.
* Fixed issue where ``del (x, y)`` would raise a syntax error.
* Certain vim commands issue commands involving subshells,
  and this is now supported.
* Null bytes handed to Popen are now automatically escaped prior
  to running a subprocess. This prevents Popen from issuing
  embedded null byte exceptions.
* Xonsh will no longer crash is the current working directory is
  removed out from under it.
* Multiline strings can now be written in subprocess mode.
* PTK completions will now correctly deduplicate autosuggest completions
  and display completions values based on the cursor position.
* Fixed bug where trailing backspaces on Windows paths could be interpreted
  as line continuations characters. Now line continuation characters must be
  preceded by a space on Windows. This only applies to xonsh in interactive
  mode to ensure  scripts are portable.
* Importing ``*.xsh`` files will now respect the encoding listed in
  that file and properly fallback to UTF-8. This behaviour follows
  the rules described in PEP 263.
* Wizard is now able to properly serialize environment paths.


v0.5.6
====================

**Added:**

* New core utility function aliases (written in pure Python) are now
  available in ``xonsh.xoreutils``. These include: ``cat``, ``echo``,
  ``pwd``, ``tee``, ``tty``, and ``yes``. These are not enabled by default.
  Use the new ``coreutils`` xontrib to load them.
* CircleCI test post codecov run
* The ``trace`` will automatically disable color printing when
  stdout is not a TTY or stdout is captured.
* New ``jedi`` xontrib enables jedi-based tab completions when it is loaded.
  This supersedes xonsh's default Python-mode completer.
* The lexer has a new ``split()`` method which splits strings
  according to xonsh's rules for whitespace and quotes.
* New events for hooking into the Python import process are now available.
  You can now provide a handler for:

  - ``on_import_pre_find_spec``
  - ``on_import_post_find_spec``
  - ``on_import_pre_create_module``
  - ``on_import_post_create_module``
  - ``on_import_pre_exec_module``
  - ``on_import_post_exec_module``


**Changed:**

* The prompt toolkit shell's first completion will now be the
  current token from the auto-suggestion, if available.
* Sourcing foreign shells will now safely skip applying aliases
  with the same name as existing xonsh aliases by default.
  This prevents accidentally overwriting important xonsh standard
  aliases, such as ``cd``.


**Fixed:**

* Threadable prediction for subprocesses will now consult both the command
  as it was typed in and any resolved aliases.
* The first prompt will no longer print in the middle of the line if the user has
  already started typing.
* Windows consoles will now automatically enable virtual terminal processing
  with the readline shell, if available. This allows the full use of ANSI
  escape sequences.
* On the Windows readline shell, the tab-completion suppression prompt will no
  longer error out depending on what you press.
* Fixed issue with subprocess mode wrapping not respecting line continuation
  backslashes.
* Handle a bug where Bash On Windows causes platform.windows_bash_command()
  to raise CalledProcessError.
* Fixed issues pertaining to completing from raw string paths.
  This is particularly relevant to Windows, where raw strings
  are inserted in path completion.
* Replace deprecated calls to ``time.clock()`` by calls to
  ``time.perf_counter()``.
* Use ``clock()`` to set the start time of ``_timings`` in non-windows instead
  of manually setting it to ``0.0``.
* The ``trace`` utility will now correctly color output and not
  print extraneous newlines when called in a script.
* The ``@$(cmd)`` operator now correctly splits strings according to
  xonsh semantics, rather than just on whitespace using ``str.split()``.
* The ``mpl`` xontrib has been updated to improve matplotlib
  handling. If ``xontrib load mpl`` is run before matplotlib
  is imported and xonsh is in interactive mode, matplotlib
  will automatically enter interactive mode as well. Additionally,
  ``pyplot.show()`` is patched in interactive mode to be non-blocking.
  If a non-blocking show fails to draw the figure for some reason,
  a regular blocking version is called.
* Fixed issues like ``timeit ls`` causing OSError - "Inappropriate ioctl
  for device".
* Fixed a potential "OSError: [Errno 22] Invalid argument" to increase job
  control stability.




v0.5.5
====================

**Added:**

* New ``--rc`` command line option allows users to specify paths to run control
  files from the command line. This includes both xonsh-based and JSON-based
  configuration.
* New ``$UPDATE_COMPLETIONS_ON_KEYPRESS`` controls whether or not completions
  will automatically display and update while typing. This feature is only
  available in the prompt-toolkit shell.


**Changed:**

* Xonsh scripts now report ``__file__`` and ``__name__`` when run as scripts
  or sourced. These variables have the same meaning as they do in Python
  scripts.
* ``$XONSHRC`` and related configuration variables now accept JSON-based
  static configuration file names as elements. This unifies the two methods
  of run control to a single entry point and loading system.
* The ``xonsh.shell.Shell()`` class now requires that an Execer instance
  be explicitly provided to its init method. This class is no longer
  responsible for creating an execer an its dependencies.
* Moved decorators ``unthreadable``, ``uncapturable`` from
  ``xonsh.proc`` to ``xonsh.tools``.
* Some refactorings on jobs control.


**Deprecated:**

* The ``--config-path`` command line option is now deprecated in favor of
  ``--rc``.


**Removed:**

* ``xonsh.environ.DEFAULT_XONSHRC`` has been removed due to deprecation.
  For this value, please check the environment instead, or call
  ``xonsh.environ.default_xonshrc(env)``.


**Fixed:**

* Command pipelines that end in a callable alias are now interruptable with
  ``^C`` and the processes that are piped into the alias have their file handles
  closed. This should ensure that the entire pipeline is closed.
* Fixed issue where unthreadable subprocs were not allowed to be
  captured with the ``$(cmd)`` operator.
* The ``ProcProxy`` class (unthreadable aliases) was not being executed and would
  hang if the alias was capturable. This has been fixed.
* Fixed a ``tcsetattr: Interrupted system call`` issue when run xonsh scripts.
* Fixed issue with ``ValueError`` being thrown from ``inspect.signature()``
  when called on C-extension callables in tab completer.
* Fixed issue that ``ls | less`` crashes on Mac.
* Threadable prediction was incorrectly based on the user input command, rather than
  the version where aliases have been resolved. This has been corrected.


v0.5.4
====================

**Added:**

* Add alias ``xip`` ("kip") so that xonsh's Python environment (whatever that is) can be modified.
* HistoryEntry, a SimpleNamespace object that represents a command in history.
* ``xonsh.completers.bash_completion`` module
* Added option to report timing information of xonsh startup times. Start xonsh
  with the ``--timings`` flag to use the feature.
* The Python tab completer will now complete the argument names of functions
  and other callables.
* Uptime module added to ``xonsh.xoreutils``. This can report the system
  boot time and up time.
* The environment variable ``XONSH_HISTORY_BACKEND`` now also supports a
  value of class type or a History Backend instance.
* ``on_envvar_new`` event that fires after a new envvar is created.
* ``on_envvar_change`` event that fires after an envvar is changed.


**Changed:**

* history indexing api to be more simple, now returns HistoryEntry.
* Decoupled ``bash_completion`` from xonsh project and added shim back to
  xonsh.
* The JSON history backend will now unlock history files that were created
  prior to the last reboot.


**Fixed:**

* Fixed broken bash completions on Windows if 'Windows Subsystem for Linux' is installed.
* Readline history would try to read the first element of history prior to
  actually loading any history. This caused an exception to be raised on
  Windows at xonsh startup when using pyreadline.
* Fixed issue with readline tab completer overwriting initial prefix in
  some instances.
* Fixed issue wherein if ``git`` or (presumably) ``hg`` are aliased, then branch
  information no longer appears in the ``$PROMPT``
* Fixed an issue with commands that background themselves (such as
  ``gpg-connect-agent``) not being able to be run from within xonshrc.




v0.5.3
====================

**Added:**

* Tab completion xontrib for python applications based on click framework.
* Added ``on_transform_command`` event for pre-processing that macros can't handle.
* Autodetection of backgroundability by binary analysis on POSIX.
* New argument ``expand_user=True`` to ``tools.expand_path``.
* New ``$COMPLETION_QUERY_LIMIT`` environment variable for setting the
  number of completions above which the user will be asked if they wish to
  see the potential completions.
* Users may now redirect stdout to stderr in subprocess mode.


**Changed:**

* The ``Block`` and ``Functor`` context managers from ``xonsh.contexts`` have been
  rewritten to use xonsh's macro capabilities. You must now enter these via the
  ``with!`` statement, e.g. ``with! Block(): pass``.
* The ``distributed`` xontrib now needs to use the ``with!`` statement, since it
  relies on ``Functor``.
* ``telnet`` has been flagged as unthreadable.
* When ``$DYNAMIC_CWD_ELISION_CHAR`` is non empty and the last dir of cwd is too
  long and shortened, the elision char is added at the end.
* ``pygments`` is no longer a strict dependency of the ``prompt_toolkit``
  backend. If ``pygments`` is not installed, the PTK backend will use the
  default ansi color settings from the terminal. Syntax highlighting requires
  that ``pygments`` is installed.
* Events are now keyword arguments only
* Restored ``on_precommand`` to its original signature.
* Move ``built_ins.expand_path`` to ``tools.expand_path``.
* Rename ``tools.expandpath`` to ``tools._expandpath``.
* Added ``gvim`` command to unthreadable predictors.
* The ``source`` alias now passes ``$ARGS`` down to file it is sourcing.


**Removed:**

* ``XonshBlockError`` has been removed, since it no longer serves a purpose.


**Fixed:**

* ``PopenThread`` will now re-issue SIGINT to the main thread when it is
  received.
* Fixed an issue that using sqlite history backend does not kill unfinished
  jobs when quitting xonsh with a second "exit".
* Fixed an issue that xonsh would fail over to external shells when
  running .xsh script which raises exceptions.
* Fixed an issue with ``openpty()`` returning non-unix line endings in its buffer.
  This was causing git and ssh to fail when xonsh was used as the login shell on the
  server. See https://mail.python.org/pipermail/python-list/2013-June/650460.html for
  more details.
* Restored the ability to ^Z and ``fg`` processes on posix platforms.
* CommandPipelines were not guaranteed to have been ended when the return code
  was requested. This has been fixed.
* Introduce path expansion in ``is_writable_file`` to fix
  ``$XONSH_TRACEBACK_LOGFILE=~/xonsh.log``.
* Backgrounding a running process (^Z) now restores ECHO mode to the terminal
  in cases where the subprocess doesn't properly restore itself. A major instance
  of this behaviour is Python's interactive interpreter.
* Readline backend would not ask the user to confirm the printing of completion
  options if they numbered above a certain value. Instead they would be dumped to
  the screen. This has been fixed.
* Jupyter kernel was no longer properly running subprocess commands.
  This has been fixed.
* The filename is applied to the target of the ``source`` alias, providing better
  tracebacks.




v0.5.2
====================

**Added:**

* Added ``weechat`` to default predictors
* ``$DYNAMIC_CWD_ELISION_CHAR`` environment variable to control how a shortened
  path is displayed.


**Changed:**

* ``_ret_code`` function of ``prompt_ret_code`` xontrib return now ``None`` when
  return code is 0 instead of empty string allowing more customization of prompt
  format.


**Fixed:**

* Minor Python completer token counting bug fix.
* multiline syntax error in PTK shell due to buffer not being reset
* Segfaults and other early exit signals are now reported correctly,
  again.
* ``tests/bin/{cat,pwd,wc}`` shebang changed to python3




v0.5.1
====================

**Fixed:**

* Fixed xonfig raising error when xonsh is not installed from source.




v0.5.0
====================

**Added:**

* $XONTRIB_MPL_MINIMAL environment variable can be set to change if plots are minimalist or as-seen
* xontrib-mpl now supports iTerm2 inline image display if iterm2_tools python package is installed
* Xonsh now will fallback to other shells if encountered errors when
  starting up.
* Added entry to customization faq re: ``dirs`` alias (#1452)
* Added entry to customization faq re: tab completion selection (#1725)
* Added entry to customization faq re: libgcc core dump (#1160)
* Section about quoting in the tutorial.
* The ``$VC_HG_SHOW_BRANCH`` environment variable to control whether to hide the hg branch in the prompt.
* xonfig now contains the latest git commit date if xonsh installed
  from source.
* Alt+Enter will execute a multiline code block irrespective of cursor position
* Windows now has the ability to read output asynchronously from
  the console.
* Use `doctr <https://drdoctr.github.io/doctr/>`_ to deploy dev docs to github pages
* New ``xonsh.proc.uncapturable()`` decorator for declaring that function
  aliases should not be run in a captured subprocess.
* New history backend sqlite.
* Prompt user to install xontrib package if they try to load an uninstalled
  xontrib
* Callable aliases may now take a final ``spec`` argument, which is the
  corresponding ``SubprocSpec`` instance.
* New ``bashisms`` xontrib provides additional Bash-like syntax, such as ``!!``.
  This xontrib only affects the command line, and not xonsh scripts.
* Tests that create testing repos (git, hg)
* New subprocess specification class ``SubprocSpec`` is used for specifying
  and manipulating subprocess classes prior to execution.
* New ``PopenThread`` class runs subprocesses on a a separate thread.
* New ``CommandPipeline`` and ``HiddenCommandPipeline`` classes manage the
  execution of a pipeline of commands via the execution of the last command
  in the pipeline. Instances may be iterated and stream lines from the
  stdout buffer. These pipelines read from the stdout & stderr streams in a
  non-blocking manner.
* ``$XONSH_STORE_STDOUT`` is now available on all platforms!
* The ``CommandsCache`` now has the ability to predict whether or not a
  command must be run in the foreground using ``Popen`` or may use a
  background thread and can use ``PopenThread``.
* Callable aliases may now use the full gamut of functions signatures:
  ``f()``, ``f(args)``,  ``f(args, stdin=None)``,
  ``f(args, stdin=None, stdout=None)``, and `
  ``f(args, stdin=None, stdout=None, stderr=None)``.
* Uncaptured subprocesses now receive a PTY file handle for stdout and
  stderr.
* New ``$XONSH_PROC_FREQUENCY`` environment variable that specifies how long
  loops in the subprocess framework should sleep. This may be adjusted from
  its default value to improved performance and mitigate "leaky" pipes on
  slower machines.
* ``Shift+Tab`` moves backwards in completion dropdown in prompt_toolkit
* PromptFormatter class that holds all the related prompt methods
* PromptFormatter caching when building the prompt
* p-strings: ``p'/foo/bar'`` is short for ``pathlib.Path('/foo/bar')``
* byte strings: prefixes other than ``b'foo'`` (eg, ``RB'foo'``) now work
* Backticks for regex or glob searches now support an additional modifier
  ``p``, which causes them to return Path objects instead of strings.
* New ``BOTTOM_TOOLBAR`` environment variable to control a bottom toolbar as specified in prompt-toolkit
* New ``$XONSH_STDERR_PREFIX`` and ``$XONSH_STDERR_POSTFIX`` environment
  variables allow the user to print a prompt-like string before and after
  all stderr that is seen. For example, say that you would like stderr
  to appear on a red background, you might set
  ``$XONSH_STDERR_PREFIX = "{BACKGROUND_RED}"`` and
  ``$XONSH_STDERR_PREFIX = "{NO_COLOR}"``.
* New ``xonsh.pyghooks.XonshTerminal256Formatter`` class patches
  the pygments formatter to understand xonsh color token semantics.
* Load events are now available
* New events added: ``on_post_init``, ``on_pre_cmdloop``, ``on_pre_rc``, ``on_post_rc``, ``on_ptk_create``
* Completion for ``xonsh`` builtin functions ``xontrib`` and ``xonfig``
* Added a general customization FAQ page to the docs to collect various
  tips/tricks/fixes for common issues/requests
* ``test_single_command`` and ``test_redirect_out_to_file`` tests in ``test_integrations``
* Add note that the target of redirection should be separated by a space.


**Changed:**

* CircleCI now handles flake8 checks
* Travis doesn't allow failures on nightly
* ``get_hg_branch`` runs ``hg root`` to find root dir and check if we're in repo
* The default style will now use the color keywords (#ansired, #ansidarkred)
  to set colors that follow the terminal color schemes. Currently, this requires
  prompt_toolkit master (>1.0.8) and pygments master (2.2) to work correctly.
* ``vox activate`` now accepts relative directories.
* Updated the effectivity of ``$XONSH_DEBUG`` on debug messages.
* Better documentation on how to get nice colors in Windows' default console
* All custom prompt_toolkit key binding filters now declared with the
  ``@Condition`` decorator
* The style for the prompt toolkit completion menu is now lightgray/darkgray instead of turquoise/teal
* landscape.io linting now ignores ply directory
* ``history`` help messages to reflect subcommand usage
* Quote all paths when completion if any of the paths needs be quoted,
  so that bash can automatically complete to the max prefix of the paths.
* Tee'd reads now occur in 1kb chunks, rather than character-by-character.
* The ``which`` alias no longer has a trailing newline if it is captured.
  This means that ``$(which cmd)`` will simply be the path to the command.
* The following commands are, by default, predicted to be not threadable
  in some circumstances:

    * bash
    * csh
    * clear
    * clear.exe
    * cls
    * cmd
    * ex
    * fish
    * htop
    * ksh
    * less
    * man
    * more
    * mutt
    * nano
    * psql
    * ranger
    * rview
    * rvim
    * scp
    * sh
    * ssh
    * startx
    * sudo
    * tcsh
    * top
    * vi
    * view
    * vim
    * vimpager
    * xo
    * xonsh
    * zsh
* The ``run_subproc()`` function has been replaced with a new implementation.
* Piping between processes now uses OS pipes.
* ``$XONSH_STORE_STDIN`` now uses ``os.pread()`` rather than ``tee`` and a new
  file.
* The implementation of the ``foreground()`` decorator has been moved to
  ``unthreadable()``.
* ``voxapi.Vox`` now supports ``pathlib.Path`` and ``PathLike`` objects as virtual environment identifiers
* Renamed FORMATTER_DICT to PROMPT_FIELDS
* BaseShell instantiates PromptFormatter
* readline/ptk shells use PromptFormatter
* Updated the bundled version of ``ply`` to current master available
* vended ``ply`` is now a git subtree to help with any future updates
* ``WHITE``  color keyword now means lightgray and ``INTENSE_WHITE`` completely white
* Removed ``add_to_shell`` doc section from ``*nix`` install pages and instead
  relocated it to the general customization page
* Moved a few ``*nix`` customization tips from the linux install page to the general
  customization page


**Removed:**

* coverage checks
* ``CompletedCommand`` and ``HiddenCompletedCommand`` classes have been removed
  in favor of ``CommandPipeline`` and ``HiddenCommandPipeline``.
* ``SimpleProcProxy`` and ``SimpleForegroundProcProxy`` have been removed
  in favor of a more general mechanism for dispatching callable aliases
  implemented in the ``ProcProxyThread``  and ``ProcProxy`` classes.
* ``test_run_subproc.py`` in favor of ``test_integrations.py``
* Unused imports in many tests
* Many duplicated tests (copypasta)


**Fixed:**

* xontrib-mpl now preserves the figure and does not permanently alter it for viewing
* Fix up small pep8 violations
* Fixed a bug where some files are not showing using bash completer
* Fixed some issues with subprocess capturing aliases that it probably
  shouldn't.
* ``safe_readable()`` now checks for ``ValueError`` as well.
* The scroll bars in the PTK completions menus are back.
* Jupyter kernel installation now respects the setuptools ``root`` parameter.
* Fix ``__repr__`` and ``__str__`` methods of ``SubprocSpec`` so they report
  correctly
* Fixed the message printed when which is unable to find the command.
* Fixed a handful of sphinx errors and warnings in the docs
* Fixed many PEP8 violations that had gone unnoticed
* Fix failure to detect an Anaconda python distribution if the python was install from the conda-forge channel.
* current_branch will try and locate the vc binary once
* May now Crtl-C out of an infinite loop with a subprocess, such as
  ```while True: sleep 1``.
* Fix for stdin redirects.
* Backgrounding works with ``$XONSH_STORE_STDOUT``
* ``PopenThread`` blocks its thread from finishing until command has completed
  or process is suspended.
* Added a minimum time buffer time for command pipelines to check for
  if previous commands have executed successfully.  This is helpful
  for pipelines where the last command takes a long time to start up,
  such as GNU Parallel. This also checks to make sure that output has occurred.
  This includes piping 2+ commands together and pipelines that end in
  unthreadable commands.
* ``curr_branch`` reports correctly when ``git config status.short true`` is used
* ``pip`` completion now filters results by prefix
* Fixed streaming ``!(alias)`` repr evaluation where bytes where not
  streamed.
* Aliases that begin with a comma now complete correctly (no spurious comma)
* Use ``python3`` in shebang lines for compatibility with distros that still use Python 2 as the default Python
* STDOUT is only stored when ``$XONSH_STORE_STDOUT=True``
* Fixed issue with alias redirections to files throwing an OSError because
  the function ProcProxies were not being waited upon.
* Fixed issue with callable aliases that happen to call sys.exit() or
  raise SystemExit taking out the whole xonsh process.
* Safely flushes file handles on threaded buffers.
* Proper default value and documentation for ``$BASH_COMPLETIONS``
* Fixed readline completer issues on paths with spaces
* Fix bug in ``argvquote()`` functions used when sourcing batch files on Windows. The bug meant an extra backslash was added to UNC paths.
  Thanks to @bytesemantics for spotting it, and @janschulz for fixing the issue.
* pep8, lint and refactor in pytest style of ``test_ptk_multiline.py``, ``test_replay.py``
* Tab completion of aliases returned a upper cased alias on Windows.
* History show all action now also include current session items.
* ``proc.stream_stderr`` now handles stderr that doesn't have buffer attribute
* Made ``history show`` result sorted.
* Fixed issue that ``history gc`` does not delete empty history files.
* Standard stream tees have been fixed to accept the possibility that
  they may not be backed by a binary buffer. This includes the pipeline
  stdout tee as well as the shell tees.
* Fixed a bug when the pygments plugin was used by third party editors etc.
* CPU usage of ``PopenThread`` and ``CommandPipeline`` has been brought
  down significantly.




v0.4.7
====================

**Added:**

* Define alias for 'echo' on startup for Windows only.
* New coredev `AstraLuma <https://github.com/AstraLuma>`_ added
* ``which -a`` now searches in ``__xonsh_ctx__`` too
* Info about the xontrib cookiecutter template on xontrib tutorial
* xonsh's optional dependencies may now be installed with the pip extras ``ptk``, ``proctitle``, ``linux``, ``mac``, and ``win``.
* Env ``help`` method to format and print the vardocs for an envvar
* test_news fails if no empty line before a category
* more info on test_news failures
* Added ``on_precommand`` and ``on_postcommand`` `events </events.html>`_
* New ``FORMATTER_DICT`` entry ``gitstatus`` to provides informative git status
* FOREIGN_ALIASES_OVERRIDE envvar to control whether foreign aliases should
  override xonsh aliases with the same name.

* Warning on tutorial about foreign aliases being ignored if a xonsh alias
  exist with the same name if not FOREIGN_ALIASES_OVERRIDE.
* The prompt-toolkit shell now auto-inserts matching parentheses, brackets, and quotes. Enabled via the ``XONSH_AUTOPAIR`` environment variable
* Better syntax highlights in prompt-toolkit, including valid command / path highlighting, macro syntax highlighting, and more
* More info on tutorial about history interaction
* Entry on bash_to_xsh
* Macro context managers are now available via the ``with!``
  syntax.


**Changed:**

* Devguide reflects the current process of releasing through ``release.xsh``
* moved ``which`` from ``xonsh.aliases`` into ``xoreutils.which``
* ``xonsh.prompt.gitstatus.gitstatus`` now returns a namedtuple

* implementation of ``xonsh.prompt.vc_branch.get_git_branch`` and
  ``xonsh.prompt.vc_branch.git_dirty_working_directory`` to use 'git status --procelain'
* moved prompt formatting specific functions from ``xonsh.environ``
  to ``xonsh.prompt.base``
* All prompt formatter functions moved to ``xonsh.prompt`` subpackage
* Printing the message about foreign aliases being ignored happens only
  if XONSH_DEBUG is set.
* Use ``SetConsoleTitleW()`` on Windows instead of a process call.
* Tutorial to reflect the current history command argument functionality
* Macro function arguments now default to ``str``, rather than ``eval``,
  for consistency with other parts of the macro system.


**Removed:**

* aliases that use '!' in their name cause they clash with the macro syntax


**Fixed:**

* Fix regression where bash git completions where not loaded
  automatically when GitForWindows is installed.
* More tokens are now supported in subproc args, such as ``==``.
* Python completions now work without space delimiters, e.g. ``a=matpl<TAB>``
  will complete to ``a=matplotlib``
* Parser would fail on nested, captured suprocess macros. Now, it works,
  hooray!?
* now fires chdir event if OS change in working directory is detected.
* ``xonsh.prompt.vc_branch.git_dirty_working_directory``
   uses ``porcelain`` option instead of using the bytestring
   ``nothing to commit`` to find out if a git directory is dirty
* Fix bug where know commands where not highlighted on windows.
* Fixed completer showing executable in upper case on windows.
* Fixed issue where tilde expansion was occurring more than once before an
  equals sign.
* test_dirstack test_cdpath_expansion leaving stray testing dirs
* Better completer display for long completions in prompt-toolkit
* Automatically append newline to target of ``source`` alias, so that it may
  be exec'd.
* test_news fails when single graves around word
* Slashes in virtual environment names work in vox
* non string type value in $FORMATTER_DICT turning prompt ugly
* whole prompt turning useless when one formatting function raises an exception
* Fix completion after alias expansion
* Fix hard crash when foreign shell functions fails to run. #1715
* Bug where non-default locations for ``XDG_DATA_HOME`` and ``XONSH_DATA_DIR``
  would not expand ``~`` into the home directory
* Auto quote path completions if path contains 'and' or 'or'

* Completion now works on subcommands after pipe, ``&&``, ``||`` and so on.
* cd . and cd <singleCharacter> now work.  Fix indexerror in AUTO_PUSHD case, too.
* Fixed issue with accidentally wrapping generators inside of function calls.
* History indexing with string returns most recent command.




v0.4.6
====================

**Added:**

* New option ``COMPLETIONS_CONFIRM``. When set, ``<Enter>`` is used to confirm
  completion instead of running command while completion menu is displayed.
* NetBSD is now supported.
* Macro function calls are now available. These use a Rust-like
  ``f!(arg)`` syntax.
* Macro subprocess call now available with the ``echo! x y z``
  syntax.
* A new `event subsystem <http://xon.sh/tutorial_events.html>`_ has been added.
* howto install sections for Debian/Ubuntu and Fedora.
* ``History`` methods ``__iter__`` and ``__getitem__``

* ``tools.get_portions`` that yields parts of an iterable
* Added a py.test plugin to collect ``test_*.xsh`` files and run ``test_*()`` functions.
* ``__repr__`` and ``__str__`` magic method on LazyObject


**Changed:**

* ``create_module`` implementation on XonshImportHook
* Results of the ``bash`` tab completer are now properly escaped (quoted) when necessary.
* Foreign aliases that match xonsh builtin aliases are now ignored with a warning.
* ``prompt_toolkit`` completions now only show the rightmost portion
  of a given completion in the dropdown
* The value of ``'none'`` is no longer allowed for ``$SHELL_TYPE`` just during the initial
  load from the environment. ``-D``, later times, and other sources still work.
* ``yacc_debug=True`` now load the parser on the same thread that the
  Parser instance is created. ``setup.py`` now uses this synchronous
  form as it was causing the parser table to be missed by some package
  managers.
* Tilde expansion for the home directory now has the same semantics as Bash.
  Previously it only matched leading tildes.
* Context sensitive AST transformation now checks that all names in an
  expression are in scope. If they are, then Python mode is retained. However,
  if even one is missing, subprocess wrapping is attempted. Previously, only the
  left-most name was examined for being within scope.
* ``dirstack.pushd`` and ``dirstack.popd`` now handle UNC paths (of form ``\\<server>\<share>\...``), but only on Windows.
  They emulate behavior of `CMD.EXE` by creating a temporary mapped drive letter (starting from z: down) to replace
  the ``\\<server>\<share>`` portion of the path, on the ``pushd`` and unmapping the drive letter when all references
  to it are popped.

* And ``dirstack`` suppresses this temporary drive mapping funky jive if registry entry
  ``HKCU\software\microsoft\command processor\DisableUNCCheck`` (or HKLM\...) is a DWORD value 1.  This allows Xonsh
  to show the actual UNC path in your prompt string and *also* allows subprocess commands invoking `CMD.EXE` to run in
  the expected working directory. See https://support.microsoft.com/en-us/kb/156276 to satisfy any lingering curiosity.
* ``lazy_locate_binary`` handles binary on different drive letter than current working directory (on Windows).
* ``_curr_session_parser`` now iterates over ``History``
* New implementation of bash completer with better performance and compatibility.
* ``$COMPLETIONS_BRACKETS`` is now available to determine whether or not to
  include opening brackets in Python completions
* ``xonsh.bat`` tries to use `pylauncher <https://www.python.org/dev/peps/pep-0397/>`_ when available.


**Removed:**

* ``History`` method ``show``
* ``_hist_get_portion`` in favor of ``tools.get_portions``
* Unused imports in proc, flake8.


**Fixed:**

* xonsh modules imported now have the __file__ attribute
* Context sensitive AST transformer was not adding argument names to the
  local scope. This would then enable extraneous subprocess mode wrapping
  for expressions whose leftmost name was function argument. This has been
  fixed by properly adding the argument names to the scope.
* Foreign shell functions that are mapped to empty filenames no longer
  receive aliases since they can't be found to source later.
* Correctly preserve arguments given to xon.sh, in case there are quoted ones.
* Environment variables in subprocess mode were not being expanded
  unless they were in a sting. They are now expanded properly.
* Fixed a bug that prevented xonsh from running scripts with code caching disabled.
* Text of instructions to download missing program now does not get off and
  appears in whole.
* Fix some test problems when win_unicode_console was installed on windows.
* Fixed bug that prompt string and ``$PWD`` failed to track change in actual working directory if the
  invoked Python function happened to change it (e.g via ```os.chdir()```.  Fix is to update ``$PWD``
  after each command in ```BaseShell.default()```.
* The interactive prompt now correctly handles multiline strings.
* ``cd \\<server>\<share>`` now works when $AUTO_PUSHD is set, either creating a temporary mapped drive or simply
  setting UNC working directory based on registry ``DisableUNCCheck``.  However, if $AUTO_PUSHD is not set and UNC
  checking is enabled (default for Windows), it issues an error message and fails.  This improves on prior behavior,
  which would fail to change the current working directory, but would set $PWD and prompt string to the UNC path,
  creating false expectations.
* fix parsing for tuple of tuples (like `(),()`)
* ``sys.stdin``, ``sys.stdout``, ``sys.stderr`` no longer complete with
  opening square brackets
* xonsh now properly handles syntax error messages arising from using values in inappropriate contexts (e.g., ``del 7``).


v0.4.5
====================

**Added:**

* ``_hist_get`` that uses generators to filter and fetch
  the history commands of each session.

* ``-n`` option to the show subcommand to choose
  to numerate the commands.
* The ``exec`` command is now a first class alias that acts the same way as in
  sh-based languages. It replaces the current process with the command and
  argument that follows it. This allows xonsh to be used as a default shell
  while maintaining functionality with SSH, gdb, and other third party programs
  that assume the default shell supports raw ``exec command [args]`` syntax.

  This feature introduces some ambiguity between exec-as-a-subprocess and
  exec-as-a-function (the inescapable Python builtin). Though the two pieces of
  syntax do not overlap, they perform very different operations. Please see
  the xonsh FAQ for more information on trade-offs and mitigation strategies.
* ``which -v`` now calls superhelp, which will print highlighted source.
* Added xontribs:
  * `z (Tracks your most used directories, based on 'frecency'.) <https://github.com/AstraLuma/xontrib-z>`_
* amalgamate.py now supports relative imports.
* ``history show`` args ``-t``, ``-f``, ``-T`` ``+T`` to filter commands by timestamp

* ``ensure_timestamp`` in xonsh.tools to try and convert an object to a timestamp a.k.a float

* ``$XONSH_DATETIME_FORMAT`` envvar, the default format to be used with ``datetime.datetime.strptime()``
* ``xon.sh`` script now sets ``$LANG=C.UTF8`` in the event that no encoding
  is detected.
* amalgamate.py now properly handles ``from __future__`` imports.


**Changed:**

* ``_hist_show`` now uses ``_hist_get`` to print out the commands.
* ``xonsh.completers`` sub-package is now fully lazy.
* The vox xontrib now takes flags very similar to Python's venv tool. Use
  ``vox --help <command>`` to learn more.
* Xontribs may now define ``__all__`` as a module top-level to limit what gets exported to the shell context
* xon.sh uses the interpreter used to install instead of the default python3.
* ``imphooks`` now checks directory access rights.
* $TITLE now changes both icon (tab) and window title
* Moved ``amalgamate_source`` outside ``build_tables``

* Disable amalgamation on setup develop
* ``_hist_parse_args`` implementation refactor

* moved all parameter checking in ``_hist_get``

* ``_hist_show`` to handle numeration and timestamp printing of commands
* ``xonsh.imphooks`` does not install the import hooks automatically, you now
  need to explicitly call the  `install_hook()` method defined in this module.
  For example: ``from xonsh.imphooks import install_hook; install_hook()``. The
  ``install_hook`` method can safely be called several times. If you need
  compatibility with previous versions of Xonsh you can use the following::

    from xonsh import imphooks
    getattr(imphooks, 'install_hook', lambda:None)()
* xonfig command now dumps more encoding related settings.


**Removed:**

* Anaconda Build is shutting down so we can no longer build conda development packages.
  All references to these packages are removed from the documentation.
* Removed conda build recipe since the it is no longer used for Anaconda Build.
  The recipe used to build xonsh on conda-forge can be found here:
  https://github.com/conda-forge/xonsh-feedstock/blob/master/recipe/meta.yaml


**Fixed:**

* ``_zsh_hist_parser`` not parsing history files without timestamps.
* Fixed amalgamation of aliased imports that are already in ``sys.modules``.
* Xonsh will no longer fail to start in directories where the user doesn't have
  read access.
* Fixed parser error line number exception from being raised while trying to
  raise a SyntaxError.
* Made pip completer more robust to when pip is not installed.
* Fix a startup problem on windows caused by a refactor of Prompt_toolkit.
  https://github.com/jonathanslenders/python-prompt-toolkit/commit/a9df2a2
* ``ensure_slice`` bugfix for -1 index/slice
* Alias tab completion works again
* Version number reported by bundled PLY
* ``xonfig`` no longer breaks if PLY is externally installed and version 3.8
* LazyObject supports set union
* Fixed error with not sourcing files with ``$XONSH_ENCODING`` and
  ``$XONSH_ENCODING_ERRORS``.
* ``$IGNOREEOF`` envrionment variable now works properly in the
  prompt-toolkit shell.
* Completions in ``jupyter_kernel.py`` now use updated completion framework




v0.4.4
====================

**Added:**

* New ``lazyobject()``, ``lazydict()``, and ``lazybool()`` decorators to turn
  functions into lazy, global objects.
* ``vox remove`` command can remove multiple environments at once.
* Added FreeBSD support.
* Tab completion for pip python package manager.
* Regular expressions for environment variable matching.

* __contains__ method on Env
* Added news tests to enforce changelog conformity.
* A new way to add optional items to the prompt format string has been added.
  Instead of relying on formatter dict items being padded with a space, now the
  padding characters are specified in the format string itself, in place of the
  format spec (after a ``:``).

  For example, previously the prompt string ``{cwd}{curr_branch} $`` would rely
  on ``curr_branch`` giving its output prepended with a space for separation,
  or outputting nothing if it is not applicable. Now ``curr_branch`` just
  outputs a value or ``None``, and the prompt string has to specify the
  surrounding characters: ``{cwd}{curr_branch: {}} $``. Here the  value of
  ``curr_branch`` will be prepended with a space (``{}`` is a placeholder for
  the value itself). The format string after ``:`` is applied only if the value
  is not ``None``.
* ``xonsh.completers`` subpackage is now amalgamated.
* amalgamate.py will now warn if the same name is defined across multiple
  different files.
* xonsh_builtins, xonsh_execer fixtures in conftest.py
* Docs on how to tweak the Windows ConHost for a better color scheme.
* Docs: how to fix Thunar's "Open Terminal Here" action.
* A new API class was added to Vox: ``xontrib.voxapi.Vox``. This allows programmatic access to the virtual environment machinery for other xontribs. See the API documentation for details.
* History now accepts multiple slices arguments separated by spaces


**Changed:**

* amalgamate now works on Python 2 and allows relative imports.
* Top-level xonsh package now more lazy.
* Show conda environment name in prompt in parentheses similar what conda does.
* Implementation of expandvars now uses regex
* Because of the addition of "optional items" to the prompt format string, the
  functions ``xonsh.environ.current_branch``, ``xonsh.environ.env_name`` and
  formatter dict items ``curr_branch``, ``current_job``, ``env_name`` are
  no longer padded with a separator.
* many test cases to use fixtures and parametrization
* Public interface in ``xonsh.ansi_colors`` module now has ``ansi_``
  prefix to prevent name conflicts with other parts of xonsh.
* Vox was moved to xontrib. Behaves exactly the same as before, just need to add it to your xontribs.
* is_int_as_str and is_slice_as_str are now reimplemented in EAFP style


**Deprecated:**

* yield statements (nose style) and for loops in tests
* is_int_or_slice


**Removed:**

* _is_in_env, _get_env_string functions on tools
* ``xonsh.environ.format_prompt`` has been dropped; ``partial_format_prompt``
  can be used instead.
* for loops and yield statements in test cases, unused imports
* is_int_or_slice


**Fixed:**

* Fixed bug on Windows preventing xonsh from changing the console title.
* Unrecognized ``$XONSH_COLOR_STYLE`` values don't crash terminal.
* Writing the window title will no longer accidentally answer interactive
  questions, eg ``rm -i`` now works as expected.
* more matching cases for envvar reference
* Certain linux VTE terminals would not start new tabs in the previous CWD.
  This may now be rectified by adding ``{vte_new_tab_cwd}`` somewhere to the
  prompt.
* Unqualified usage of Unstorable in xonsh setup wizard that was causing the
  wizard to crash and burn
* Bare ``except:`` was replaced with ``except Exception`` to prevent
  accidentally catching utility exceptions such as KeyboardInterrupt, which
  caused unexpected problems like printing out the raw $PROMPT string.
* Fixed multiple definition of ``EQUAL``.
* Fixed multiple definition of ``pprint``.
* Fixed multiple definition of ``pyghooks``.
* Fixed multiple definition of ``pygments``.
* Fixed multiple definition of ``tokenize``.
* redundant and 'leaky' tests in nose
* Fix bug that prevented disabling $INTENSIFY_COLORS_ON_WIN in ``xonshrc``
* ``LazyJSON`` will now hide failures to close, and instead rely on reference
  counting if something goes wrong.
* Fixed maximum recursion error with color styles.
* Parser tables will no longer be generated in the current directory
  by accident.
* Error messages when zsh or bash history file is not found




v0.4.3
====================

**Added:**

* The results of glob expressions are sorted if ``$GLOB_SORTED`` is set.
* LazyObjects will now load themselves on ``__getitem__()``
* New tools in ``xonsh.lazyasd`` module for loading modules in background
  threads.


**Changed:**

* ``GLOB_SORTED`` is enabled by default.
* Sped up loading of pygments by ~100x by loading ``pkg_resources`` in
  background.
* Sped up loading of prompt-toolkit by ~2x-3x by loading ``pkg_resources``
  in background.
* ``setup.py`` will no longer git checkout to replace the version number.
  Now it simply stores and reuses the original version line.


**Removed:**

* Removed the ``xonsh.built_ins.ENV`` global instance of the Env class.


**Fixed:**

* Bug with setting hist size not being settable due to lazy object loading
  has been resolved.
* Minor amalgamate bug with ``import pkg.mod`` amalgamated imports.
* No longer raises an error if a directory in ``$PATH`` does not exist on
  Python v3.4.
* Fixed a readline shell completion issue that caused by inconsistency between
  ``$CASE_SENSITIVE_COMPLETIONS`` and readline's inputrc setting.




v0.4.2
====================

**Added:**

* dev versions now display a ``devN`` counter at the end and ``xonfig info``
  also displays the git sha of the current build


**Changed:**

* `prompt_toolkit` completion no longer automatically selects the first entry on first tab-press when completing multiple directories at once


**Fixed:**

* Sourcing foreign shells now allow fully capture environment variables that
  contain newlines as long as they also don't contain equal signs.
* Added scripts directory to MANIFEST.in




v0.4.1
====================

**Fixed:**

* ``setup.py`` will only amalgamate source files if ``amalgamate.py`` is
  available. This fixes issues with installing from pip.




v0.4.0
====================

**Added:**

* A new class, ``xonsh.tools.EnvPath`` has been added. This class implements a
  ``MutableSequence`` object and overrides the ``__getitem__`` method so that
  when its entries are requested (either explicitly or implicitly), variable
  and user expansion is performed, and relative paths are resolved.
  ``EnvPath`` accepts objects (or lists of objects) of ``str``, ``bytes`` or
  ``pathlib.Path`` types.
* New amalgamate tool collapses modules inside of a package into a single
  ``__amalgam__.py`` module. This tool glues together all of the code from the
  modules in a package, finds and removes intra-package imports, makes all
  non-package imports lazy, and adds hooks into the ``__init__.py``.
  This helps makes initial imports of modules fast and decreases startup time.
  Packages and sub-packages must be amalgamated separately.
* New lazy and self-destructive module ``xonsh.lazyasd`` adds a suite of
  classes for delayed creation of objects.

    - A ``LazyObject`` won't be created until it has an attribute accessed.
    - A ``LazyDict`` will load each value only when a key is accessed.
    - A ``LazyBool`` will only be created when ``__bool__()`` is called.

  Additionally, when fully loaded, the above objects will replace themselves
  by name in the context that they were handed, thus dereferencing themselves.
  This is useful for global variables that may be expensive to create,
  should only be created once, and may not be used in any particular session.
* New ``xon.sh`` script added for launching xonsh from a sh environment.
  This should be used if the normal ``xonsh`` script does not work for
  some reason.
* Normal globbing is now available in Python mode via ``g````
* Backticks were expanded to allow searching using arbitrary functions, via
  ``@<func>````
* ``xonsh.platform`` now has a new ``PATH_DEFAULT`` variable.
* Tab completers can now raise ``StopIteration`` to prevent consideration of
  remaining completers.
* Added tab completer for the ``completer`` alias.
* New ``Block`` and ``Functor`` context managers are now available as
  part of the ``xonsh.contexts`` module.
* ``Block`` provides support for turning a context body into a non-executing
  list of string lines. This is implement via a syntax tree transformation.
  This is useful for creating remote execution tools that seek to prevent
  local execution.
* ``Functor`` is a subclass of the ``Block`` context manager that turns the
  block into a callable object.  The function object is available via the
  ``func()`` attribute.  However, the ``Functor`` instance is itself callable
  and will dispatch to ``func()``.
* New ``$VC_BRANCH_TIMEOUT`` environment variable is the time (in seconds)
  of how long to spend attempting each individual version control branch
  information command during ``$PROMPT`` formatting.  This allows for faster
  prompt resolution and faster startup times.
* New lazy methods added to CommandsCache allowing for testing and inspection
  without the possibility of recomputing the cache.
* ``!(command)`` is now usefully iterable, yielding lines of stdout
* Added XonshCalledProcessError, which includes the relevant CompletedCommand.
  Also handles differences between Py3.4 and 3.5 in CalledProcessError
* Tab completion of paths now includes zsh-style path expansion (subsequence
  matching), toggleable with ``$SUBSEQUENCE_PATH_COMPLETION``
* Tab completion of paths now includes "fuzzy" matches that are accurate to
  within a few characters, toggleable with ``$FUZZY_PATH_COMPLETION``
* Provide ``$XONSH_SOURCE`` for scripts in the environment variables pointing to
  the currently running script's path
* Arguments '+' and '-' for the ``fg`` command (job control)
* Provide ``$XONSH_SOURCE`` for scripts in the environment variables pointing to
  the currently running script's path
* ``!(command)`` is now usefully iterable, yielding lines of stdout
* Added XonshCalledProcessError, which includes the relevant CompletedCommand.
  Also handles differences between Py3.4 and 3.5 in CalledProcessError
* XonshError and XonshCalledProcessError are now in builtins:

  - ``history session``
  - ``history xonsh``
  - ``history all``
  - ``history zsh``
  - ``history bash``
  - ``__xonsh_history__.show()``

* New ``pathsep_to_set()`` and ``set_to_pathsep()`` functions convert to/from
  ``os.pathsep`` separated strings to a set of strings.


**Changed:**

* Changed testing framework from nose to pytest
* All ``PATH``-like environment variables are now stored in an ``EnvPath``
  object, so that non-absolute paths or paths containing environment variables
  can be resolved properly.
* In ``VI_MODE``, the ``v`` key will enter character selection mode, not open
  the editor.  ``Ctrl-X Ctrl-E`` will still open an editor in any mode
* ``$XONSH_DEBUG`` will now suppress amalgamated imports. This usually needs to be
  set in the calling environment or prior to *any* xonsh imports.
* Restructured ``xonsh.platform`` to be fully lazy.
* Restructured ``xonsh.ansi_colors`` to be fully lazy.
* Ensured the ``pygments`` and ``xonsh.pyghooks`` are not imported until
  actually needed.
* Yacc parser is now loaded in a background thread.
* Cleaned up argument parsing in ``xonsh.main.premain`` by removing the
  ``undo_args`` hack.
* Now complains on invalid arguments.
* ``Env`` now guarantees that the ``$PATH`` is available and mutable when
  initialized.
* On Windows the ``PROMPT`` environment variable is reset to `$P$G` before
  sourcing ``*.bat`` files.
* On Windows the ``PROMPT`` environment variable is reset to `$P$G` before starting
  subprocesses. This prevents the unformatted xonsh ``PROMPT`` template from showing up
  when running batch files with ``ECHO ON```
* ``@()`` now passes through functions as well as strings, which allows for the
  use of anonymous aliases and aliases not explicitly added to the ``aliases``
  mapping.
* Functions in ``Execer`` now take ``transform`` kwarg instead of
  ``wrap_subproc``.
* Provide ``$XONSH_SOURCE`` for scripts in the environment variables pointing to
  the currently running script's path
* XonshError and XonshCalledProcessError are now in builtins
* ``__repr__`` on the environment only shows a short representation of the
  object instead of printing the whole environment dictionary
* More informative prompt when configuring foreign shells in the wizard.
* ``CommandsCache`` is now a mapping from command names to a tuple of
  (executable locations, has alias flags). This enables faster lookup times.
* ``locate_bin()`` now uses the ``CommandsCache``, rather than scanning the
  ``$PATH`` itself.
* ``$PATHEXT`` is now a set, rather than a list.
* Ignore case and leading a quotes when sorting completions


**Removed:**

* The ``'console_scripts'`` option to setuptools has been removed. It was found
  to cause slowdowns of over 150 ms on every startup.
* Bash is no longer loaded by default as a foreign shell for initial
  configuration. This was done to increase stock startup times. This
  behaviour can be recovered by adding ``{"shell": "bash"}`` to your
  ``"foreign_shells"`` in your config.json file. For more details,
  see http://xon.sh/xonshconfig.html#foreign-shells
* ``ensure_git()`` and ``ensure_hg()`` decorators removed.
* ``call_hg_command()`` function removed.


**Fixed:**

* Issue where ``xonsh`` did not expand user and environment variables in
  ``$PATH``, forcing the user to add absolute paths.
* Fixed a problem with aliases not always being found.
* Fixed issue where input was directed to the last process in a pipeline,
  rather than the first.
* Bug where xonfig wizard can't find ENV docs
* Fixed ``xonsh.environ.locate_binary()`` to handle PATH variable are given as a tuple.
* Fixed missing completions for ``cd`` and ```rmdir`` when directories had spaces
  in their names.
* Bug preventing `xonsh` executable being installed on macOS.
* Strip leading space in commands passed using the "-c" switch
* Fixed xonfig wizard failing on Windows due to colon in created filename.
* Ensured that the prompt_toolkit shell functions, even without a ``completer``
  attribute.
* Fixed crash resulting from malformed ``$PROMPT`` or ``$TITLE``.
* xonsh no longer backgrounds itself after every command on Cygwin.
* Fixed an issue about ``os.killpg()`` on Cygwin which caused xonsh to crash
  occasionally
* Fix crash on startup when Bash Windows Subsystem for Linux is on the Path.
* Fixed issue with setting and signaling process groups on Linux when the first
  process is a function alias and has no pid.
* Fixed ``_list_completers`` such that it does not throw a ValueError if no completer is registered.
* Fixed ``_list_completers`` such that it does not throw an AttributeError if a completer has no docstring.
* Bug that caused command line argument ``--config-path`` to be ignored.
* Bug that caused xonsh to break on startup when prompt-toolkit < 1.0.0.


v0.3.4
====================

**Changed:**

* ``$PROMPT`` from foreign shells is now ignored.
* ``$RC_FILES`` environment variable now stores the run control files we
  attempted to load.
* Only show the prompt for the wizard if we did not attempt to load any run
  control files (as opposed to if none were successfully loaded).
* Git and mercurial branch and dirty function refactor to improve run times.


**Fixed:**

* Fixed an issue whereby attempting to delete a literal value (e.g., ``del 7``)
  in the prompt_toolkit shell would cause xonsh to crash.
* Fixed broken behavior when using ``cd ..`` to move into a nonexistent
  directory.
* Partial workaround for Cygwin where ``pthread_sigmask`` appears to be missing
  from the ``signal`` module.
* Fixed crash resulting from malformed ``$PROMPT``.
* Fixed regression on Windows with the locate_binary() function.
  The bug prevented `source-cmd` from working correctly and broke the
  ``activate``/``deactivate`` aliases for the conda environments.
* Fixed crash resulting from errors other than syntax errors in run control
  file.
* On Windows if bash is not on the path look in the registry for the defaults
  install directory for GitForWindows.


v0.3.3
====================
**Added:**

* Question mark literals, ``?``, are now allowed as part of
  subprocess argument names.
* IPython style visual pointer to show where syntax error was detected
* Pretty printing of output and syntax highlighting of input and output can now
  be controlled via new environment variables ``$COLOR_INPUT``,
  ``$COLOR_RESULTS``, and ``$PRETTY_PRINT_RESULTS``.

* In interactive mode, if there are stopped or background jobs, Xonsh prompts
  for confirmations rather than just killing all jobs and exiting.

**Changed:**

* ``which`` now gives a better verbose report of where the executables are
  found.
* Tab completion now uses a different interface, which allows new completers
  to be implemented in Python.
* Most functions in the ``Execer`` now take an extra argument
  ``transform``, indicating whether the syntax tree transformations should
  be applied.
* ``prompt_toolkit`` is now loaded lazily, decreasing load times when using
  the ``readline`` shell.
* RC files are now executed directly in the appropriate context.
* ``_`` is now updated by ``![]``, to contain the appropriate
  ``CompletedCommand`` object.



**Removed:**

* Fixed bug on Windows where ``which`` did not include current directory

**Fixed:**

* Fixed crashed bash-completer when bash is not available on Windows
* Fixed bug on Windows where tab-completion for executables would return all files.
* Fixed bug on Windows which caused the bash $PROMPT variable to be used when no
  no $PROMPT variable was set in .xonshrc
* Improved start-up times by caching information about bash completion
  functions
* The --shell-type CLI flag now takes precedence over $SHELL_TYPE specified in
  .xonshrc
* Fixed an issue about ``os.killpg()`` on OS X which caused xonsh crash with
  occasionally.



v0.3.2
====================
**Fixed:**

* Fixed PermissionError when tab completions tries to lookup executables in
  directories without read permissions.
* Fixed incorrect parsing of command line flags



v0.3.1
====================
**Added:**

* When a subprocess exits with a signal (e.g. SIGSEGV), a message is printed,
  similar to Bash.
* Added comma literals to subproc mode.
* ``@$(cmd)`` has been added as a subprocess-mode operator, which replaces in
  the subprocess command itself with the result of running ``cmd``.
* New ``showcmd`` alias for displaying how xonsh interprets subprocess mode
  commands and arguments.
* Added ``$DYNAMIC_CWD_WIDTH`` to allow the adjusting of the current working
  directory width in the prompt.
* Added ``$XONSH_DEBUG`` environment variable to help with debugging.
* The ``${...}`` shortcut for ``__xonsh_env__`` now returns appropriate
  completion options

**Changed:**

* On Windows the default bash completions files ``$BASH_COMPLETIONS`` now points
  to the default location of the completions files used by 'Git for Windows'
* On Cygwin, some tweaks are applied to foreign shell subprocess calls and the
  readline import, in order to avoid hangs on launch.


**Removed:**

* Special cased code for handling version of prompt_toolkit < v1.0.0


**Fixed:**

* Show sorted bash completions suggestions.
* Fix bash completions (e.g git etc.) on windows when completions files have
  spaces in their path names
* Fixed a bug preventing ``source-bash`` from working on Windows
* Numerous improvements to job control via a nearly-complete rewrite.
* Addressed issue with finding the next break in subproc mode in context
  sensitive parsing.
* Fixed issue with loading readline init files (inputrc) that seems to be
  triggered by libedit.
* ``$MULTILINE_PROMPT`` now allows colors, as originally intended.
* Rectified install issue with Jupyter hook when installing with pyenv,
  Jupyter install hook now respects ``--prefix`` argument.
* Fixed issue with the xonsh.ply subpackage not being installed.
* Fixed a parsing bug whereby a trailing ``&`` on a line was being ignored
  (processes were unable to be started in the background)



v0.3.0
====================
**Added:**

* ``and``, ``or``, ``&&``, ``||`` have been added as subprocess logical operators,
  by popular demand!
* Subprocesses may be negated with ``not`` and grouped together with parentheses.
* New framework for writing xonsh extensions, called ``xontribs``.
* Added a new shell type ``'none'``, used to avoid importing ``readline`` or
  ``prompt_toolkit`` when running scripts or running a single command.
* New: `sudo` functionality on Windows through an alias
* Automatically enhance colors for readability in the default terminal (cmd.exe)
  on Windows. This functionality can be enabled/disabled with the
  $INTENSIFY_COLORS_ON_WIN environment variable.
* Added ``Ellipsis`` lookup to ``__xonsh_env__`` to allow environment variable checks, e.g. ``'HOME' in ${...}``
* Added an option to update ``os.environ`` every time the xonsh environment changes.
  This is disabled by default but can be enabled by setting ``$UPDATE_OS_ENVIRON`` to
  True.
* Added Windows 'cmd.exe' as a foreign shell. This gives xonsh the ability to source
  Windows Batch files (.bat and .cmd). Calling ``source-cmd script.bat`` or the
  alias ``source-bat script.bat`` will call the bat file and changes to the
  environment variables will be reflected in xonsh.
* Added an alias for the conda environment activate/deactivate batch scripts when
  running the Anaconda python distribution on Windows.
* Added a menu entry to launch xonsh when installing xonsh from a conda package
* Added a new ``which`` alias that supports both regular ``which`` and also searches
  through xonsh aliases. A pure python implementation of ``which`` is used. Thanks
  to Trent Mick. https://github.com/trentm/which/
* Added support for prompt toolkit v1.0.0.
* Added ``$XONSH_CACHE_SCRIPTS`` and ``$XONSH_CACHE_EVERYTHING`` environment
  variables to control caching of scripts and interactive commands.  These can
  also be controlled by command line options ``--no-script-cache`` and
  ``--cache-everything`` when starting xonsh.
* Added a workaround to allow ctrl-c to interrupt reverse incremental search in
  the readline shell

**Changed:**

* Running scripts through xonsh (or running a single command with ``-c``) no
  longer runs the user's rc file, unless the ``--login`` option is specified.
  Also avoids loading aliases and environments from foreign shells, as well as
  loading bash completions.
* rc files are now compiled and cached, to avoid re-parsing when they haven't
  changed.  Scripts are also compiled and cached, and there is the option to
  cache interactive commands.
* Left and Right arrows in the ``prompt_toolkit`` shell now wrap in multiline
  environments
* Regexpath matching with backticks, now returns an empty list in python mode.
* Pygments added as a dependency for the conda package
* Foreign shells now allow for setting exit-on-error commands before and after
  all other commands via the ``seterrprevcmd`` and ``seterrpostcmd`` arguments.
  Sensinble defaults are provided for existing shells.
* PLY is no longer a external dependency but is bundled in xonsh/ply. Xonsh can
  therefore run without any external dependencies, although having prompt-toolkit
  recommended.
* Provide better user feedback when running ``which`` in a platform that doesn't
  provide it (e.g. Windows).
* The lexer now uses a custom tokenizer that handles regex globs in the proper
  way.






**Fixed:**

* Fixed bug with loading prompt-toolkit shell < v0.57.
* Fixed bug with prompt-toolkit completion when the cursor is not at the end of
  the line.
* Aliases will now evaluate environment variables and other expansions
  at execution time rather than passing through a literal string.
* Fixed environment variables from os.environ not being loaded when a running
  a script
* The readline shell will now load the inputrc files.
* Fixed bug that prevented `source-alias` from working.
* Now able to ``^C`` the xonfig wizard on start up.
* Fixed deadlock on Windows when running subprocess that generates enough output
  to fill the OS pipe buffer.
* Sourcing foreign shells will now return a non-zero exit code if the
  source operation failed for some reason.
* Fixed PermissionError when running commands in directories without read permissions
* Prevent Windows fixups from overriding environment vars in static config
* Fixed Optional Github project status to reflect added/removed files via git_dirty_working_directory()
* Fixed xonsh.exe launcher on Windows, when Python install directory has a space in it
* Fixed `$CDPATH` to support `~` and environments variables in its items




v0.2.7
====================
**Added:**

* Added new valid ``$SHELL_TYPE`` called ``'best'``. This selects the best value
  for the concrete shell type based on the availability on the user's machine.
* New environment variable ``$XONSH_COLOR_STYLE`` will set the color mapping
  for all of xonsh.
* New ``XonshStyle`` pygments style will determine the appropriate color
  mapping based on ``$XONSH_COLOR_STYLE``.  The associated ``xonsh_style_proxy()``
  is intended for wrapping ``XonshStyle`` when actually being used by
  pygments.
* The functions ``print_color()`` and ``format_color()`` found in ``xonsh.tools``
  dispatch to the approriate shell color handling and may be used from
  anywhere.
* ``xonsh.tools.HAVE_PYGMENTS`` flag now denotes if pygments is installed and
  available on the users system.
* The ``ansi_colors`` module is now available for handling ANSI color codes.
* ``?`` and ``??`` operator output now has colored titles, like in IPython.
* ``??`` will syntax highlight source code if pygments is available.
* Python mode output is now syntax highlighted if pygments is available.
* New ``$RIGHT_PROMPT`` environment variable for displaying right-aligned
  text in prompt-toolkit shell.
* Added ``!(...)`` operator, which returns an object representing the result
  of running a command.  The truth value of this object is True if the
  return code is equal to zero and False otherwise.
* Optional dependency on the win_unicode_console package to enable unicode
  support in cmd.exe on Windows. This can be disabled/enabled with the
  ``$WIN_UNICODE_CONSOLE`` environment variable.

**Changed:**

* Updated ``$SHELL_TYPE`` default to ``'best'``.
* Shell classes are now responsible for implementing their own color
  formatting and printing.
* Prompt coloring, history diffing, and tracing uses new color handling
  capabilities.
* New ``Token.Color`` token for xonsh color names, e.g. we now use
  ``Token.Color.RED`` rather than ``Token.RED``.
* Untracked files in git are ignored when determining if a git workdir is
  is dirty. This affects the coloring of the branch label.
* Regular expression globbing now uses ``re.fullmatch`` instead of
  ``re.match``, and the result of an empty regex glob does not cause the
  argument to be deleted.


**Removed:**

* The ``xonsh.tools.TERM_COLORS`` mapping has been axed, along with all
  references to it. This may cause a problem if you were using a raw color code
  in your xonshrc file from ``$FORMATTER_DICT``. To fix, simply remove these
  references.

**Fixed:**

* Multidimensional slicing, as in numpy, no longer throws SyntaxErrors.
* Some minor zsh fixes for more platforms and setups.
* The ``BaseShell.settitle`` method no longer has its commands captured by
  ``$(...)``



v0.2.6
====================
**Added:**

* ``trace`` alias added that enables users to turn on and off the printing
  of source code lines prior to their execution. This is useful for debugging scripts.
* New ability to force callable alias functions to be run in the foreground, i.e.
  the main thread from which the function was called. This is useful for debuggers
  and profilers which may require such access. Use the ``xonsh.proc.foreground``
  decorator on an alias function to flag it. ``ForegroundProcProxy`` and
  ``SimpleForegroundProcProxy`` classes have been added to support this feature.
  Normally, forcing a foreground alias is not needed.
* Added boolean ``$RAISE_SUBPROC_ERROR`` environment variable. If true
  and a subprocess command exits with a non-zero return code, a
  CalledProcessError will be raised. This is useful in scripts that should
  fail at the first error.
* If the ``setproctitle`` package is installed, the process title will be
  set to ``'xonsh'`` rather than the path to the Python interpreter.
* zsh foreign shell interface now supported natively in xonsh, like with Bash.
  New ``source-zsh`` alias allows easy access to zsh scripts and functions.
* Vox virtual environment manager added.

**Changed:**

* The ``foreign_shell_data()`` keyword arguments ``envcmd`` and ``aliascmd``
  now default to ``None``.
* Updated alias docs to pull in usage from the commands automatically.

**Fixed:**

* Hundreds of bugs related to line and column numbers have been addressed.
* Fixed path completion not working for absolute paths or for expanded paths on Windows.
* Fixed issue with hg dirty branches and $PATH.
* Fixed issues related to foreign shell data in files with whitespace in the names.
* Worked around bug in ConEmu/cmder which prevented ``get_git_branch()``
  from working in these terminal emulators on Windows.


v0.2.5
===========
**Added:**

* New configuration utility 'xonfig' which reports current system
  setup information and creates config files through an interactive
  wizard.
* Toolkit for creating wizards now available
* timeit and which aliases will now complete their arguments.
* $COMPLETIONS_MENU_ROWS environment variable controls the size of the
  tab-completion menu in prompt-toolkit.
* Prompt-toolkit shell now supports true multiline input with the ability
  to scroll up and down in the prompt.

**Changed:**

* The xonfig wizard will run on interactive startup if no configuration
  file is found.
* BaseShell now has a singleline() method for prompting a single input.
* Environment variable docs are now auto-generated.
* Prompt-toolkit shell will now dynamically allocate space for the
  tab-completion menu.
* Looking up nonexistent environment variables now generates an error
  in Python mode, but produces a sane default value in subprocess mode.
* Environments are now considered to contain all manually-adjusted keys,
  and also all keys with an associated default value.

**Removed:**

* Removed ``xonsh.ptk.shortcuts.Prompter.create_prompt_layout()`` and
  ``xonsh.ptk.shortcuts.Prompter.create_prompt_application()`` methods
  to reduce portion of xonsh that forks prompt-toolkit. This may require
  users to upgrade to prompt-toolkit v0.57+.

**Fixed:**

* First prompt in the prompt-toolkit shell now allows for up and down
  arrows to search through history.
* Made obtaining the prompt-toolkit buffer thread-safe.
* Now always set non-detypable environment variables when sourcing
  foreign shells.
* Fixed issue with job management if a TTY existed but was not controlled
  by the process, posix only.
* Jupyter kernel no longer times out when using foreign shells on startup.
* Capturing redirections, e.g. ``$(echo hello > f.txt)``, no longer fails
  with a decoding error.
* Evaluation in a Jupyter cell will return pformatted object.
* Jupyter with redirect uncaptured subprocs to notebook.
* Tab completion in Jupyter fixed.


v0.2.1 - v0.2.4
===============
You are reading the docs...but you still feel hungry.

v0.2.0
=============
**Added:**

* Rich history recording and replaying

v0.1.0
=============
**Added:**

* Naturally typed environment variables
* Inherits the environment from BASH
* Uses BASH completion for subprocess commands
* Regular expression filename globbing
* Its own PLY-based lexer and parser
* xonsh code parses into a Python AST
* You can do all the normal Python things, like arithmetic and importing
* Captured and uncaptured subprocesses
* Pipes, redirection, and non-blocking subprocess syntax support
* Help and superhelp with ? and ??
* Command aliasing
* Multiline input, unlike ed
* History matching like in IPython
* Color prompts
* Low system overhead




<v0.1.0
=============
The before times, like 65,000,000 BCE.
