**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

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


**Security:** None
