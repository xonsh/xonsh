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
