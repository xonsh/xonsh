.. _events:

********************
Advanced Events
********************

If you haven't, go read the `events tutorial <tutorial_events.html>`_ first. This documents the messy
details of the event system.

You may also find the `events API reference <api/events.html>`_ useful.

Why Unordered?
==============
Yes, handler call order is not guaranteed. Please don't file bugs about this.

This was chosen because the order of handler registration is dependent on load order, which is
stable in a release but not something generally reasoned about. In addition, xontribs mean that we
don't know what handlers could be registered. So even an "ordered" event system would be unable to
make guarantees about ordering because of the larger system.

Because of this, the event system is not ordered; this is a form of abstraction. Order-dependent
semantics are not encouraged by the built-in methods.

So how do I handle results?
===========================
``Event.fire()`` returns a list of the returns from the handlers. You should merge this list in an
appropriate way.

What are Species?
=================
In xonsh, events come in species. Each one may look like an event and quack like an event, but they
behave differently.

This was done because load hooks look like events and quack like events, but they have different
semantics. See `LoadEvents <api/events.html#xonsh.events.LoadEvent>`_ for details.

In order to turn an event from the default ``Event``, you must transmogrify it, using
``events.transmogrify()``. The class the event is turned in to must be a subclass of ``AbstractEvent``.

(Under the hood, transmogrify creates a new instance and copies the handlers and docstring from the
old instance to the new one.)

