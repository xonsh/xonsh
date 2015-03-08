==========================
Frequently Asked Questions
==========================
Ok, so, maybe no one actually asked them.

1. Why xonsh?
-------------
Why Not?

2. Why not another exotic shell, such as ``fish``?
-----------------------------------------------------
While many other alternative shells have an amazing suite of features
as well as much improved syntax of traditional options, none of them 
are quite a beautiful as Python.  In xonsh, you get the best of all possible
worlds. A syntax that already fits your brain and any features that you 
desire.

3. Why not just use the IPython command line interface?
-------------------------------------------------------
There are two serious drawbacks to this approach - though believe me I have 
tried it. 

The first is that typing ``!`` before every subprocess command is 
extremely tedious.  I think that this is because it is a prefix operator and 
thus gets in the way of what you are trying to do right as you start to try 
to do it. Making ``!`` a postfix operator could address some of this, but 
would probably end up being annoying, though not nearly as jarring.

The second reason is that tab completion of subprocess commands after an ``!``
does not work. This is a deal breaker for day-to-day use. 