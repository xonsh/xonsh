**Added:**

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

**Changed:**

* Because of the addition of "optional items" to the prompt format string, the
  functions ``xonsh.environ.current_branch``, ``xonsh.environ.env_name`` and
  formatter dict items ``curr_branch``, ``current_job``, ``env_name`` are
  no longer padded with a separator.

**Deprecated:** None

**Removed:**

* ``xonsh.environ.format_prompt`` has been dropped; ``partial_format_prompt``
  can be used instead.

**Fixed:** None

**Security:** None
