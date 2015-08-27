.. _tutorial_hist:

**********************************
Tutorial [Advanced]: Livng History
**********************************
Import your best Leonard Nimoy documenray voice and get ready for the xonsh tutorial 
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



Reproducibility and Debugging.
y


``show`` command
================
show

.. code-block:: xonshcon

    >>> 1 + 1
    2


Exciting Techinical Detail: Lazy JSON
=====================================
woo

Exciting Techinical Detail: Teeing and Psuedo Terminals
========================================================
OMG

Fun ideas for history data
==========================
xxx