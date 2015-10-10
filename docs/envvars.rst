Environment Variables
=====================
The following table displays information about the environment variables that 
effect XONSH performance in some way. It also lists their default values, if
applicable.

.. list-table:: 
    :widths: 1 1 3
    :header-rows: 1

    * - variable
      - default
      - description
    * - BASH_COMPLETIONS
      - Normally this is ``('/etc/bash_completion', 
                            '/usr/share/bash-completion/completions/git')``
        but on Mac is ``'/usr/local/etc/bash_completion',
                        '/opt/local/etc/profile.d/bash_completion.sh')``.
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
    * - FORCE_POSIX_PATHS
      - Not defined
      - Forces forward slashes (``/``) on Windows systems when using auto completion if 
        set to anything truthy.
    * - FORMATTER_DICT
      - xonsh.environ.FORMATTER_DICT  
      - Dictionary containing variables to be used when formatting PROMPT and TITLE 
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    * - MULTILINE_PROMPT
      - ``'.'``
      - Prompt text for 2nd+ lines of input, may be str or function which returns 
        a str.
    * - PROMPT
      - xonsh.environ.DEFAULT_PROMPT  
      - The prompt text.  May contain keyword arguments which are auto-formatted,
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    * - SHELL_TYPE
      - ``'readline'``
      - Which shell is used. Currently two shell types are supported: ``'readline'`` that
        is backed by Python's readline module, and ``'prompt_toolkit'`` that uses 
        external library of the same name. For using prompt_toolkit shell you need 
        to have 
        `prompt_toolkit <https://github.com/jonathanslenders/python-prompt-toolkit>`_
        library installed. To specify which shell should be used, do so in the run 
        control file.
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
    * - TITLE
      - xonsh.environ.DEFAULT_TITLE
      - The title text for the window in which xonsh is running. Formatted in the same 
        manner as PROMPT, 
        see `Customizing the Prompt <tutorial.html#customizing-the-prompt>`_.
    * - XONSHRC
      - ``'~/.xonshrc'``
      - Location of run control file.
    * - XONSH_CONFIG_DIR
      - ``$XDG_CONFIG_HOME/xonsh``
      - This is location where xonsh configuration information is stored.
    * - XONSH_DATA_DIR
      - ``$XDG_DATA_HOME/xonsh``
      - This is the location where xonsh data files are stored, such as history.
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
    * - XONSH_SHOW_TRACEBACK
      - Not defined
      - Controls if a traceback is shown exceptions occur in the shell. Set ``'True'`` 
        to always show or ``'False'`` to always hide. If undefined then traceback is 
        hidden but a notice is shown on how to enable the traceback.
    * - XONSH_STORE_STDOUT 
      - ``False``
      - Whether or not to store the stdout and stderr streams in the history files.

