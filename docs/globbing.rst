Globbing
========

Xonsh supports four forms of filename globbing: normal (shell-style) globbing,
regular expression globbing, match globbing, and formatted glob literals. All
can be used in both subprocess mode and Python mode.


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


Match Globbing
--------------

The ``m`` modifier enables **match globbing** — a regex glob that returns
capture groups instead of full paths. This lets you destructure matched paths
directly:

.. code-block:: xonshcon

    @ for parent, file in m`.*/(.*)/(.*\.py)`:
          print(parent, file)
    src main.py
    src utils.py
    tests test_main.py

When the pattern contains capture groups ``()``, each match returns a tuple
of the captured strings. Without groups, full paths are returned — same as
``r`` glob, but with full-path matching instead of segment-by-segment.

This is useful for extracting path components without manual splitting:

.. code-block:: xonshcon

    @ # Find all .png files and get (directory, filename) pairs
    @ pairs = m`images/(.*)/(.*\.png)`
    @ print(pairs)
    [('icons', 'logo.png'), ('photos', 'cat.png')]

    @ # Single group — returns flat list of strings
    @ names = m`src/(.*)\.py`
    @ print(names)
    ['main', 'utils']

Unlike ``r`` glob which matches segment-by-segment, ``m`` glob applies the
regex to the **full path**. This means regex features like groups and
backreferences can span across ``/``.

``$DOTGLOB`` is respected — hidden files and directories are excluded by
default.


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


XonshList
---------

All glob forms (``g``, ``r``, ``m``, ``p``) return a ``XonshList`` — an
extended list with convenience methods for common shell operations. Every
method returns a new ``XonshList``, so calls can be chained:

.. code-block:: xonshcon

    @ g`**/*.py`.files().sorted()
    ['setup.py', 'src/main.py', 'tests/test_main.py']

    @ r`.*\.log`.exists().paths()
    [PosixPath('app.log'), PosixPath('error.log')]

    @ m`src/(.*)\.py`.unique().sorted()
    ['config', 'main', 'utils']

Available methods:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``.sorted(key=, reverse=)``
     - Return a new sorted list. Unlike ``list.sort()``, returns the list
       for chaining.
   * - ``.unique()``
     - Remove duplicates, preserving order.
   * - ``.filter(func)``
     - Keep only elements where ``func(elem)`` is truthy.
   * - ``.select(n)``
     - Pick the n-th element from each tuple (for multi-group ``m`` globs).
       Skips ``None`` values from optional groups.
   * - ``.paths()``
     - Convert elements to ``pathlib.Path`` objects.
   * - ``.files()``
     - Keep only existing regular files.
   * - ``.dirs()``
     - Keep only existing directories.
   * - ``.exists()``
     - Keep only paths that exist on disk.
   * - ``.visible()``
     - Keep only visible (non-hidden) entries.
   * - ``.hidden()``
     - Keep only hidden entries (dotfiles on Unix, ``FILE_ATTRIBUTE_HIDDEN``
       on Windows).

A more complete example — find all Python test files, convert to ``Path``
objects, and extract just the filenames:

.. code-block:: xonshcon

    @ g`tests/**/*.py`.files().paths().filter(lambda p: p.stem.startswith('test_'))
    [PosixPath('tests/test_main.py'), PosixPath('tests/test_utils.py')]

Working with Tuples from Match Globs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``m`` glob has multiple capture groups, the result is a list of tuples.
Path-based methods (``.files()``, ``.dirs()``, ``.exists()``, ``.paths()``)
don't work on tuples — use ``.select(n)`` first to extract a specific element:

.. code-block:: xonshcon

    @ results = m`src/(.*)/(.*\.py)`
    @ print(results[:2])
    [('lib', 'utils.py'), ('lib', 'main.py')]

    @ results.files()  # TypeError!
    TypeError: .files() requires string paths, got tuples.
    Use .select(n) to pick a tuple element first, e.g. .select(0).files()

    @ # Extract directory names
    @ results.select(0).unique().sorted()
    ['lib', 'tests']

    @ # Extract filenames
    @ results.select(1).sorted()
    ['main.py', 'utils.py']

Methods that don't need paths — ``.unique()``, ``.sorted()``, ``.filter()``
— work on tuples directly:

.. code-block:: xonshcon

    @ m`src/(.*)/(.*\.py)`.unique().sorted()[:3]
    [('lib', 'main.py'), ('lib', 'utils.py'), ('tests', 'test_main.py')]

``XonshList`` is a regular ``list`` subclass, so it works everywhere a list
does — iteration, indexing, ``len()``, passing to functions, etc.


Full-Path Regex via Custom Search
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Xonsh supports custom path search functions with the ``@func`pattern``` syntax.
This can be used to implement full-path regex matching where the pattern is
applied to the entire path, not split by ``/``:

.. code-block:: python

    @ def refullglob(pattern):
          import re, os
           regex = re.compile(pattern)
           results = []
           for root, dirs, files in os.walk('.'):
               for name in dirs + files:
                   path = os.path.join(root, name)
                   if regex.fullmatch(path):
                       results.append(path)
           return results
    @ @refullglob`(.*/)*\w+\.py`
    ['./src/main.py', './src/utils.py', './tests/test_main.py']

This approach has trade-offs compared to the built-in ``r`` glob:

- **Pro:** the full ``re`` syntax works — groups, backreferences, and
  alternations can span across ``/``.
- **Con:** it always walks the entire directory tree. On large trees this is
  slower than the built-in segment-by-segment pruning.
- **Con:** ``$DOTGLOB`` is not automatically respected — add filtering for
  names starting with ``.`` if needed.

