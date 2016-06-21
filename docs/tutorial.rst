.. _tutorial:

*******************
Tutorial
*******************
xonsh is a shell language and command prompt. Unlike other shells, xonsh is
based on Python, with additional syntax added that makes calling subprocess
commands, manipulating the environment, and dealing with the file system
easy.  The xonsh command prompt gives users interactive access to the xonsh
language.

While all Python code is also xonsh, not all Bash code can be used in xonsh.
That would defeat the purpose, and Python is better anyway! Still, xonsh is
Bash-wards compatible in the ways that matter, such as for running commands,
reading in the Bash environment, and utilizing Bash tab completion.

The purpose of this tutorial is to teach you xonsh. There are many excellent
guides out there for learning Python, and this will not join their ranks.
Similarly, you'd probably get the most out of this tutorial if you have already
used a command prompt or interactive interpreter.

Let's dive in!

Starting xonsh
========================
Assuming you have successfully installed xonsh (see http://xon.sh),
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

Very nice.

The Environment Itself ``${...}``
---------------------------------

All environment variables live in the built-in ``${...}`` (aka ``__xonsh_env__``) mapping.
You can access this mapping directly, but in most situations, you shouldn’t need to.

If you want for example to check if an environment variable is present in your current
session (say, in your awesome new ``xonsh`` script) you can use the membership operator:
.. code-block:: xonshcon

   >>> 'HOME' in ${...}
   True

One helpful method on the ``${...}`` is :func:`~xonsh.environ.Env.swap`.
It can be used to temporarily set an environment variable:

.. code-block:: xonshcon

    >>> with ${...}.swap(SOMEVAR='foo'):
    ...     echo $SOMEVAR
    ...
    ...
    foo
    >>> echo $SOMEVAR

    >>>

Environment Lookup with ``${<expr>}``
-------------------------------------

The ``$NAME`` is great as long as you know the name of the environment
variable you want to look up.  But what if you want to construct the name
programmatically, or read it from another variable?  Enter the ``${}``
operator.

.. warning:: In Bash, ``$NAME`` and ``${NAME}`` are syntactically equivalent.
             In xonsh, they have separate meanings.

We can place any valid Python expression inside of the curly braces in
``${<expr>}``. This result of this expression will then be used to look up a
value in the environment. Here are a couple of examples in action:

.. code-block:: xonshcon

    >>> x = 'USER'
    >>> ${x}
    'snail'
    >>> ${'HO' + 'ME'}
    '/home/snail'

Not bad, xonsh, not bad.

Environment Types
-----------------

Like other variables in Python, environment variables have a type. Sometimes
this type is imposed based on the variable name. The current rules are pretty
simple:

* ``\w*PATH``: any variable whose name ends in PATH is a list of strings.
* ``\w*DIRS``: any variable whose name ends in DIRS is a list of strings.
* ``XONSH_HISTORY_SIZE``: this variable is an int.
* ``CASE_SENSITIVE_COMPLETIONS``: this variable is a boolean.

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
They can be seen on the `Environment Variables page <envvars.html>`_.

.. note:: In subprocess mode, referencing an undefined environment variable
          will produce an empty string.  In Python mode, however, a
          ``KeyError`` will be raised if the variable does not exist in the
          environment.

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


Captured Subprocess with ``$()`` and ``!()``
============================================
The ``$(<expr>)`` operator in xonsh executes a subprocess command and
*captures* some information about that command.

The ``$()`` syntax captures and returns the standard output stream of the
command as a Python string.  This is similar to how ``$()`` performs in Bash.
For example,

.. code-block:: xonshcon

    >>> $(ls -l)
    'total 0\n-rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh\n'

The ``!()`` syntax captured more information about the command, as an instance
of a class called ``CompletedCommand``.  This object contains more information
about the result of the given command, including the return code, the process
id, the standard output and standard error streams, and information about how
input and output were redirected.  For example:

.. code-block:: xonshcon

    >>> !(ls nonexistent_directory)
    CompletedCommand(stdin=None, stdout='', stderr='/bin/ls: cannot access nonexistent_directory: No such file or directory\n', pid=1862, returncode=2, args=['ls', 'nonexistent_directory'], alias=['ls', '--color=auto'], stdin_redirect=None, stdout_redirect=None, stderr_redirect=None)

This object will be "truthy" if its return code was 0, and it is equal (via
``==``) to its return code.  It also hashes to its return code.  This allows
for some interesting new kinds of interactions with subprocess commands, for
example:

.. code-block:: xonshcon

    def check_file(file):
        if !(test -e @(file)):
            if !(test -f @(file)) or !(test -d @(file)):
                print("File is a regular file or directory")
            else:
                print("File is not a regular file or directory")
        else:
            print("File does not exist")

    def wait_until_google_responds():
        while not !(ping -c 1 google.com):
            sleep 1


If you iterate over the ``CompletedCommand`` object, it will yield lines of its
output.  Using this, you can quickly and cleanly process output from commands.
Additionally, these objects expose a method ``itercheck``, which behaves the same
as the built-in iterator but raises ``XonshCalledProcessError`` if the process
had a nonzero return code.

.. code-block:: xonshcon

    def get_wireless_interface():
        """Returns devicename of first connected wifi, None otherwise"""
        for line in !(nmcli device):
            dev, typ, state, conn_name = line.split(None, 3)
            if typ == 'wifi' and state == 'connected':
                return dev

    def grep_path(path, regexp):
        """Recursively greps `path` for perl `regexp`

        Returns a dict of 'matches' and 'failures'.
        Matches are files that contain the given regexp.
        Failures are files that couldn't be scanned.
        """
        matches = []
        failures = []

        try:
            for match in !(grep -RPl @(regexp) @(str(path))).itercheck():
                matches.append(match)
        except XonshCalledProcessError as error:
            for line in error.stderr.split('\n'):
                if not line.strip():
                    continue
                filename = line.split('grep: ', 1)[1].rsplit(':', 1)[0]
                failures.append(filename)
        return {'matches': matches, 'failures': failures}


The ``$()`` and ``!()`` operators are expressions themselves. This means that
we can assign the results to a variable or perform any other manipulations we
want.

.. code-block:: xonshcon

    >>> x = $(ls -l)
    >>> print(x.upper())
    TOTAL 0
    -RW-RW-R-- 1 SNAIL SNAIL 0 MAR  8 15:46 XONSH
    >>> y = !(ls -l)
    >>> print(y.returncode)
    0
    >>> print(y.rtn)  # alias to returncode
    0


.. warning:: Job control is not implemented for captured subprocesses.

While in subprocess-mode or inside of a captured subprocess, we can always
still query the environment with ``$NAME`` variables or the ``${}`` syntax,
or inject Python values with the ``@()`` operator:

.. code-block:: xonshcon

    >>> $(echo $HOME)
    '/home/snail\n'

Uncaptured Subprocess with ``$[]`` and ``![]``
===============================================
Uncaptured subprocesses are denoted with the ``$[]`` and ``![]`` operators. They are
the same as ``$()`` captured subprocesses in almost every way. The only
difference is that the subprocess's stdout passes directly through xonsh and
to the screen.  The return value of ``$[]`` is always ``None``.

In the following, we can see that the results of ``$[]`` are automatically
printed, and the return value is not a string.

.. code-block:: xonshcon

    >>> x = $[ls -l]
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh
    >>> x is None
    True

Previously when we automatically entered subprocess-mode, uncaptured
subprocesses were used.  Thus ``ls -l`` and ``$[ls -l]`` are usually
equivalent.

The ``![]`` operator is similar to the ``!()`` in that it returns an object
containing information about the result of executing the given command.
However, its standard output and standard error streams are directed to the
terminal, and the resulting object is not displayed.  For example

.. code-block:: xonshcon

    >>> x = ![ls -l] and ![echo "hi"]
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh
    hi


Python Evaluation with ``@()``
===============================

The ``@(<expr>)`` operator form works in subprocess mode, and will evaluate
arbitrary Python code. The result is appended to the subprocess command list.
If the result is a string, it is appended to the argument list. If the result
is a list or other non-string sequence, the contents are converted to strings
and appended to the argument list in order. If the result in the first position
is a function, it is treated as an alias (see the section on `Aliases`_ below),
even if it was not explicitly added to the ``aliases`` mapping.  Otherwise, the
result is automatically converted to a string. For example,

.. code-block:: xonshcon

    >>> x = 'xonsh'
    >>> y = 'party'
    >>> echo @(x + ' ' + y)
    xonsh party
    >>> echo @(2+2)
    4
    >>> echo @([42, 'yo'])
    42 yo
    >>> echo "hello" | @(lambda a, s=None: s.strip + " world")
    hello world

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

Command Substitution with ``@$()``
==================================

A common use of the ``@()`` and ``$()`` operators is allowing the output of a
command to replace the command itself (command substitution):
``@([i.strip() for i in $(cmd).split()])``.  Xonsh offers a
short-hand syntax for this operation: ``@$(cmd)``.

Consider the following example:

.. code-block:: xonshcon

    >>> # this returns a string representing stdout
    >>> $(which ls)
    'ls --color=auto\n'

    >>> # this attempts to run the command, but as one argument
    >>> # (looks for 'ls --color=auto\n' with spaces and newline)
    >>> @($(which ls).strip())
    xonsh: subprocess mode: command not found: ls --color=auto

    >>> # this actually executes the intended command
    >>> @([i.strip() for i in $(which ls).split()])
    some_file  some_other_file

    >>> # this does the same thing, but is much more concise
    >>> @$(which ls)
    some_file  some_other_file


Nesting Subprocesses
=====================================
Though I am begging you not to abuse this, it is possible to nest the
subprocess operators that we have seen so far (``$()``, ``$[]``, ``${}``,
``@()``, ``@$()``).  An instance of ``ls -l`` that is on the wrong side of the
border of the absurd is shown below:

.. code-block:: console

    >>> $[@$(which @($(echo ls).strip())) @('-' + $(printf 'l'))]
    total 0
    -rw-rw-r-- 1 snail snail 0 Mar  8 15:46 xonsh

With great power, and so forth...

.. note:: Nesting these subprocess operators inside of ``$()`` and/or ``$[]``
          works because the contents of those operators are executed in
          subprocess mode.  Since ``@()`` and ``${}`` run their contents in
          Python mode, it is not possible to nest other subprocess operators
          inside of them.

Pipes
====================

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

Logical Subprocess And
=======================

Subprocess-mode also allows you to use the ``and`` operator to chain together
subprocess commands. The truth value of a command is evaluated as whether
its return code is zero (i.e. ``proc.returncode == 0``).  Like in Python,
if the command evaluates to ``False``, subsequent commands will not be executed.
For example, suppose we want to lists files that may or may not exist:

.. code-block:: xonshcon

    >>> touch exists
    >>> ls exists and ls doesnt
    exists
    /bin/ls: cannot access doesnt: No such file or directory

However, if you list the file that doesn't exist first,
you would have only seen the error:

.. code-block:: xonshcon

    >>> ls doesnt and ls exists
    /bin/ls: cannot access doesnt: No such file or directory

Also, don't worry. Xonsh directly translates the ``&&`` operator into ``and``
for you. It is less Pythonic, of course, but it is your shell!

Logical Subprocess Or
=======================

Much like with ``and``, you can use the ``or`` operator to chain together
subprocess commands. The difference, to be certain, is that
subsequent commands will be executed only if the
if the return code is non-zero (i.e. a failure). Using the file example
from above:

.. code-block:: xonshcon

    >>> ls exists or ls doesnt
    exists

This doesn't even try to list a non-existent file!
However, if you list the file that doesn't exist first,
you will see the error and then the file that does exist:

.. code-block:: xonshcon

    >>> ls doesnt or ls exists
    /bin/ls: cannot access doesnt: No such file or directory
    exists

Never fear! Xonsh also directly translates the ``||`` operator into ``or``,
too. Your muscle memory is safe now, here with us.

Input/Output Redirection
====================================

xonsh also allows you to redirect ``stdin``, ``stdout``, and/or ``stderr``.
This allows you to control where the output of a command is sent, and where
it receives its input from.  xonsh has its own syntax for these operations,
but, for compatibility purposes, xonsh also support Bash-like syntax.

The basic operations are "write to" (``>``), "append to" (``>>``), and "read
from" (``<``).  The details of these are perhaps best explained through
examples.

Redirecting ``stdout``
----------------------

All of the following examples will execute ``COMMAND`` and write its regular
output (stdout) to a file called ``output.txt``, creating it if it does not
exist:

.. code-block:: xonshcon

    >>> COMMAND > output.txt
    >>> COMMAND out> output.txt
    >>> COMMAND o> output.txt
    >>> COMMAND 1> output.txt # included for Bash compatibility

These can be made to append to ``output.txt`` instead of overwriting its contents
by replacing ``>`` with ``>>`` (note that ``>>`` will still create the file if it
does not exist).

Redirecting ``stderr``
----------------------

All of the following examples will execute ``COMMAND`` and write its error
output (stderr) to a file called ``errors.txt``, creating it if it does not
exist:

.. code-block:: xonshcon

    >>> COMMAND err> errors.txt
    >>> COMMAND e> errors.txt
    >>> COMMAND 2> errors.txt # included for Bash compatibility

As above, replacing ``>`` with ``>>`` will cause the error output to be
appended to ``errors.txt``, rather than replacing its contents.

Combining Streams
----------------------

It is possible to send all of ``COMMAND``'s output (both regular output and
error output) to the same location.  All of the following examples accomplish
that task:

.. code-block:: xonshcon

    >>> COMMAND all> combined.txt
    >>> COMMAND a> combined.txt
    >>> COMMAND &> combined.txt # included for Bash compatibility

It is also possible to explicitly merge stderr into stdout so that error
messages are reported to the same location as regular output.  You can do this
with the following syntax:

.. code-block:: xonshcon

    >>> COMMAND err>out
    >>> COMMAND err>o
    >>> COMMAND e>out
    >>> COMMAND e>o
    >>> COMMAND 2>&1 # included for Bash compatibility

This merge can be combined with other redirections, including pipes (see the
section on `Pipes`_ above):

.. code-block:: xonshcon

    >>> COMMAND err>out | COMMAND2
    >>> COMMAND e>o > combined.txt

It is worth noting that this last example is equivalent to: ``COMMAND a> combined.txt``

Redirecting ``stdin``
---------------------

It is also possible to have a command read its input from a file, rather
than from ``stdin``.  The following examples demonstrate two ways to accomplish this:

.. code-block:: xonshcon

    >>> COMMAND < input.txt
    >>> < input.txt COMMAND

Combining I/O Redirects
------------------------

It is worth noting that all of these redirections can be combined.  Below is
one example of a complicated redirect.

.. code-block:: xonshcon

    >>> COMMAND1 e>o < input.txt | COMMAND2 > output.txt e>> errors.txt

This line will run ``COMMAND1`` with the contents of ``input.txt`` fed in on
stdin, and will pipe all output (stdout and stderr) to ``COMMAND2``; the
regular output of this command will be redirected to ``output.txt``, and the
error output will be appended to ``errors.txt``.


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
to the foreground. Additionally, specify "+" for the most recent job and "-"
for the second most recent job.

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

By default, the name of an environment variable inside a string will be
replaced by the contents of that variable (in subprocess mode only).  For
example:

.. code-block:: xonshcon

    >>> print("my home is $HOME")
    my home is $HOME
    >>> echo "my home is $HOME"
    my home is /home/snail

You can avoid this expansion within a particular command by forcing the strings
to be evaluated in Python mode using the ``@()`` syntax:

.. code-block:: xonshcon

    >>> echo "my home is $HOME"
    my home is /home/snail
    >>> echo @("my home is $HOME")
    my home is $HOME

You can also disable environment variable expansion completely by setting
``$EXPAND_ENV_VARS`` to ``False``.

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

This is not available in Python-mode because multiplication is pretty
important.


Advanced Path Search with Backticks
===================================

xonsh offers additional ways to find path names beyond regular globbing, both
in Python mode and in subprocess mode.

Regular Expression Globbing
---------------------------

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

This same kind of search is performed if the backticks are prefaced with ``r``.
So the following expresions are equivalent: ```test``` and ``r`test```.

Other than the regex matching, this functions in the same way as normal
globbing.  For more information, please see the documentation for the ``re``
module in the Python standard library.

.. warning:: This backtick syntax has very different from that of Bash.  In
             Bash, backticks mean to run a captured subprocess ``$()``.


Normal Globbing
---------------

In subprocess mode, normal globbing happens without any special syntax.
However, the backtick syntax has an additional feature: it is available inside
of Python mode as well as subprocess mode.

Similarly to regex globbing, normal globbing can be performed (either in Python
mode or subprocess mode) by using the ``g````:

.. code-block:: xonshcon

    >>> touch a aa aaa aba abba aab aabb abcba
    >>> ls a*b*
    aab  aabb  aba  abba  abcba
    >>> ls g`a*b*`
    aab  aabb  aba  abba  abcba
    >>> print(g`a*b*`)
    ['aab', 'aabb', 'abba', 'abcba', 'aba']
    >>> len(g`a*b*`)
    5


Custom Path Searches
--------------------

In addition, if normal globbing and regular expression globbing are not enough,
xonsh allows you to specify your own search functions.

A search function is defined as a function of a single argument (a string) that
returns a list of possible matches to that string.  Search functions can then
be used with backticks with the following syntax: ``@<name>`test```

The following example shows the form of these functions:

.. code-block:: xonshcon

    >>> def foo(s):
    ...     return [i for i in os.listdir('.') if i.startswith(s)]
    >>> @foo`aa`
    ['aa', 'aaa', 'aab', 'aabb']


Help & Superhelp with ``?`` & ``??``
=====================================================
From IPython, xonsh allows you to inspect objects with question marks.
A single question mark (``?``) is used to display the normal level of help.
Double question marks (``??``) are used to display a higher level of help,
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
Like Python and Bash, xonsh provides built-in hooks to compile, evaluate,
and execute strings of xonsh code.  To prevent this functionality from having
serious name collisions with the Python built-in ``compile()``, ``eval()``,
and ``exec()`` functions, the xonsh equivalents all append an 'x'.  So for
xonsh code you want to use the ``compilex()``, ``evalx()``, and ``execx()``
functions. If you don't know what these do, you probably don't need them.


Aliases
==============================
Another important xonsh built-in is the ``aliases`` mapping.  This is
like a dictionary that affects how subprocess commands are run.  If you are
familiar with the Bash ``alias`` built-in, this is similar.  Alias command
matching only occurs for the first element of a subprocess command.

The keys of ``aliases`` are strings that act as commands in subprocess-mode.
The values are lists of strings, where the first element is the command, and
the rest are the arguments. You can also set the value to a string, in which
case it will be converted to a list automatically with ``shlex.split``.

For example, the following creates several aliases for the ``git``
version control software.  Both styles (list of strings and single
string) are shown:

.. code-block:: xonshcon

    >>> aliases['g'] = 'git status -sb'
    >>> aliases['gco'] = 'git checkout'
    >>> aliases['gp'] = ['git', 'pull']

If you were to run ``gco feature-fabulous`` with the above aliases in effect,
the command would reduce to ``['git', 'checkout', 'feature-fabulous']`` before
being executed.


Callable Aliases
----------------
Lastly, if an alias value is a function (or other callable), then this
function is called *instead* of going to a subprocess command. Such functions
must have one of the following two signatures

.. code-block:: python

    def _mycmd(args, stdin=None):
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
        import builtins
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

        # Lastly, a 3-tuple return value can be used to include an integer
        # return code indicating failure (> 0 return code). In the previous
        # examples the return code would be 0/success.
        return (None, "I failed", 2)


.. code-block:: python

    def _mycmd2(args, stdin, stdout, stderr):
        """args will be a list of strings representing the arguments to this
        command.  stdin is a read-only file-like object, and stdout and stderr
        are write-only file-like objects
        """
        # This form allows "streaming" data to stdout and stderr
        import time
        for i in range(5):
            time.sleep(i)
            print(i, file=stdout)

        # In this form, the return value should be a single integer
        # representing the "return code" of the alias (zero if successful,
        # non-zero otherwise)
        return 0


Adding and Removing Aliases
---------------------------
We can dynamically alter the aliases present simply by modifying the
built-in mapping.  Here is an example using a function value:

.. code-block:: xonshcon

    >>> def _banana(args, stdin=None):
    ...     return ('My spoon is tooo big!', None)
    >>> aliases['banana'] = _banana
    >>> banana
    'My spoon is tooo big!'

.. note::

   Alias functions should generally be defined with a leading underscore.
   Otherwise, they may shadow the alias itself, as Python variables take
   precedence over aliases when xonsh executes commands.


Anonymous Aliases
-----------------
As mentioned above, it is also possible to treat functions outside this mapping
as aliases, by wrapping them in ``@()``.  For example:

.. code-block:: xonshcon

    >>> @(_banana)
    'My spoon is tooo big!'
    >>> echo "hello" | @(lambda args, stdin=None: stdin.strip() + args[0]) world
    hello world


Foreground-only Aliases
-----------------------
Usually, callable alias commands will be run in a separate thread so that users
they may be run in the background.  However, some aliases may need to be
executed on the thread that they were called from. This is mostly useful for
debuggers and profilers. To make an alias run in the foreground, decorate its
function with the ``xonsh.proc.foreground`` decorator.

.. code-block:: python

    from xonsh.proc import foreground

    @foreground
    def _mycmd(args, stdin=None):
        return 'In your face!'

    aliases['mycmd'] = _mycmd

Aliasing is a powerful way that xonsh allows you to seamlessly interact to
with Python and subprocess.

Up, Down, Tab
==============
The up and down keys search history matching from the start of the line,
much like they do in the IPython shell.

Tab completion is present as well. By default, in Python-mode you are able to
complete based on the variable names in the current builtins, globals, and
locals, as well as xonsh languages keywords & operator, files & directories,
and environment variable names. In subprocess-mode, you additionally complete
on the names of executable files on your ``$PATH``, alias keys, and full Bash
completion for the commands themselves.

xonsh also provides a means of modifying the behavior of the tab completer.  More
detail is available on the `Tab Completion page <tutorial_completers.html>`_.

Customizing the Prompt
======================
Customizing the prompt by modifying ``$PROMPT`` is probably the most common
reason for altering an environment variable.

.. note:: Note that the ``$PROMPT`` variable will never be inherited from a
          parent process (regardless of whether that parent is a foreign shell
          or an instance of xonsh).

The ``$PROMPT`` variable can be a string, or it can be a function (of no
arguments) that returns a string.  The result can contain keyword arguments,
which will be replaced automatically:

.. code-block:: xonshcon

    >>> $PROMPT = '{user}@{hostname}:{cwd} > '
    snail@home:~ > # it works!
    snail@home:~ > $PROMPT = lambda: '{user}@{hostname}:{cwd} >> '
    snail@home:~ >> # so does that!

By default, the following variables are available for use:

  * ``user``: The username of the current user
  * ``hostname``: The name of the host computer
  * ``cwd``: The current working directory, you may use ``$DYNAMIC_CWD_WIDTH`` to
    set a maximum width for this variable.
  * ``short_cwd``: A shortened form of the current working directory; e.g.,
    ``/path/to/xonsh`` becomes ``/p/t/xonsh``
  * ``cwd_dir``: The dirname of the current working directory, e.g. ``/path/to`` in
    ``/path/to/xonsh``.
  * ``cwd_base``: The basename of the current working directory, e.g. ``xonsh`` in
    ``/path/to/xonsh``.
  * ``curr_branch``: The name of the current git branch (preceded by space),
    if any.
  * ``branch_color``: ``{BOLD_GREEN}`` if the current git branch is clean,
    otherwise ``{BOLD_RED}``. This is yellow if the branch color could not be
    determined.
  * ``branch_bg_color``: Like, ``{branch_color}``, but sets a background color
    instead.
  * ``prompt_end``: `#` if the user has root/admin permissions `$` otherwise
  * ``current_job``: The name of the command currently running in the
    foreground, if any.

You can also color your prompt easily by inserting keywords such as ``{GREEN}``
or ``{BOLD_BLUE}``.  Colors have the form shown below:

* ``NO_COLOR``: Resets any previously used color codes
* ``COLORNAME``: Inserts a color code for the following basic colors,
  which come in regular (dark) and intense (light) forms:

    - ``BLACK`` or ``INTENSE_BLACK``
    - ``RED`` or ``INTENSE_RED``
    - ``GREEN`` or ``INTENSE_GREEN``
    - ``YELLOW`` or ``INTENSE_YELLOW``
    - ``BLUE`` or ``INTENSE_BLUE``
    - ``PURPLE`` or ``INTENSE_PURPLE``
    - ``CYAN`` or ``INTENSE_CYAN``
    - ``WHITE`` or ``INTENSE_WHITE``

* ``#HEX``: A ``#`` before a len-3 or len-6 hex code will use that
  hex color, or the nearest approximation that that is supported by
  the shell and terminal.  For example, ``#fff`` and ``#fafad2`` are
  both valid.
* ``BACKGROUND_`` may be added to the begining of a color name or hex
  color to set a background color.  For example, ``BACKGROUND_INTENSE_RED``
  and ``BACKGROUND_#123456`` can both be used.
* ``bg#HEX`` or ``BG#HEX`` are shortcuts for setting a background hex color.
  Thus you can set ``bg#0012ab`` or the uppercase version.
* ``BOLD_`` is a prefix qualifier that may be used with any foreground color.
  For example, ``BOLD_RED`` and ``BOLD_#112233`` are OK!
* ``UNDERLINE_`` is a prefix qualifier that also may be used with any
  foreground color. For example, ``UNDERLINE_GREEN``.
* Or any other combination of qualifiers, such as
  ``BOLD_UNDERLINE_INTENSE_BLACK``,   which is the most metal color you
  can use!

You can make use of additional variables beyond these by adding them to the
``FORMATTER_DICT`` environment variable.  The values in this dictionary
should be strings (which will be inserted into the prompt verbatim), or
functions of no arguments (which will be called each time the prompt is
generated, and the results of those calls will be inserted into the prompt).
For example:

.. code-block:: console

    snail@home ~ $ $FORMATTER_DICT['test'] = "hey"
    snail@home ~ $ $PROMPT = "{test} {cwd} $ "
    hey ~ $
    hey ~ $ import random
    hey ~ $ $FORMATTER_DICT['test'] = lambda: random.randint(1,9)
    3 ~ $
    5 ~ $
    2 ~ $
    8 ~ $

If a function in ``$FORMATTER_DICT`` returns ``None``, the ``None`` will be
interpreted as an empty string.

Environment variables and functions are also available with the ``$``
prefix.  For example:

.. code-block:: console

    snail@home ~ $ $PROMPT = "{$LANG} >"
    en_US.utf8 >

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
        echo @(x) > @("file{0}.txt".format(i))

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
        echo @(x) > @("file{0}.txt".format(i))

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

Additionally, if the script should exit if a command fails, set the
environment variable ``$RAISE_SUBPROC_ERROR = True`` at the top of the
file. Errors in Python mode will already raise exceptions and so this
is roughly equivalent to Bash's ``set -e``.

Furthermore, you can also toggle the ability to print source code lines with the
``trace on`` and ``trace off`` commands.  This is roughly equivelent to
Bash's ``set -x`` or Python's ``python -m trace``, but you know, better.

Importing Xonsh (``*.xsh``)
==============================
You can import xonsh source files with the ``*.xsh`` file extension using
the normal Python syntax.  Say you had a file called ``mine.xsh``, you could,
therefore, perform a Bash-like source into your current shell with the
following:

.. code-block:: xonsh

    from mine import *


That's All, Folks
======================
To leave xonsh, hit ``Ctrl-D``, type ``EOF``, type ``quit``, or type ``exit``.
On Windows, you can also type ``Ctrl-Z``.

.. code-block:: xonshcon

    >>> exit

Now it is your turn.
