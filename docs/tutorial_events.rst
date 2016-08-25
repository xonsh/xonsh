.. _tutorial_events:

************************************
Tutorial: Events
************************************
What's the best way to keep informed in xonsh? Subscribe to an event!

Overview
========
Simply, events are a way for xonsh to .... do something.


Show me the code!
=================
Fine, fine!

This will add a line to a file every time the current directory changes (due to ``cd``, ``pushd``,
or several other commands).

    @events.on_chdir
    def add_to_file(newdir):
        with open(g`~/.dirhist`[0], 'a') as dh:
            print(newdir, file=dh)

Core Events
===========

* ``on_precommand``
* ``on_postcommand``
* ``on_chdir``
