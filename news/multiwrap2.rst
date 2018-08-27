**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed automatic wrapping of many subprocesses that spanned multiple lines via
  line continuation characters with logical operators separating the commands.
  For example, the following now works:

  .. code-block:: sh

        echo 'a' \
        and echo 'b'

**Security:** None
