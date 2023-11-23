Core Events
===========
The following events are defined by xonsh itself. For more information about events,
see `the events tutorial <tutorial_events.html>`_.

.. include:: eventsbody


Event Categories
----------------
Additionally, there are a few categories of events whose names are part of
the specification of the event. These events are fired if they exist, and
are ignored otherwise. Here are their specifications.

-------

``on_pre_spec_run(spec: SubprocSpec) -> None``
.........................................................
This event fires whenever any command has its ``SubprocSpec.run()``
method called.  This is fired prior to the run call executing anything
at all. This receives the ``SubprocSpec`` object as ``spec`` that triggered
the event, allowing the handler to modify the spec if needed.  For example,
if we wanted to intercept all specs, we could write:

.. code-block:: python

    @events.on_pre_spec_run
    def print_when_ls(spec=None, **kwargs):
        print("Running a command")


``on_pre_spec_run_<cmd-name>(spec: SubprocSpec) -> None``
.........................................................
This event fires whenever a command with a give name (``<cmd-name>``)
has its ``SubprocSpec.run()`` method called.  This is fired
prior to the run call executing anything at all. This receives the
``SubprocSpec`` object as ``spec`` that triggered the event, allowing
the handler to modify the spec if needed.  For example, if we wanted to
intercept an ``ls`` spec, we could write:

.. code-block:: python

    @events.on_pre_spec_run_ls
    def print_when_ls(spec=None, **kwargs):
        print("Look at me list stuff!")


``on_post_spec_run(spec: SubprocSpec) -> None``
..........................................................
This event fires whenever any command has its ``SubprocSpec.run()``
method called.  This is fired after to the run call has executed
everything except returning. This recieves the ``SubprocSpec`` object as
``spec`` that triggered the event, allowing the handler to modify the spec
if needed. Note that because of the way process pipelines and specs work
in xonsh, the command will have started running, but won't necessarily have
completed. This is because ``SubprocSpec.run()`` does not block.
For example, if we wanted to get any spec after a command has started running,
we could write:

.. code-block:: python

    @events.on_post_spec_run
    def print_while_ls(spec=None, **kwargs):
        print("A command is running")



``on_post_spec_run_<cmd-name>(spec: SubprocSpec) -> None``
..........................................................
This event fires whenever a command with a give name (``<cmd-name>``)
has its ``SubprocSpec.run()`` method called.  This is fired
after to the run call has executed everything except returning. This recieves the
``SubprocSpec`` object as ``spec`` that triggered the event, allowing
the handler to modify the spec if needed. Note that because of the
way process pipelines and specs work in xonsh, the command will have
started running, but won't necessarily have completed. This is because
``SubprocSpec.run()`` does not block.
For example, if we wanted to get an ``ls`` spec after ls has started running,
we could write:

.. code-block:: python

    @events.on_post_spec_run_ls
    def print_while_ls(spec=None, **kwargs):
        print("Mom! I'm listing!")
