**Added:** None
  
Xontrib loading mechanism has been slightly extended. If a xontrib define a function named ``xontrib_init``, this function will be called by ``xontrib load``, or at startup just after the main ``__xonsh_shell__`` has been instantiated. This allow ``xontrib`` s to not have side effects at import time, and common python module to define xonsh extensions more easily

**Changed:** None

`xonsh.xontribs:update_context` has been modified to both return both a
modified context, as well as the xontrib module that was loaded.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
