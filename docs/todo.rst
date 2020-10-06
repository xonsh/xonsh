==========================
Wishlist & To-Dos
==========================
Here is what is targeted for future versions of xonsh. Any one wishing
to tackle any of these or add their own is encouraged to do so!

Add xsh syntax highlighting on Github
----------------------------------------
There is a way to `contribute to github/linguist <https://github.com/github/linguist/blob/master/CONTRIBUTING.md>`_
to add xsh syntax highlighting. It would be great for someone to add xonsh to linguist.
For now we use Python syntax by adding the ``language`` to ``.gitattributes``:

.. code-block::

    *xonshrc text linguist-language=Python
    *.xsh text linguist-language=Python

xontribs
----------------------------------------
This is simply a list of things we wish existed as a xontrib.

* Gitsome-style rich git(hub) client
* Timeout context manager--will kill a ``with`` block if it takes too long
* Macros to run a command in a specific container
* Tools to go between ``namedtuple`` and shell-style tables
* Able to use ``find``-like and ``grep``-like calls as iterables
* ``touch`` and ``rm`` like xoreutils
* `Keep <https://github.com/OrkoHunter/keep>`_ (With PTK keyboard shortcut)
* Display docstring of python class/method/function being typed into xonsh prompt, like ptpython
* udisks notifications and easy access
* Easily (transparently) load/save data


Tab completion from man pages
---------------------------------
One of the more genius ideas I first encountered from ``fish`` is the idea
that man pages can be used to supply matches to tab-completion.  In principle
this is not that hard. First, we just need to use ``man2html`` and then 
parse the html.


Support and testing for other platforms
-------------------------------------------
This includes:

* Support for future versions of Python
* Testing on Mac OSX


urwid based command prompt
-----------------------------
Moving to urwid would allow for a whole new depth of user interaction.
There could be syntax highlighting as you type, a real interface for
environment variables, and so on.  The command prompt is only the start!
