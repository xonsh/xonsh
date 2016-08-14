**Added:**

* The ``exec`` command is now a first class alias that acts the same way as in
  sh-based languages. It replaces the current process with the command and
  argument that follows it. This allows xonsh to be used as a default shell
  while maintaining functionality with SSH, gdb, and other third party programs
  that assume the default shell supports raw ``exec command [args]`` syntax.

  This feature introduces some ambiguity between exec-as-a-subprocess and
  exec-as-a-function (the inescapable Python builtin). Though the two pieces of
  syntax do not overlap, they perform very different operations. Please see
  the xonsh FAQ for more information on trade-offs and mitigation strategies.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
