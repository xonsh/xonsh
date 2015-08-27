.. _tutorial_hist:

**********************************
Tutorial [Advanced]: Livng History
**********************************
Import your best Leonard Nimoy documentary voice and get ready for the xonsh tutorial 
on ``history``.

How is xonsh history different?
================================
Most shells - bash foremost among them - think of history as a linear sequence of 
past commands that have been entered into *the* terminal. This is saved when *the*
shell exits, and loaded when *the* new shell starts. But this is not longer
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
                     # this is only available on Linux. Off by default.
         }, 
        ...
        ],
    }

This rich set of data allows xonsh to do much more advanced inspection and manipution.
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
history file.  However, xonsh also has the ability to ``replay`` a history file. 

Replaying history allows previous sessions to act as scripts in a new or the same enviornment.
Replaying will create a new, separate history session and file. The two histories - even though
they contain the same inputs - are then able to be diff'ed. Diff'ing can be done through 
xonsh custom history diff'ing tool, which can help pinpoint differences stemming from the 
enviroment as well as the input/output.  This cycle of do-replay-diff is more meaningful than
a traditional, "What did I/it/the Universe just do?!" approach.

Of course, nothing has ever stopped anyone from pulling unix tools like ``env``, ``script``, 
``diff``, and others together to deliver the same kind of capability. However, in practice, 
no one does this. With xonsh, rich and useful history come batteries included.

``history`` command
====================
All xonsh history inspection and manipulation goes the the top-level ``history`` alias or 
command.  If you run this without an ``action`` argument, it will default to the ``show``
action, see below.

.. code-block:: xonshcon

    >>> history

Also note that the history object itself can be accessed through the xonsh builtin variable
``__xonsh_history__``.


``show`` action
================
The ``show`` action for the history command mimics what the ``history`` command does
in other shells.  Namely, it displays the past inputs along with the index of these 
inputs. This operates on the current session only and is the default action for 
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

In the future, ``show`` may also be used to display outputs, return values, and time stamps.
But the default behavior will remain as shown here.

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
The info action combines the ``id`` and ``file`` actions as well as adds some aditional
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

``replay`` action
==================
The ``replay`` action allows for history files to be rerun, as scripts or in an existing xonsh 
session.

First, the original ``'replay'`` environment is loaded and will be merged with the current ``'native'`` 
environment. How the environments are merged or not merged can be set at replay time. The default is for 
the current native environment to take precendence. Next, each input in the environment is executed in order. 
Lastly, the information of the replayed history file is printed.

Let's walk through an example. To begin with, open up xonsh and run some simple commands, as follows.
Call this the ``orig`` session.

**orig history**

.. code-block:: xonshcon

    >>> mkdir -p temp/
    >>> cd temp
    >>> import random
    >>> touch @(random.randint(0, 18))
    >>> ls
    2
    >>> history file
    /home/scopatz/.local/share/xonsh/xonsh-4bc4ecd6-3eba-4f3a-b396-a229ba2b4810.json
    >>> exit

We can now replay this by passing the filename into the replay command or the replay action 
of the history command. This action has a few different options, but one of them is that 
we can select a different target output file with the ``-o`` or ``--target`` option. 
For example, in a new session, we could run:

**new history**

.. code-block:: xonshcon

    >>> history replay -o ~/new.json ~/.local/share/xonsh/xonsh-4bc4ecd6-3eba-4f3a-b396-a229ba2b4810.json
    2  10
    /home/scopatz/new.json

    ------------------------------------------------------------
    Just replayed history, new history has following information
    ------------------------------------------------------------
    sessionid: 35712b6f-4b15-4ef9-8ce3-b4c781601bc2
    filename: /home/scopatz/new.json
    length: 7
    buffersize: 100
    bufferlength: 0

As you can see, a new history was created and another random file was added to the file system.
If we want instead to replay history in its own session, we can always use the ``-c`` option on 
xonsh itself to execute the replay command.

**next history**

.. code-block:: xonshcon

    >>> xonsh -c "replay -o ~/next.json ~/new.json"
    2  7  10
    /home/scopatz/next.json

    ------------------------------------------------------------
    Just replayed history, new history has following information
    ------------------------------------------------------------
    sessionid: 70d7186e-3eb9-4b1c-8f82-45bb8a1b7967
    filename: /home/scopatz/next.json
    length: 7
    buffersize: 100
    bufferlength: 0


Currently history does not handle alias storage and reloading, but such a feature may be coming in 
the future.

``diff`` action
===============
Between any two history files, we can run the ``diff`` action. This does more that a simple line
diff that you might generate with the unix ``diff`` command. (If you want a line diff, just 
use the unix command!) Instead this takes advantage of the fact that we know we have xonsh 
history files to do a more sophistcated diff on the environment, input, output (if available), 
and return values.  Of course, the histories inputs should be 'sufficiently similar' if the diff 
is to be meaningful. However, they don't need to be exactly the same.

The diff action has one major option, ``-v`` or ``--verbose``. This basically says whether the 
diff should go into as much detail as possible or only pick out the relevant peices. Diffing
the new and next examples from the replay action, we see the diff looks like:

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

As can be seen, the diff has three secions.  

1. **The header** descibes the meta-information about the histories, such as 
   their file names, sessionids, and time stamps.
2. **The environment** section describes the differences in the environment 
   when the histories were started or replayed.
3. **The commands** list this differences in the command themselves. 

For the commands, the input sequences are diff'd first, prior to the outputs
being compared. In a terminal, this will appear in color, with the first history
in red and the second one in green.

Exciting Techinical Detail: Lazy JSON
=====================================
woo

Exciting Techinical Detail: Teeing and Psuedo Terminals
========================================================
OMG

Fun ideas for history data
==========================
xxx
