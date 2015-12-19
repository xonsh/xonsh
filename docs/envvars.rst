Environment Variables
=====================
The following table displays information about the environment variables that 
effect XONSH performance in some way. It also lists their default values, if
applicable.

.. Please keep the following in alphabetic order - scopatz

.. list-table:: 
    :widths: 1 1 3
    :header-rows: 1

    * - variable
      - default
      - description
    * - ANSICON
      - No default set
      - This is used on Windows to set the title, if available.
    * - AUTO_CD
      - ``False``
      - Flag to enable changing to a directory by entering the dirname or full path only (without the `cd` command)
    * - AUTO_PUSHD
      - ``False``
      - Flag for automatically pushing directories onto the directory stack.
    * - AUTO_SUGGEST
      - ``True``
      - Enable automatic command suggestions based on history (like in fish shell).
      
        Pressing the right arrow key inserts the currently displayed suggestion.
        
        (Only usable with SHELL_TYPE=prompt_toolkit)
    * - BASH_COMPLETIONS
      - Normally this is ``('/etc/bash_completion', '/usr/share/bash-completion/completions/git')``
        but on Mac is ``('/usr/local/etc/bash_completion', '/opt/local/etc/profile.d/bash_completion.sh')``
        and on Arch Linux is ``('/usr/share/bash-completion/bash_completion',
        '/usr/share/bash-completion/completions/git')``.
      - This is a list (or tuple) of strings that specifies where the BASH completion 
        files may be found. The default values are platform dependent, but sane. 
        To specify an alternate list, do so in the run control file.
    * - CASE_SENSITIVE_COMPLETIONS
      - ``True`` on Linux, otherwise ``False``
      - Sets whether completions should be case sensitive or case insensitive.
    * - CDPATH
      - ``[]``
      - A list of paths to be used as roots for a ``cd``, breaking compatibility with 
        bash, xonsh always prefer an existing relative path.
    * - COMPLETIONS_DISPLAY
      - ``'multi'``
      - Configure if and how Python completions are displayed by the prompt_toolkit shell.
      
        This option does not affect bash completions, auto-suggestions etc.
        
        Changing it at runtime will take immediate effect, so you can quickly
        disable and enable completions during shell sessions.
        
        - If COMPLETIONS_DISPLAY is ``'none'`` or ``'false'``, do not display those completions.
        
        - If COMPLETIONS_DISPLAY is ``'single'``, display completions in a single column while typing.
        
        - If COMPLETIONS_DISPLAY is ``'multi'`` or ``'true'``, display completions in multiple columns while typing.
        
        These option values are not case- or type-sensitive, so e.g.
        writing ``$COMPLETIONS_DISPLAY = None`` and ``$COMPLETIONS_DISPLAY = 'none'`` is equivalent.
        
        (Only usable with SHELL_TYPE=prompt_toolkit)
    * - DIRSTACK_SIZE
      - ``20``
      - Maximum size of the directory stack.
    * - EXPAND_ENV_VARS
      - ``True``
      - Toggles whether environment variables are expanded inside of strings in subprocess mode.
    * - FORCE_POSIX_PATHS
      - ``False``
      - Forces forward slashes (``/``) on Windows systems when using auto completion if 
        set to anything truthy.
    * - FORMATTER_DICT
      - xonsh.environ.FORMATTER_DICT  
      - Dictionary containing variables to be used when formatting PROMPT and TITLE 
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    * - HISTCONTROL
      - ``set([])``
      - A set of strings (comma-separated list in string form) of options that
        determine what commands are saved to the history list. By default all
        commands are saved. The option ``ignoredups`` will not save the command
        if it matches the previous command. The option ``ignoreerr`` will cause
        any commands that fail (i.e. return non-zero exit status) to not be
        added to the history list.
    * - IGNOREEOF
      - ``False``
      - Prevents Ctrl-D from exiting the shell.
    * - INDENT
      - ``'    '``
      - Indentation string for multiline input
    * - MOUSE_SUPPORT
      - ``False``
      - Enable mouse support in the prompt_toolkit shell.
        
        This allows clicking for positioning the cursor or selecting a completion. In some terminals
        however, this disables the ability to scroll back through the history of the terminal.
        
        (Only usable with SHELL_TYPE=prompt_toolkit)
    * - MULTILINE_PROMPT
      - ``'.'``
      - Prompt text for 2nd+ lines of input, may be str or function which returns 
        a str.
    * - OLDPWD
      - No default
      - Used to represent a previous present working directory.
    * - PATH
      - ``()``
      - List of strings representing where to look for executables.
    * - PATHEXT
      - ``()``
      - List of strings for filtering valid exeutables by.
    * - PROMPT
      - xonsh.environ.DEFAULT_PROMPT  
      - The prompt text.  May contain keyword arguments which are auto-formatted,
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    * - PROMPT_TOOLKIT_COLORS
      - ``{}``
      - This is a mapping of from color names to HTML color codes.  Whenever
        prompt-toolkit would color a word a particular color (in the prompt, or
        in syntax highlighting), it will use the value specified here to
        represent that color, instead of its default.  If a color is not
        specified here, prompt-toolkit uses the colors from
        ``xonsh.tools._PT_COLORS``.
    * - PROMPT_TOOLKIT_STYLES
      - ``None``
      - This is a mapping of user-specified styles for prompt-toolkit. See the 
        prompt-toolkit documentation for more details. If None, this is skipped.
    * - PUSHD_MINUS
      - ``False``
      - Flag for directory pushing functionality. False is the normal behaviour.
    * - PUSHD_SILENT
      - ``False``
      - Whether or not to supress directory stack manipulation output.
    * - SHELL_TYPE
      - ``'prompt_toolkit'`` if on Windows, otherwise ``'readline'``
      - Which shell is used. Currently two base shell types are supported: 
        ``'readline'`` that is backed by Python's readline module, and 
        ``'prompt_toolkit'`` that uses external library of the same name. 
        To use the prompt_toolkit shell you need to have 
        `prompt_toolkit <https://github.com/jonathanslenders/python-prompt-toolkit>`_
        library installed. To specify which shell should be used, do so in the run 
        control file. Additionally, you may also set this value to ``'random'``
        to get a random choice of shell type on startup.
    * - SUGGEST_COMMANDS
      - ``True``
      - When a user types an invalid command, xonsh will try to offer suggestions of 
        similar valid commands if this is ``True``.
    * - SUGGEST_MAX_NUM
      - ``5``
      - xonsh will show at most this many suggestions in response to an invalid command.
        If negative, there is no limit to how many suggestions are shown.
    * - SUGGEST_THRESHOLD
      - ``3``
      - An error threshold. If the Levenshtein distance between the entered command and 
        a valid command is less than this value, the valid command will be offered as a 
        suggestion.
    * - TEEPTY_PIPE_DELAY
      - ``0.01``
      - The number of [seconds] to delay a spawned process if it has information
        being piped in via stdin. This value must be a float. If a value less than 
        or equal to zero is passed in, no delay is used. This can be used to fix 
        situations where a spawned process, such as piping into ``grep``, exits
        too quickly for the piping operation itself. TeePTY (and thus this variable)
        are currently only used when ``$XONSH_STORE_STDOUT`` is ``True``.
    * - TERM
      - No default
      - TERM is sometimes set by the terminal emulator. This is used (when valid)
        to determine whether or not to set the title. Users shouldn't need to 
        set this themselves.
    * - TITLE
      - xonsh.environ.DEFAULT_TITLE
      - The title text for the window in which xonsh is running. Formatted in the same 
        manner as PROMPT, 
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    * - VI_MODE
      - ``False``
      - Flag to enable ``vi_mode`` in the ``prompt_toolkit`` shell.  
    * - XDG_CONFIG_HOME
      - ``~/.config``
      - Open desktop standard configuration home dir. This is the same default as
        used in the standard.
    * - XDG_DATA_HOME
      - ``~/.local/share``
      - Open desktop standard data home dir. This is the same default as used
        in the standard.
    * - XONSHCONFIG
      - ``$XONSH_CONFIG_DIR/config.json``
      - The location of the static xonsh configuration file, if it exists. This is
        in JSON format.
    * - XONSHRC
      - ``('/etc/xonshrc', '~/.xonshrc')`` (Linux and OSX) 
    	``('%ALLUSERSPROFILE%\xonsh\xonshrc', '~/.xonshrc')`` (Windows)
      - A tuple of the locations of run control files, if they exist.  User defined
        run control file will supercede values set in system-wide control file if there
        is a naming collision.
    * - XONSH_CONFIG_DIR
      - ``$XDG_CONFIG_HOME/xonsh``
      - This is location where xonsh configuration information is stored.
    * - XONSH_DATA_DIR
      - ``$XDG_DATA_HOME/xonsh``
      - This is the location where xonsh data files are stored, such as history.
    * - XONSH_ENCODING
      - ``sys.getdefaultencoding()``
      - This is the that xonsh should use for subrpocess operations.
    * - XONSH_ENCODING_ERRORS
      - ``'surrogateescape'``
      - The flag for how to handle encoding errors should they happen.
        Any string flag that has been previously registered with Python
        is allowed. See the `Python codecs documentation <https://docs.python.org/3/library/codecs.html#error-handlers>`_
        for more information and available options. 
    * - XONSH_HISTORY_FILE
      - ``'~/.xonsh_history'``
      - Location of history file (deprecated).
    * - XONSH_HISTORY_SIZE
      - ``(8128, 'commands')`` or ``'8128 commands'``           
      - Value and units tuple that sets the size of history after garbage collection. 
        Canonical units are ``'commands'`` for the number of past commands executed, 
        ``'files'`` for the number of history files to keep, ``'s'`` for the number of
        seconds in the past that are allowed, and ``'b'`` for the number of bytes that 
        are allowed for history to consume. Common abbreviations, such as ``6 months``
        or ``1 GB`` are also allowed.
    * - XONSH_INTERACTIVE
      - 
      - ``True`` if xonsh is running interactively, and ``False`` otherwise.
    * - XONSH_LOGIN
      - ``True`` if xonsh is running as a login shell, and ``False`` otherwise.
    * - XONSH_SHOW_TRACEBACK
      - ``False`` but not set
      - Controls if a traceback is shown exceptions occur in the shell. Set ``True`` 
        to always show or ``False`` to always hide. If undefined then traceback is 
        hidden but a notice is shown on how to enable the traceback.
    * - XONSH_STORE_STDOUT 
      - ``False``
      - Whether or not to store the stdout and stderr streams in the history files.

