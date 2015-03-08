.. _tutorial:

*******************
Tutorial
*******************
xonsh is shell language and command prompt. Unlike other shells, xonsh is 
based on Python with additional syntax added that makes calling subprocess
commands, manipulating the environment, and dealing with the file system easy. 
The xonsh command prompt give the users interactive access to the xonsh 
language. 

While all Python code is also xonsh, not all BASH code can be used in xonsh.
That would defeat the purpose and Python is better anyway! Still, xonsh is
BASH-wards compatible in the ways that matter, such as for running commands, 
reading in the BASH environment, and utilizing BASH tab completion.

The purpose of this tutorial is to teach you xonsh. There are many excellent
guides out there for learning Python and this will not join their ranks.
Similarly, you'd probably get the most out of this tutorial if you have 
already used a command prompt or interactive interpreter. 

Let's dive in!

Starting xonsh
========================
Assuming you have successfully installed xonsh (see http://xonsh.org),
you can start up the xonsh interpreter via the ``xonsh`` command. Suppose
you are in a lesser terminal:

.. code-block:: bash

    bash $ xonsh
    snail@home ~ $ 

Now we are in a xonsh shell. Our username happens to be ``snail``, our
hostname happens to be ``home``, and we are in our home directory (``~``).
Alternatively, you can setup your terminal emulator (xterm, gnome-terminal, 
etc) to run xonsh automatically when it starts up. This is recomended.

Basics
=======================
xon