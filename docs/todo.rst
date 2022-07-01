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
