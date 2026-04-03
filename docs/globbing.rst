Globbing
========

Xonsh supports three forms of filename globbing: normal (shell-style) globbing,
regular expression globbing, and formatted glob literals. All three can be used
in both subprocess mode and Python mode.


Normal Globbing
---------------

Filename globbing with the ``*`` character is allowed in subprocess mode.
This uses Python's ``glob`` module under the covers. As an example, start with
a directory of files:

.. code-block:: xonshcon

    @ mkdir -p test/a/b
    @ touch test/f.txt test/a/f.txt test/a/b/f.txt
    @ ls test
    a  f.txt

In subprocess mode, normal globbing happens without any special syntax.
However, there is backtick syntax that is available inside Python mode as well
as subprocess mode. This can be done using ``g``:

.. code-block:: xonshcon

    @ ls test/*.txt
    test/f.txt
    @ print(g`test/*.txt`)
    ['test/f.txt']

The ``*`` wildcard matches any characters within a single path component.
The ``?`` wildcard matches a single character. The ``[abc]`` syntax matches one
of the enclosed characters.

Recursive globbing with ``**`` matches zero or more intermediate directories.
For example, ``test/**/f.txt`` matches ``test/f.txt``, ``test/a/f.txt``, and
``test/a/b/f.txt``:

.. code-block:: xonshcon

    @ print(g`test/**/f.txt`)
    ['test/a/b/f.txt', 'test/a/f.txt', 'test/f.txt']


Hidden (Dot) Files
------------------

By default, globbing excludes hidden files and directories — those whose names
begin with a literal ``.``. The ``$DOTGLOB`` environment variable controls this
for all globbing forms: normal globs (``g``), regex globs (``r``), and bare
subprocess wildcards.

When ``$DOTGLOB`` is ``False`` (the default), dotfiles are filtered out:

.. code-block:: xonshcon

    @ touch visible .hidden
    @ print(g`*`)
    ['visible']

When ``$DOTGLOB`` is ``True``, dotfiles are included:

.. code-block:: xonshcon

    @ $DOTGLOB = True
    @ print(g`*`)
    ['.hidden', 'visible']

The same applies to regex globs:

.. code-block:: xonshcon

    @ $DOTGLOB = True
    @ print(`\..*`)
    ['.hidden']


Regular Expression Globbing
---------------------------

If you have ever felt that normal globbing could use some more octane,
then regex globbing is the tool for you! Any string that uses backticks
(`````) instead of quotes (``'``, ``"``) is interpreted as a regular
expression to match filenames against. Like with regular globbing, a
list of successful matches is returned. In Python mode, this is just a
list of strings. In subprocess mode, each filename becomes its own argument
to the subprocess command.

This same kind of search is performed if the backticks are prefaced with ``r``.
So the following expressions are equivalent: ````test```` and ``r`test```.

.. code-block:: xonshcon

    @ touch a aa aaa aba abba aab aabb abcba
    @ ls `a(a+|b+)a`
    aaa  aba  abba
    @ print(`a(a+|b+)a`)
    ['aaa', 'aba', 'abba']

Segment-by-Segment Matching
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Regex globbing splits the pattern by the path separator (``/``) and compiles
each segment as a separate regular expression. At each directory level, only
entries matching the current segment are visited. This prunes the directory
tree early and avoids a full recursive walk.

However, this means that regex features spanning across ``/`` will break because
the segments are no longer valid regexes on their own:

.. code-block:: xonshcon

    @ # Group split across / — each segment gets an unmatched parenthesis
    @ r`(.*/)*\w+\.py`
    re.error: missing ), unterminated subpattern at position 0

    @ # Backreference across / — refers to a group in a different segment
    @ r`(\w+)/(\1)\.py`
    re.error: cannot refer to an open group at position 8

Full-Path Regex via Custom Search
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Xonsh supports custom path search functions with the ``@func`pattern``` syntax.
This can be used to implement full-path regex matching where the pattern is
applied to the entire path, not split by ``/``:

.. code-block:: xonshcon

    @ import re, os
    @ def refullglob(pattern):
    ...     regex = re.compile(pattern)
    ...     results = []
    ...     for root, dirs, files in os.walk('.'):
    ...         for name in dirs + files:
    ...             path = os.path.join(root, name)
    ...             if regex.fullmatch(path):
    ...                 results.append(path)
    ...     return results
    @ @refullglob`(.*/)*\w+\.py`
    ['./src/main.py', './src/utils.py', './tests/test_main.py']

This approach has trade-offs compared to the built-in ``r`` glob:

- **Pro:** the full ``re`` syntax works — groups, backreferences, and
  alternations can span across ``/``.
- **Con:** it always walks the entire directory tree. On large trees this is
  slower than the built-in segment-by-segment pruning.
- **Con:** ``$DOTGLOB`` is not automatically respected — add filtering for
  names starting with ``.`` if needed.


Formatted Glob Literals
-----------------------

Using the ``f`` modifier with either regex or normal globbing makes
the glob pattern behave like a formatted string literal. This can be used to
substitute variables and other expressions into the glob pattern:

.. code-block:: xonshcon

    @ touch a aa aaa aba abba aab aabb abcba
    @ mypattern = 'ab'
    @ print(f`{mypattern[0]}+`)
    ['a', 'aa', 'aaa']
    @ print(gf`{mypattern}*`)
    ['aba', 'abba', 'abcba']


Sorting
-------

By default, glob results are sorted alphabetically. The ``$GLOB_SORTED``
environment variable controls this for normal globs. Setting it to ``False``
returns results in arbitrary filesystem order:

.. code-block:: xonshcon

    @ $GLOB_SORTED = False
    @ g`*`
    ['setup.py', 'README.md']

Regex globs are always sorted regardless of this setting.
