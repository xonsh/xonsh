**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Readline history would try to read the first element of history prior to 
  actually loading any history. This caused an exception to be raised on 
  Windows at xonsh startup when using pyreadline.

**Security:** None
