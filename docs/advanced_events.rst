.. _events:

********************
Advanced Events
********************

If you havent, go read the `events tutorial <tutorial_events.rst>`_ first. This documents the messy
details of the event system.

You may also find the `events API reference <api/events.html>`_ useful.

What are Species?
=================
In xonsh, events come in species. Each one may look like an event and quack like an event, but they
behave differently.

This was done because load hooks look like events and quack like events, but they have different
semantics. See `LoadEvents <api/events.html#xonsh.events.LoadEvent>`_ for details.

Why Unordered?
==============
Yes, handler call order is not guarenteed. Please don't file bugs about this.

This was chosen because the order of handler registration is dependant on load order, which is 
stable in a release but not something generally reasoned about. In addition, xontribs mean that we
don't know what handlers could be registered.

Because of this, the event system is not ordered, and order-dependant semantics are not encouraged.

So how do I handle results?
===========================
``Event.fire()`` returns a list of the returns from the handlers. You should merge this list in an 
appropriate way.
