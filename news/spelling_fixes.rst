**Added:**

*  ``xonsh.color_tools.make_palette()``

   Simple rename of the pre-existing
   ``xonsh.color_tools.make_pallete()`` function.

*  ``xonsh.tools.decorator()`` function/method decorator.

   This allows for an API function to be annotated with a
   decorator that documents deprecation, while also tying in
   functionality that will warn a user that the function has
   been deprecated, and, raise an ``AssertionError`` if the
   function has passed its expiry date.

**Changed:** None

**Deprecated:**

*  ``xonsh.color_tools.make_pallette()``

**Removed:** None

**Fixed:**

*  Numerous spelling errors in documentation, docstrings/comments, text
   strings and local variable names.

*  Spelling error in the ``xonsh.color_tools.make_pallette()`` public
   function declaration. This was fixed by renaming the function to
   ``xonsh.color_tools.make_palette()`` while maintaining a binding
   of ``make_pallette()`` to the new ``make_palette()`` in case users
   are already used to this API.

**Security:** None
