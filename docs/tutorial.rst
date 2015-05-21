.. _tutorial:

*******************
Tutorial
*******************
xonsh is a shell language and command prompt. Unlike other shells, xonsh is
based on Python, with additional syntax added that makes calling subprocess
commands, manipulating the environment, and dealing with the file system
easily.  The xonsh command prompt gives users interactive access to the xonsh
language.

While all Python code is also xonsh, not all BASH code can be used in xonsh.
That would defeat the purpose, and Python is better anyway! Still, xonsh is
BASH-wards compatible in the ways that matter, such as for running commands,
reading in the BASH environment, and utilizing BASH tab completion.

The purpose of this tutorial is to teach you xonsh. There are many excellent
guides out there for learning Python, and this will not join their ranks.
Similarly, you'd probably get the most out of this tutorial if you have already
used a command prompt or interactive interpreter.

Let's dive in!

Starting xonsh
========================
Assuming you have successfully installed xonsh (see http://xonsh.org),
you can start up the xonsh interpreter via the ``xonsh`` command. Suppose
you are in a lesser terminal:

.. code-block:: bash

    bash $ xonsh
    snail@home ~ $

Now we are in a xonsh shell. Our username happens to be ``snail``, our
hostname happens to be ``home``, and we are in our home directory (``~``).
Alternatively, you can setup your terminal emulator (xterm, gnome-terminal,
etc) to run xonsh automatically when it starts up. This is recommended.

Basics
=======================
The xonsh language is based on Python, and the xonsh shell uses Python to
interpret any input it receives. This makes simple things, like arithmetic,
simple:

.. code-block:: xonshcon

    >>> 1 + 1
    2

.. note:: From here on we'll be using ``>>>`` to prefix (or prompt) any
          xonsh input. This follows the Python convention and helps trick
          syntax highlighting, though ``$`` is more traditional for shells.

Since this is just Python, we are able import modules, print values,
and use other built-in Python functionality:

.. code-block:: xonshcon

    >>> import sys
    >>> print(sys.version)
    3.4.2 |Continuum Analytics, Inc.| (default, Oct 21 2014, 17:16:37)
    [GCC 4.4.7 20120313 (Red Hat 4.4.7-1)]


We can also create and use literal data types, such as ints, floats, lists,
sets, and dictionaries. Everything that you are used to if you already know
Python is there:

.. code-block:: xonshcon

    >>> d = {'xonsh': True}
    >>> d.get('bash', False)
    False

The xonsh shell also supports multi-line input for more advanced flow control.
The multi-line mode is automatically entered whenever the first line of input
is not syntactically valid on its own.  Multi-line mode is then exited when
enter (or return) is pressed when the cursor is in the first column.

.. code-block:: xonshcon

    >>> if True:
    ...     print(1)
    ... else:
    ...     print(2)
    ...
    1

Flow control, of course, includes loops.

.. code-block:: xonshcon

    >>> for i, x in enumerate('xonsh'):
    ...     print(i, x)
    ...
    0 x
    1 o
    2 n
    3 s
    4 h

We can also define and call functions and classes. I'll mostly spare you the
details, but this *is* pretty cool:

.. code-block:: xonshcon

    >>> def f():
    ...     return "xonsh"
    ...
    >>> f()
    'xonsh'

For easier indentation, Shift+Tab will enter 4 spaces.
And that about wraps it up for the basics section.  It is just like Python.

Environment Variables
=======================
Environment variables are written as ``$`` followed by a name.  For example,
``$HOME``, ``$PWD``, and ``$PATH``.

.. code-block:: xonshcon

    >>> $HOME
    '/home/snail'

You can set (and export) environment variables like you would set any other
variable in Python.  The same is true for deleting them too.

.. code-block:: xonshcon

    >>> $GOAL = 'Become the Lord of the Files'
    >>> print($GOAL)
    Become the Lord of the Files
    >>> del $GOAL

Very nice. All environment variables live in the built-in
``__xonsh_env__`` mapping. You can access this mapping directly, but in most
situations, you shouldn't need to.

Like other variables in Python, environment variables have a type. Sometimes
this type is imposed based on the variable name. The current rules are pretty
simple:

* ``PATH``: any variable whose name contains PATH is a list of strings.
* ``XONSH_HISTORY_SIZE``: this variable is an int.

xonsh will automatically convert back and forth to untyped (string-only)
representations of the environment as needed (mostly by subprocess commands).
When in xonsh, you'll always have the typed version.  Here are a couple of
PATH examples:

.. code-block:: xonshcon

    >>> $PATH
    ['/home/snail/.local/bin', '/home/snail/sandbox/bin',
    '/home/snail/miniconda3/bin', '/usr/local/bin', '/usr/local/sbin',
    '/usr/bin', '/usr/sbin', '/bin', '/sbin', '.']
    >>> $LD_LIBRARY_PATH
    ['/home/snail/.local/lib', '']

Also note that *any* Python object can go into the environment. It is sometimes
useful to have more sophisticated types, like functions, in the environment.
There are handful of environment variables that xonsh considers special.
They can be seen in the table below:

================== ============================= ================================
variable           default                       description
================== ============================= ================================
ALIASES            xonsh.aliases.DEFAULT_ALIASES A dictionary containing aliases.
                                                 See `Aliases`_ below for more
                                                 information.
PROMPT             xonsh.environ.DEFAULT_PROMPT  The prompt text.  May contain
                                                 keyword arguments which are
                                                 auto-formatted (see `Customizing
                                                 the Prompt`_ below).
MULTILINE_PROMPT   ``'.'``                       Prompt text for 2nd+ lines of
                                                 input, may be str or
                                                 function which returns a str.
TITLE              xonsh.environ.DEFAULT_TITLE   The title text for the window
                                                 in which xonsh is running.
                                                 Formatted in the same manner
                                                 as PROMPT (see `Customizing the
                                                 Prompt`_ below).
FORMATTER_DICT     xonsh.environ.FORMATTER_DICT  Dictionary containing variables
                                                 to be used when formatting PROMPT
                                                 and TITLE (see `Customizing the
                                                 Prompt`_ below).
XONSHRC            ``'~/.xonshrc'``              Location of run control file
XONSH_HISTORY_SIZE 8128                          Number of items to store in the
                                                 history.
XONSH_HISTORY_FILE ``'~/.xonsh_history'``        Location of history file
XONSH_INTERACTIVE                                ``True`` if xonsh is running 
                                                 interactively, and ``False`` 
                                                 otherwise.
BASH_COMPLETIONS   ``[] or ['/etc/...']``        This is a list of strings that
                                                 specifies where the BASH
                                                 completion files may be found.
                                                 The default values are platform
                                                 dependent, but sane.  To
                                                 specify an alternate list,
                                                 do so in the run control file.
SUGGEST_COMMANDS   ``True``                      When a user types an invalid
                                                 command, xonsh will try to offer
                                                 suggestions of similar valid
                                                 commands if this is ``True``.
SUGGEST_THRESHOLD  ``3``                         An error threshold.  If the
                                                 Levenshtein distance between the
                                                 entered command and a valid
                                                 command is less than this value,
                                                 the valid command will be
                                                 offered as a suggestion.
SUGGEST_MAX_NUM    ``5``                         xonsh will show at most this
                                                 many suggestions in response to
                                                 an invalid command.  If
                                                 negative, there is no limit to
                                                 how many suggestions are shown.
================== ============================= ================================

Environment Lookup with ``${}``
================================
The ``$NAME`` is great as long as you know the name of the environment
variable you want to look up.  But what if you want to construct the name
programmatically, or read it from another variable?  Enter the ``${}``
operator.

.. warning:: In BASH, ``$NAME`` and ``${NAME}`` are syntactically equivalent.
             In xonsh, they have separate meanings.

We can place any valid Python expression inside of the curly braces in
``${<expr>}``. This result of this expression will then be used to look up a
value in the environment.  In fact, ``${<expr>}`` is the same as doing
``__xonsh_env__[<expr>]``, but much nicer to look at. Here are a couple of
examples in action:

.. code-block:: xonshcon

    >>> x = 'USER'
    >>> ${x}
    'snail'
    >>> ${'HO' + 'ME'}
    '/home/snail'

Not bad, xonsh, not bad.


Running Commands
==============================
As a shell, xonsh is meant to make running commands easy and fun.
Running subprocess commands should work like any other in any other shell.

.. code-block:: xonshcon

    >>> echo "Yoo hoo"
    Yoo hoo
    >>> cd xonsh
    >>> ls
    build  docs     README.rst  setup.py  xonsh           __pycache__
    dist   license  scripts     tests     xonsh.egg-info
    >>> dir scripts
    xonsh  xonsh.bat
    >>> git status
    On branch master
    Your branch is up-to-date with 'origin/master'.
    Changes not staged for commit:
      (use "git add <file>..." to update what will be committed)
      (use "git checkout -- <file>..." to discard changes in working directory)

        modified:   docs/tutorial.rst

    no changes added to commit (use "git add" and/or "git commit -a")
    >>> exit

This should feel very natural.


Python-mode vs Subprocess-mode
================================
It is sometimes helpful to make the distinction between lines that operate
in pure Python mode and lines that use shell-specific syntax, edit the
execution environment, and run commands. Unfortunately, it is not always
clear from the syntax alone what mode is desired. This ambiguity stems from
most command line utilities looking a lot like Python operators.

Take the case of ``ls -l``.  This is valid Python code, though it could
have also been written as ``ls - l`` or ``ls-l``.  So how does xonsh know
that ``ls -l`` is meant to be run in subprocess-mode?

For any given line that only contains an expression statement (expr-stmt,
see the Python AST docs for more information), if the left-most name cannot
be found as a current variable name xonsh will try to parse the line as a
subprocess command instead.  In the above, if ``ls`` is not a variable,
then subprocess mode will be attempted. If parsing in subprocess mode fails,
then the line is left in Python-mode.

In the following example, we will list the contents of the directory
with ``ls -l``. Then we'll make new variable names ``ls`` and ``l`` and then
subtract them. Finally, we will delete ``ls`` and ``l`` and be able to list
the directories again.

.. code-block:: xonshcon

    >>> # this will be in subproc-mode, because ls doesn't exist
    >>> ls -l
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh
    >>> # set an ls variable to force python-mode
    >>> ls = 44
    >>> l = 2
    >>> ls -l
    42
    >>> # deleting ls will return us to supbroc-mode
    >>> del ls
    >>> ls -l
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh

The determination between Python- and subprocess-modes is always done in the
safest possible way. If anything goes wrong, it will favor Python-mode.
The determination between the two modes is done well ahead of any execution.
You do not need to worry about partially executed commands - that is
impossible.

If you absolutely want to run a subprocess command, you can always
force xonsh to do so with the syntax that we will see in the following
sections.


Captured Subprocess with ``$()``
================================
The ``$(<expr>)`` operator in xonsh executes a subprocess command and
*captures* the output. The expression in the parentheses will be run and
stdout will be returned as string. This is similar to how ``$()`` performs in
BASH.  For example,

.. code-block:: xonshcon

    >>> $(ls -l)
    'total 0\n-rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh\n'

The ``$()`` operator is an expression itself. This means that we can
assign the results to a variable or perform any other manipulations we want.

.. code-block:: xonshcon

    >>> x = $(ls -l)
    >>> print(x.upper())
    TOTAL 0
    -RW-RW-R-- 1 SNAIL SNAIL 0 MAR  8 15:46 XONSH

While in subprocess-mode or inside of a captured subprocess, we can always
still query the environment with ``$NAME`` variables.

.. code-block:: xonshcon

    >>> $(echo $HOME)
    '/home/snail\n'

Uncaptured Subprocess with ``$[]``
===================================
Uncaptured subprocess are denoted with the ``$[<expr>]`` operator. They are
the same as ``$()`` captured subprocesses in almost every way. The only
difference is that the subprocess's stdout passes directly through xonsh and
to the screen.  The return value of ``$[]`` is always ``None``.

In the following, we can see that the results of ``$[]`` are automatically
printed and the return value is not a string.

.. code-block:: xonshcon

    >>> x = $[ls -l]
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh
    >>> x is None
    True

Previously when we automatically entered subprocess-mode, uncaptured
subprocesses were used.  Thus ``ls -l`` and ``$[ls -l]`` are usually
equivalent.

Python Evaluation with ``@()``
===============================

The ``@(<expr>)`` operator from will evaluate arbitrary Python code in
subprocess mode, and the result will be appended to the subprocess command
list. If the result is a string, it is appended to the argument list.
If the result is a list or other non-string sequence, the contents are
converted to strings and appended to the argument list in order. Otherwise, the
result is automatically converted to a string.  For example,

.. code-block:: xonshcon

    >>> x = 'xonsh'
    >>> y = 'party'
    >>> echo @(x + ' ' + y)
    xonsh party
    >>> echo @(2+2)
    4
    >>> echo @([42, 'yo'])
    42 yo

This syntax can be used inside of a captured or uncaptured subprocess, and can
be used to generate any of the tokens in the subprocess command list.

.. code-block:: xonshcon

    >>> out = $(echo @(x + ' ' + y))
    >>> out
    'xonsh party\n'
    >>> @("ech" + "o") "hey"
    hey

Thus, ``@()`` allows us to create complex commands in Python-mode and then
feed them to a subprocess as needed.  For example:

.. code-block:: xonsh

    for i in range(20):
        $[touch @('file%02d' % i)]


Nesting Subprocesses
=====================================
Though I am begging you not to abuse this, it is possible to nest the
subprocess operators that we have seen so far (``$()``, ``$[]``, ``${}``,
``@()``).  An instance of ``ls -l`` that is on the wrong side of the border of
the absurd is shown below:

.. code-block:: xonshcon

    >>> $[$(echo ls) @('-' + $(echo l).strip())]
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh

With great power, and so forth...

.. note:: Nesting these subprocess operators inside of ``$()`` and/or ``$[]``
          works, because the contents of those operators are executed in
          subprocess mode.  Since ``@()`` and ``${}`` run their contents in
          Python mode, it is not possible to nest other subprocess operators
          inside of them.



Pipes with ``|``
====================================
In subprocess-mode, xonsh allows you to use the ``|`` character to pipe
together commands as you would in other shells.

.. code-block:: xonshcon

    >>> env | uniq | sort | grep PATH
    DATAPATH=/usr/share/MCNPX/v260/Data/
    DEFAULTS_PATH=/usr/share/gconf/awesome-gnome.default.path
    LD_LIBRARY_PATH=/home/snail/.local/lib:
    MANDATORY_PATH=/usr/share/gconf/awesome-gnome.mandatory.path
    PATH=/home/snail/.local/bin:/home/snail/sandbox/bin:/usr/local/bin
    XDG_SEAT_PATH=/org/freedesktop/DisplayManager/Seat0
    XDG_SESSION_PATH=/org/freedesktop/DisplayManager/Session0

This is only available in subprocess-mode because ``|`` is otherwise a
Python operator.
If you are unsure of what pipes are, there are many great references out there.
You should be able to find information on StackOverflow or Google.


Writing Files with ``>``
=====================================
In subprocess-mode, if the second to last element is a greater-than sign
``>`` and the last element evaluates to a string, the output of the
preceding command will be written to file. If the file already exists, the
current contents will be erased.  For example, let's write a simple file
called ``conch.txt`` using ``echo``:

.. code-block:: xonshcon

    >>> echo Piggy > conch.txt
    'Piggy\n'
    >>> cat conch.txt
    Piggy

This can be pretty useful.  This does not work in Python-mode, since ``>``
is a valid Python operator.


Appending to Files with ``>>``
=====================================
Following the same syntax as with ``>`` in subprocess-mode, the ``>>``
operator allows us to append to a file rather than overwriting it completely.
If the file doesn't exist, it is created. Let's reuse the ``conch.txt``
file from above and add a line.

.. code-block:: xonshcon

    >>> echo Ralph >> conch.txt
    'Ralph\n'
    >>> cat conch.txt
    Piggy
    Ralph

Again, the ``>>`` does not work as shown here in Python-mode, where it takes
on its usual meaning.


Background Jobs
===============

Typically, when you start a program running in xonsh, xonsh itself will pause
and wait for that program to terminate.  Sometimes, though, you may want to
continue giving commands to xonsh while that program is running.  In subprocess
mode, you can start a process "in the background" (i.e., in a way that allows
continued use of the shell) by adding an ampersand (``&``) to the end of your
command.  Background jobs are very useful when running programs with graphical
user interfaces.

The following shows an example with ``emacs``.

.. code-block:: xonshcon

    >>> emacs &
    >>>

Note that the prompt is returned to you after emacs is started.

Job Control
===========

If you start a program in the foreground (with no ampersand), you can suspend
that program's execution and return to the xonsh prompt by pressing Control-Z.
This will give control of the terminal back to xonsh, and will keep the program
paused in the background.

.. note:: Suspending processes via Control-Z is not yet supported when
	  running on Windows.

To unpause the program and bring it back to the foreground, you can use the
``fg`` command.  To unpause the program have it continue in the background
(giving you continued access to the xonsh prompt), you can use the ``bg``
command.

You can get a listing of all currently running jobs with the ``jobs`` command.

Each job has a unique identifier (starting with 1 and counting upward).  By
default, the ``fg`` and ``bg`` commands operate on the job that was started
most recently.  You can bring older jobs to the foreground or background by
specifying the appropriate ID; for example, ``fg 1`` brings the job with ID 1
to the foreground.

String Literals in Subprocess-mode
====================================
Strings can be used to escape special characters in subprocess-mode. The
contents of the string are passed directly to the subprocess command as a
single argument.  So whenever you are in doubt, or if there is a xonsh syntax
error because of a filename, just wrap the offending portion in a string.

A common use case for this is files with spaces in their names. This
detestable practice refuses to die. "No problem!" says xonsh, "I have
strings."  Let's see it go!

.. code-block:: xonshcon

    >>> touch "sp ace"
    >>> ls -l
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 17:50 sp ace
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh

Spaces in filenames, of course, are just the beginning.


Filename Globbing with ``*``
===============================
Filename globbing with the ``*`` character is also allowed in subprocess-mode.
This simply uses Python's glob module under-the-covers.  See there for more
details.  As an example, start with a lovely bunch of xonshs:

.. code-block:: xonshcon

    >>> touch xonsh conch konk quanxh
    >>> ls
    conch  konk  quanxh  xonsh
    >>> ls *h
    conch  quanxh  xonsh
    >>> ls *o*
    conch  konk  xonsh

This is not available in Python-mode, because multiplication is pretty
important.


Regular Expression Filename Globbing with Backticks
=====================================================
If you have ever felt that normal globbing could use some more octane,
then regex globbing is the tool for you! Any string that uses backticks
(`````) instead of quotes (``'``, ``"``) is interpreted as a regular
expression to match filenames against.  Like with regular globbing, a
list of successful matches is returned.  In Python-mode, this is just a
list of strings. In subprocess-mode, each filename becomes its own argument
to the subprocess command.

Let's see a demonstration with some simple filenames:


.. code-block:: xonshcon

    >>> touch a aa aaa aba abba aab aabb abcba
    >>> ls `a(a+|b+)a`
    aaa  aba  abba
    >>> print(`a(a+|b+)a`)
    ['aaa', 'aba', 'abba']
    >>> len(`a(a+|b+)a`)
    3

Other than the regex matching, this functions in the same way as normal
globbing.
For more information, please see the documentation for the ``re`` module in
the Python standard library.

.. warning:: This backtick syntax has very different from that of BASH.  In
             BASH, backticks means to run a captured subprocess ``$()``.


Help & Superhelp with ``?`` & ``??``
=====================================================
From IPython, xonsh allows you to inspect objects with question marks.
A single question mark (``?``) is used to display normal level of help.
Double question marks (``??``) are used to display higher level of help,
called superhelp. Superhelp usually includes source code if the object was
written in pure Python.

Let's start by looking at the help for the int type:

.. code-block:: xonshcon

    >>> int?
    Type:            type
    String form:     <class 'int'>
    Init definition: (self, *args, **kwargs)
    Docstring:
    int(x=0) -> integer
    int(x, base=10) -> integer

    Convert a number or string to an integer, or return 0 if no arguments
    are given.  If x is a number, return x.__int__().  For floating point
    numbers, this truncates towards zero.

    If x is not a number or if base is given, then x must be a string,
    bytes, or bytearray instance representing an integer literal in the
    given base.  The literal can be preceded by '+' or '-' and be surrounded
    by whitespace.  The base defaults to 10.  Valid bases are 0 and 2-36.
    Base 0 means to interpret the base from the string as an integer literal.
    >>> int('0b100', base=0)
    4
    <class 'int'>

Now, let's look at the superhelp for the xonsh built-in that enables
regex globbing:

.. code-block:: xonshcon

    >>> __xonsh_regexpath__??
    Type:        function
    String form: <function regexpath at 0x7fef91612950>
    File:        /home/scopatz/.local/lib/python3.4/site-packages/xonsh-0.1-py3.4.egg/xonsh/built_ins.py
    Definition:  (s)
    Source:
    def regexpath(s):
        """Takes a regular expression string and returns a list of file
        paths that match the regex.
        """
        s = expand_path(s)
        return reglob(s)
    <function regexpath at 0x7fef91612950>

Note that both help and superhelp return the object that they are inspecting.
This allows you to chain together help inside of other operations and
ask for help several times in an object hierarchy.  For instance, let's get
help for both the dict type and its key() method simultaneously:

.. code-block:: xonshcon

    >>> dict?.keys??
    Type:            type
    String form:     <class 'dict'>
    Init definition: (self, *args, **kwargs)
    Docstring:
    dict() -> new empty dictionary
    dict(mapping) -> new dictionary initialized from a mapping object's
        (key, value) pairs
    dict(iterable) -> new dictionary initialized as if via:
        d = {}
        for k, v in iterable:
            d[k] = v
    dict(**kwargs) -> new dictionary initialized with the name=value pairs
        in the keyword argument list.  For example:  dict(one=1, two=2)
    Type:        method_descriptor
    String form: <method 'keys' of 'dict' objects>
    Docstring:   D.keys() -> a set-like object providing a view on D's keys
    <method 'keys' of 'dict' objects>

Of course, for subprocess commands, you still want to use the ``man`` command.


Compile, Evaluate, & Execute
================================
Like Python and BASH, xonsh provides built-in hooks to compile, evaluate,
and execute strings of xonsh code.  To prevent this functionality from having
serious name collisions with the Python built-in ``compile()``, ``eval()``,
and ``exec()`` functions, the xonsh equivalents all append an 'x'.  So for
xonsh code you want to use the ``compilex()``, ``evalx()``, and ``execx()``
functions. If you don't know what these do, you probably don't need them.


Up, Down, Tab
==============
The up and down keys search history matching from the start of the line,
much like they do in the IPython shell.

Tab completion is present as well. In Python-mode you are able to complete
based on the variable names in the current builtins, globals, and locals,
as well as xonsh languages keywords & operator, files & directories, and
environment variable names. In subprocess-mode, you additionally complete
on any file names on your ``$PATH``, alias keys, and full BASH completion
for the commands themselves.

Aliases
==============================
An important environment variable is the ``$ALIASES`` mapping.  This is
like a dictionary that effects how subprocess commands are run.  If you are
familiar with the BASH ``alias`` built-in, this is similar.  Alias command
matching only occurs for the first element of a subprocess command.

The keys of ``$ALIASES`` are strings that act as commands in subprocess-mode.
The values are lists of strings, where the first element is the command and
the rest are the arguments. You can also set the value to a string, in which
case it will be converted to a list automatically with ``shlex.split``.

For example, here are some of the default aliases:

.. code-block:: python

    DEFAULT_ALIASES = {
        'ls': 'ls --color=auto -v',
        'grep': 'grep --color=auto',
        'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
        'ipynb': ['ipython', 'notebook', '--no-browser'],
        }

If you were to run ``ls dir/`` with the aliases above in effect (by running
``$ALIASES.update(DEFAULT_ALIASES)``), it would reduce to
``["ls", "--color=auto", "-v", "dir/"]`` before being executed.

Lastly, if an alias value is a function (or other callable), then this
function is called *instead* of going to a subprocess command. Such functions
must have the following signature:

.. code-block:: python

    def mycmd(args, stdin=None):
        """args will be a list of strings representing the arguments to this
        command. stdin will be a string, if present. This is used to pipe
        the output of the previous command into this one.
        """
        # do whatever you want! Anything you print to stdout or stderr
        # will be captured for you automatically. This allows callable
        # aliases to support piping.
        print('I go to stdout and will be printed or piped')

        # Note: that you have access to the xonsh
        # built-ins if you 'import builtins'.  For example, if you need the
        # environment, you could do to following:
        import bulitins
        env = builtins.__xonsh_env__

        # The return value of the function can either be None,
        return

        # a single string representing stdout
        return  'I am out of here'

        # or you can build up strings for stdout and stderr and then
        # return a (stdout, stderr) tuple. Both of these may be
        # either a str or None. Any results returned like this will be
        # concatenated with the strings printed elsewhere in the function.
        stdout = 'I commanded'
        stderr = None
        return stdout, stderr

We can dynamically alter the aliases present simply by modifying the
built-in mapping.  Here is an example using a function value:

.. code-block:: xonshcon

    >>> $ALIASES['banana'] = lambda args, stdin=None: ('My spoon is tooo big!', None)
    >>> banana
    'My spoon is tooo big!'

Aliasing is a powerful way that xonsh allows you to seamlessly interact to
with Python and subprocess.

Customizing the Prompt
======================

Customizing the prompt is probably the most common reason for altering an
environment variable.  The ``PROMPT`` variable can be a string, or it can be a
function (of no arguments) that returns a string.  The result can contain
keyword arguments, which will be replaced automatically:

.. code-block:: xonshcon

    >>> $PROMPT = '{user}@{hostname}:{cwd} > '
    snail@home:~ > # it works!
    snail@home:~ > $PROMPT = lambda : '{user}@{hostname}:{cwd} >> '
    snail@home:~ >> # so does that!
    
By default, the following variables are available for use:
  * ``user``: The username of the current user
  * ``hostname``: The name of the host computer
  * ``cwd``: The current working directory
  * ``curr_branch``: The name of the current git branch (preceded by space),
    if any.
  * ``branch_color``: ``{BOLD_GREEN}`` if the current git branch is clean,
    otherwise ``{BOLD_RED}``

You can also color your prompt easily by inserting keywords such as ``{GREEN}``
or ``{BOLD_BLUE}``.  Colors have the form shown below:
    
  * ``(QUALIFIER\_)COLORNAME``: Inserts an ANSI color code
      * ``COLORNAME`` can be any of: ``BLACK``, ``RED``, ``GREEN``, ``YELLOW``,
        ``BLUE``, ``PURPLE``, ``CYAN``, or ``WHITE``
      * ``QUALIFIER`` is optional and can be any of: ``BOLD``, ``UNDERLINE``,
        ``BACKGROUND``, ``INTENSE``, ``BOLD_INTENSE``, or 
        ``BACKGROUND_INTENSE``
  * ``NO_COLOR``: Resets any previously used color codes

You can make use of additional variables beyond these by adding them to the
``FORMATTER_PROMPT`` environment variable.  The values in this dictionary
should be strings (which will be inserted into the prompt verbatim), or
functions of no arguments (which will be called each time the prompt is
generated, and the results of those calls will be inserted into the prompt).
For example:

.. code-block:: xonshcon

    snail@home ~ $ $FORMATTER_DICT['test'] = "hey"
    snail@home ~ $ $PROMPT = "{test} {cwd} $ "
    hey ~ $ 
    hey ~ $ import random
    hey ~ $ $FORMATTER_DICT['test'] = lambda: random.randint(1,9)
    3 ~ $ 
    5 ~ $ 
    2 ~ $ 
    8 ~ $ 

Executing Commands and Scripts
==============================
When started with the ``-c`` flag and a command, xonsh will execute that command
and exit, instead of entering the command loop.

.. code-block:: bash

    bash $ xonsh -c "echo @(7+3)"
    10

Longer scripts can be run either by specifying a filename containing the script,
or by feeding them to xonsh via stdin.  For example, consider the following
script, stored in ``test.xsh``:

.. code-block:: xonsh

    #!/usr/bin/env xonsh
    
    ls
    
    print('removing files')
    rm `file\d+.txt`
    
    ls
    
    print('adding files')
    # This is a comment
    for i, x in enumerate("xonsh"):
        echo @(x) > @("file%d.txt" % i)
    
    print($(ls).replace('\n', ' '))


This script could be run by piping its contents to xonsh:

.. code-block:: bash

    bash $ cat test.xsh | xonsh
    file0.txt  file1.txt  file2.txt  file3.txt  file4.txt  test_script.sh
    removing files
    test_script.sh
    adding files
    file0.txt file1.txt file2.txt file3.txt file4.txt test_script.sh

or by invoking xonsh with its filename as an argument:

.. code-block:: bash

    bash $ xonsh test.xsh
    file0.txt  file1.txt  file2.txt  file3.txt  file4.txt  test_script.sh
    removing files
    test_script.sh
    adding files
    file0.txt file1.txt file2.txt file3.txt file4.txt test_script.sh

xonsh scripts can also accept arguments.  These arguments are made available to
the script in two different ways:

#. In either mode, as individual variables ``$ARG<n>`` (e.g., ``$ARG1``)
#. In Python mode only, as a list ``$ARGS``

For example, consider a slight variation of the example script from above that
operates on a given argument, rather than on the string ``'xonsh'`` (notice how
``$ARGS`` and ``$ARG1`` are used):

.. code-block:: xonsh

    #!/usr/bin/env xonsh
    
    print($ARGS)
    
    ls
    
    print('removing files')
    rm `file\d+.txt`
    
    ls
    
    print('adding files')
    # This is a comment
    for i, x in enumerate($ARG1):
        echo @(x) > @("file%d.txt" % i)
    
    print($(ls).replace('\n', ' '))
    print()

.. code-block:: bash

    bash $ xonsh test2.xsh snails
    ['test_script.sh', 'snails']
    file0.txt  file1.txt  file2.txt  file3.txt  file4.txt  file5.txt  test_script.sh
    removing files
    test_script.sh
    adding files
    file0.txt file1.txt file2.txt file3.txt file4.txt file5.txt test_script.sh

    bash $ echo @(' '.join($(cat @('file%d.txt' % i)).strip() for i in range(6)))
    s n a i l s

Importing Xonsh (``*.xsh``)
==============================
You can import xonsh source files with the ``*.xsh`` file extension using
the normal Python syntax.  Say you had a file called ``mine.xsh``, you could
therefore perform a Bash-like source into your current shell with the
following:

.. code-block:: xonsh

    from mine import *


That's All, Folks
======================
To leave xonsh, hit ``Ctrl-D``, type ``EOF``, type ``quit``, or type ``exit``.
On Windows you can also type ``Ctrl-Z``.

.. code-block:: xonshcon

    >>> exit

Now it is your turn.
