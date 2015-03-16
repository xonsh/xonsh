==========================
Frequently Asked Questions
==========================
Ok, so, maybe no one actually asked them.

1. Why xonsh?
-------------
The idea for xonsh first struck while I was reviewing the BASH chapter 
(written by my co-author `Katy Huff <http://katyhuff.github.io/>`_)
of `Effective Computation in Physics <http://physics.codes/>`_. In the book
we spend a bunch of time describing important, but complex ideas, such 
as piping. However, we don't even touch on more 'basic' aspects of the BASH
language, such as if-statements or loops. Even though I have been using BASH
for well over a decade, I am not even sure I *know how*
to add two numbers together in it or consistently create an array. This is
normal.

If the tool is so bad, then maybe we need a new tool. So xonsh is really meant
to solve the problem that other shells don't "fit your brain." 
In some programing situations this is OK because of what you get 
(an optimizing compiler, type safety, provable correctness, register access).
But a shell that doesn't fit your brain is only a liability.

Coincidentally, within the week, `an article floated to the top of Hacker News <http://stephen-brennan.com/2015/01/16/write-a-shell-in-c/>`_ 
that teaches you how to write a shell in C. So I thought, "It can't be 
that hard..."

And thus, `again <http://exofrills.org>`_, I entered the danger zone.


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


4. So how does this all work?
-----------------------------
We use `PLY <http://www.dabeaz.com/ply/ply.html>`_ to tokenize and parse 
xonsh code. This is heavily inspired by how `pycparser <https://github.com/eliben/pycparser>`_
used this PLY. From our parser, we construct an abstract syntax tree (AST)
only using nodes found in the Python ``ast`` standard library module. 
This allows us to compile and execute the AST using the normal Python tools.

Of course, xonsh has special builtins, so the proper context 
(builtins, globals, and locals) must be set up prior to actually executing 
any code. However, the AST can be constructed completely independently of 
any context...mostly.  

While the grammar of the xonsh language is context-free, it was convienent 
to write the executer in a way that is slightly context sensitive. This is 
because certain expressions are ambiguious as to whether they belong to 
Python-mode or subprocess-mode. For example, most people will look at 
``ls -l`` and see a listing command.  However, if ``ls`` and ``l`` were 
Python variables, this could be transformed to the equivalent (Python) 
expressions ``ls - l`` or ``ls-l``.  Neither of which are valid listing 
commands.

What xonsh does to overcome such ambiquity is to check if the left-most 
name (``ls`` above) is in the present Python context. If it is, then it takes
the line to be valid xonsh as written. If the left-most name cannot be found,
then xonsh assumes that the left-most name is an external command. It thus 
attempts to parse the line after wrapping it in an uncaptured subprocess 
call ``$[]``.  If wrapped version successfully parses, the ``$[]`` version 
stays. Otherwise the original line is retained.

All of the context sensitive parsing occurs as an AST transformation prior to 
any code is executed.  This ensures that code will never be partially executed
before failing.

It is critical to note that the context sensitive parsing is a convenience
meant for humans.  If ambiguity remains or exactness is required, simply 
manually use the ``$[]`` or ``$()`` operators on your code.


5. Context-sensitive parsing is gross
--------------------------------------
Yes, context-sensitive parsing is gross. But the point of xonsh is that it
is ultimately a lot less gross than other shell languages, such as BASH.
Furthermore, its use is heavily limited here.
