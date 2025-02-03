.. _tutorial_hist:

************************************
Tutorial: History
************************************
Import your best Leonard Nimoy documentary voice and get ready for the xonsh tutorial
on ``history``.

How is xonsh history different?
================================
Most shells - bash foremost among them - think of history as a linear sequence of
past commands that have been entered into *the* terminal. This is saved when *the*
shell exits, and loaded when *the* new shell starts. But this is no longer
how the world works.

The world is a messy, asynchronous place. We usually have at least as many terminals
(and shells) open at a time as we can practically handle - and probably even more!
In xonsh, history acknowledges that this is the case. Instead of a single history
file of inputs, xonsh implements a collection of JSON-formatted history files that
can be thought of as having the following structure:

.. code-block:: python

    {'env': {...},  # Environment that xonsh was started with
     'sessionid': str, # UUID4 for the session
     'ts': [start, stop],  # start and stop timestamps for session [s since epoch]
     'locked': True,  # boolean for whether the file is in use or not
     'cmds': [  # array of commands
        {'inp': str,  # input command
         'ts': [start, stop],  # timestamps for the command
         'rtn': int, # command return code
         'out' str,  # stdout and stderr of command, for subproc commands
                     # this is only available select OSs. Off by default.
         },
        ...
        ],
    }

This rich set of data allows xonsh to do much more advanced inspection and manipulation.
The sessionid, locking, and one-file-per-shell ideas allow for there to be multiple
instances of xonsh running at the same time without competing and overwriting
history constantly. Of course, an external process deleting a history file can still
cause problems. But hey, the world and the file system are messy places to be!


Why have rich history?
=======================
Often by the time you know that you need a historical artifact, it is already too
late. You can't remember:

* the input exactly,
* you think that you remember the output but when you rerun the command what you get
  now seems somehow different,
* who knows what the return code was,
* and whatever command you ran right before is now lost in the mists of time!

So the reasons for having rich history are debugging and reproducibility. Xonsh takes the
guess-work out of the past. There is even the ability to store all of stdout, though this
is turned off by default.
If history was just a static file, it would be more like a server log than a traditional
history file.


``history`` command
====================
All xonsh history inspection and manipulation goes through the top-level ``history``
alias or command.  If you run this without an ``action`` argument, it will default to
the ``show`` action, see below.

.. code-block:: xonshcon

    >>> history

Also note that the history object itself can be accessed through the xonsh built-in variable
``__xonsh__.history``.


``show`` action
================
The ``show`` action for the history command mimics what the ``history`` command does
in other shells.  Namely, it displays the past inputs along with the index of these
inputs. This operates on the current session by default and is the default action for
the ``history`` command. For example,

.. code-block:: xonshcon

    >>> 1 + 1
    2
    >>> history show
     0  1 + 1
    >>> history
     0  1 + 1
     1  history show


.. note:: History is zero-indexed; this is still Python.

The show command can also optionally take as an argument any integer (to just display
that history index) or a slice (to display a range of history indices). To display
only the even indices from above, you could write:

.. code-block:: xonshcon

    >>> history show ::2
     0  1 + 1
     2  history

One can also use many slice/integer arguments to get different portions of history

After ``show`` an option that indicates which history to be returned can be used:

``xonsh`` displays the past inputs from all
valid json files found in ``XONSH_DATA_DIR``. As such, this operates on all
past and present xonsh sessions.

``all`` is an alias for ``xonsh``.

``zsh`` will display all history from the history file specified
by the ``HISTFILE`` environmental variable in zsh.
By default this is ``~/.zsh_history``. However, they can also be respectively
specified in both ``~/.zshrc`` and ``~/.zprofile``. Xonsh will parse these files
(rc file first) to check if ``HISTFILE`` has been set.

The ``bash`` action will display all history from the history file specified
by the ``HISTFILE`` environmental variable in bash.
By default this is ``~/.bash_history``. However, they can also be respectively
specified in both ``~/.bashrc`` and ``~/.bash_profile``. Xonsh will parse these
files (rc file first) to check if ``HISTFILE`` has been set.


``show`` also accepts other options for more control over history output,
the ``-n`` option is used to enumerate the commands,
the ``-t`` option is used to show the timestamps,
and more, try out ``history show --help`` for a list of options.


``id`` action
================
Each xonsh history has its own universally unique ``sessionid``. The ``id`` action is how you
display this identified. For instance,

.. code-block:: xonshcon

    >>> history id
    ace97177-f8dd-4a8d-8a91-a98ffd0b3d17

``file`` action
================
Similarly, each xonsh history has its own file associated with it. The ``file`` action is
how you display the path to this file. For example,

.. code-block:: xonshcon

    >>> history file
    /home/me/.local/share/xonsh/xonsh-ace97177-f8dd-4a8d-8a91-a98ffd0b3d17.json

Note that by these files are stored in ``$XONSH_DATA_DIR`` environment variable. This
is, by default, set to the ``xonsh`` dir inside of the free desktop standards
``$XDG_DATA_HOME`` environment variable. See
`this page <http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html>`_ for
more details.

``info`` action
===============
The info action combines the ``id`` and ``file`` actions as well as adds some additional
information about the current state of the history. By default, this prints a key-value
series of lines. However, it can also return a JSON formatted string.

.. code-block:: xonshcon

    >>> history info
    sessionid: ace97177-f8dd-4a8d-8a91-a98ffd0b3d17
    filename: /home/scopatz/.local/share/xonsh/xonsh-ace97177-f8dd-4a8d-8a91-a98ffd0b3d17.json
    length: 6
    buffersize: 100
    bufferlength: 6

.. code-block:: xonshcon

    >>> history info --json
    {"sessionid": "ace97177-f8dd-4a8d-8a91-a98ffd0b3d17",
     "filename": "/home/scopatz/.local/share/xonsh/xonsh-ace97177-f8dd-4a8d-8a91-a98ffd0b3d17.json",
     "length": 7, "buffersize": 100, "bufferlength": 7}


``diff`` action
===============
Between any two history files, we can run the ``diff`` action. This does more that a simple line
diff that you might generate with the unix ``diff`` command. (If you want a line diff, just
use the unix command!) Instead this takes advantage of the fact that we know we have xonsh
history files to do a more sophisticated diff on the environment, input, output (if available),
and return values.  Of course, the histories inputs should be 'sufficiently similar' if the diff
is to be meaningful. However, they don't need to be exactly the same.

The diff action has one major option, ``-v`` or ``--verbose``. This basically says whether the
diff should go into as much detail as possible or only pick out the relevant pieces. Diffing
the new and next examples, we see the diff looks like:

.. code-block:: xonshcon

    >>> history diff ~/new.json ~/next.json
    --- /home/scopatz/new.json (35712b6f-4b15-4ef9-8ce3-b4c781601bc2) [unlocked]
    started: 2015-08-27 15:13:44.873869 stopped: 2015-08-27 15:13:44.918903 runtime: 0:00:00.045034
    +++ /home/scopatz/next.json (70d7186e-3eb9-4b1c-8f82-45bb8a1b7967) [unlocked]
    started: 2015-08-27 15:15:09.423932 stopped: 2015-08-27 15:15:09.619098 runtime: 0:00:00.195166

    Environment
    -----------
    'PATH' is in both, but differs
    - /home/scopatz/.local/bin:/home/scopatz/sandbox/bin:/home/scopatz/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/home/scopatz/origen22/code/
    + /home/scopatz/.local/bin:/home/scopatz/sandbox/bin:/home/scopatz/miniconda3/bin:/home/scopatz/.local/bin:/home/scopatz/sandbox/bin:/home/scopatz/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/home/scopatz/origen22/code/:/home/scopatz/origen22/code/

    'SHLVL' is in both, but differs
    - 2
    + 3

    'XONSH_INTERACTIVE' is in both, but differs
    - True
    + False

    These vars are only in 70d7186e-3eb9-4b1c-8f82-45bb8a1b7967: {'OLDPWD'}

    Commands
    --------
    cmd #4 in 35712b6f-4b15-4ef9-8ce3-b4c781601bc2 input is the same as
    cmd #4 in 70d7186e-3eb9-4b1c-8f82-45bb8a1b7967, but output differs:
    Outputs differ
    - 2  10
    + 2  7  10

    cmd #5 in 35712b6f-4b15-4ef9-8ce3-b4c781601bc2 input is the same as
    cmd #5 in 70d7186e-3eb9-4b1c-8f82-45bb8a1b7967, but output differs:
    Outputs differ
    - /home/scopatz/new.json
    + /home/scopatz/next.json

As can be seen, the diff has three sections.

1. **The header** describes the meta-information about the histories, such as
   their file names, sessionids, and time stamps.
2. **The environment** section describes the differences in the environment
   when the histories were started.
3. **The commands** list this differences in the command themselves.

For the commands, the input sequences are diff'd first, prior to the outputs
being compared. In a terminal, this will appear in color, with the first history
in red and the second one in green.

``flush`` action
================
Normally, the history entries are kept in memory and are only saved to disk once
the in-memory buffer gets full. This is in order to reduce unnecessary I/O and to
keep session history free from noise from other sessions. Sometimes, however, it
may be useful to share entries between shell sessions. In such a case, one can use
the ``flush`` action to immediately save the session history to disk and make it
accessible from other shell sessions.

``pull`` action
================
Tries to pull the history from parallel sessions and add to the current session.

For example if there are two parallel terminal windows the run of ``history pull``
command from the second terminal window will get the commands from the first terminal.

The optional `--session-id` allows you to specify that history should only be pulled
from a specific other session. Most useful when using the JSON history backend, as
the overhead of an unfiltered `pull` can be significantly higher.

``clear`` action
================
Deletes the history from the current session up until this point. Later commands
will still be saved.

``off`` action
================
Deletes the history from the current session and turns off history saving for the
rest of the session. Only session metadata will be saved, not commands or output.

``on`` action
================
Turns history saving back on. Previous commands won't be saved, but future
commands will be.

``gc`` action
===============
Last, but certainly not least, the ``gc`` action is a manual hook into executing
history garbage control. Since history has the potential for a lot of information
to be stored, it is necessary to be able to clean out the cache every once in a
while.

Garbage control is launched automatically for every xonsh thread, but runs in the
a background thread. The garbage collector only operates on unlocked history files.
The action here allows you to manually start a new garbage collector, possibly with
different criteria.

Normally, the garbage collector uses the environment variable ``$XONSH_HISTORY_SIZE``
to determine the size and units of what should be allowed to remain on disk. By default,
this is ``(8128, 'commands')``. This variable is usually a tuple or list of a
number and a string, as seen here.  However, you can also use a string with the same
information, e.g. ``'8128 commands'``.  On the command line, though, you just pass in
two arguments to the ``--size`` option, a la ``--size 8128 commands``.

The garbage collector accepts four canonical units:

1. ``'commands'`` is for limiting the number of past commands executed in the
    history files,
2. ``'files'`` is for specifying the total number of history files to keep,
3. ``'s'`` is for the number of seconds in the past that are allowed - which
   is effectively a timeout of the history files, and
4. ``'b'`` is for the number of bytes that are allowed on the file system
   for all history files to collectively consume.

However, other units, aliases, and appropriate conversion functions have been implemented.
This makes it easier to garbage collect based on human-friendly values.

**GC Aliases:**

.. code-block:: python

    {'commands': ['', 'c', 'cmd', 'cmds', 'command'],
     'files': ['f'],
     's': ['sec', 'second', 'seconds', 'm', 'min', 'mins', 'h', 'hr', 'hour', 'hours',
           'd', 'day', 'days', 'mon', 'month', 'months', 'y', 'yr', 'yrs', 'year', 'years'],
     'b': ['byte', 'bytes', 'kb', 'kilobyte', 'kilobytes', 'mb', 'meg', 'megs', 'megabyte',
           'megabytes', 'gb', 'gig', 'gigs', 'gigabyte', 'gigabytes', 'tb', 'terabyte',
           'terabytes']
     }

So all said and done, if you wanted to remove all history files older than a month,
you could run the following command:

.. code-block:: xonshcon

    >>> history gc --size 1 month


History Indexing
=======================
History object (``__xonsh__.history``) acts like a sequence that can be indexed in a special way
that adds extra functionality. At the moment only history from the
current session can be retrieved. Note that the most recent command
is the last item in history.

The index acts as a filter with two parts, command and argument,
separated by comma. Based on the type of each part different
filtering can be achieved,

for the command part:
    - an int returns the command in that position.
    - a slice returns a list of commands.

for the argument part:
    - an int returns the argument of the command in that position.
    - a slice returns a part of the command based on the argument
      position.

The argument part of the filter can be omitted but the command part is
required.

Command arguments are separated by white space.

If the filtering produces only one result it is
returned as a string else a list of strings is returned.

examples:

.. code-block:: xonshcon

    >>> echo mkdir with/a/huge/name/
    mkdir with/a/huge/name
    >>> __xonsh__.history[-1, -1]
    'with/a/huge/name/'
    >>> __xonsh__.history[0, 1:]
    'mkdir with/a/huge/name'


Exciting Technical Detail: Lazy JSON
=====================================
So now you know how to inspect, run, and remove history. But what *is* a history file exactly?
While xonsh history files are JSON formatted, and they do have the structure indicated at the
top of the page, that isn't their top-level structure.  If you open one up, you'll see a bunch
of hocus pocus before you get to anything real.

Xonsh has implemented a generic indexing system (sizes, offsets, etc)for JSON files that lives
inside of the file that it indexes.  This is known as ``LazyJSON`` because it allows us to
only read in the parts of a file that we need. For garbage collecting based on the number
of commands, we can get this information from the index and don't need to read in any of the
original data.

The best part about this is that it is totally generic. Feel free to use ``xonsh.lazyjson``
yourself for things other than xonsh history! Of course, if you want to read in xonsh history,
you should probably use the module.


Exciting Technical Detail: Teeing and Pseudo Terminals
========================================================
Xonsh is able to capture all stdout and stderr transparently and responsively. For aliases,
Python code, or xonsh code, this isn't a big deal. It is easy to redirect information
flowing through ``sys.stdout`` and ``sys.stderr``.  For subprocess commands, this is
considerably harder. Capturing stdout during the session is disabled by default but can be
enabled by setting ``$XONSH_CAPTURE_ALWAYS=True``. Storing stdout to the history backend
is disabled by default but can be enabled by setting ``$XONSH_STORE_STDOUT=True``.

To be able to tee stdout and stderr and still have the terminal responsive, xonsh implements
its own teeing pseudo-terminal on top of the Python standard library ``pty`` module. You
can find this class in the ``xonsh.teepty`` module. Like with lazy JSON, this is independent
from other parts of xonsh and can be used on its own.  If you find this useful in other areas,
please let us know!


Sqlite History Backend
======================

Xonsh has a second built-in history backend powered by sqlite (other than
the JSON version mentioned all above in this tutorial). It shares the same
functionality as the JSON version in most ways, except it currently doesn't
support the ``history diff`` action and does not store the output of commands,
as the json-backend does. E.g.
`__xonsh__.history[-1].out` will always be `None`.

The Sqlite history backend can provide a speed advantage in loading history
into a just-started xonsh session. The JSON history backend may need to read
potentially thousands of json files and the sqlite backend only reads one.
Note that this does not affect startup time, but the amount of time before
all history is available for searching.

To use sqlite history backend, set ``$XONSH_HISTORY_BACKEND = 'sqlite'`` in
your ``~/.xonshrc`` file. To switch back to JSON version, remove this line,
or set it to ``'json'``.

.. note:: SQLite history backend currently only supports ``commands`` as
    the unit in ``$XONSH_HISTORY_SIZE`` in its garbage collection.

.. tip:: If you have `sqlite-web <https://pypi.python.org/pypi/sqlite-web>`_
    installed, you can read the history easily with command:
    ``sqlite_web @$(history file)``.


Fun ideas for history data
==========================
Now that we have all of this history data, it seems like what we have here is just the tip
of the iceberg! Here are some hopefully fun ideas that I think would be great to see
implemented:

* Basic statistic reports about command usage, timing, etc.,
* Global statistics by collecting anonymized histories from many people,
* MCMC-based tab-completer for inputs,
* and many more!

Let us know if you'd be interested in working on any of these, inside or outside of xonsh.
