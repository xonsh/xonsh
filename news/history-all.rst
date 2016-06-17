**Added:** None

- ``history session``

  ``session`` is equivalent to existing ``show`` and will
  display the current session's history only

- ``history xonsh``
  ``history all``
  
  The ``xonsh`` and ``all`` options are equivalent and will 
  display all history from valid json files found in
  ``XONSH_DATA_DIR``

- ``history zsh``
  ``history bash``

  These options will display all history from the ``HISTFILE``
  specified by each shell respectively. By default these
  are ``~/.zsh_history`` and ``~/.bash_history`` respectively
  but they can also be respectively specified in:
  
  - ``~/.zshrc``/ ``~/.zprofile``
  - ``~/.bashrc``/ ``~/.bash_profile``

  Xonsh will parse this files (rc file first) to check if 
  ``HISTFILE`` has been set.

- Additionally these options are all available from 
  ``__xonsh_history__.show()`` restricted to the following:

  - ``session``
  - ``all``
  - ``zsh``
  - ``bash``

  When invoked in this way the history is returned as a list
  with each item in the format: (name, start_time, index)

- All history is sorted by command start time.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
