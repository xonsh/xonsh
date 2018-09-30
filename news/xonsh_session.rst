**Added:** None

**Changed:** None

* All `__xonsh_*__` builtins have been migrated to a `XonshSession` instance at
  `__xonsh__`. E.g. `__xonsh_env__` is now `__xonsh__.env`. 

**Deprecated:** None

* All `__xonsh_*__` builtins are deprected. Instead, the corresponding
  `__xonsh__.*` accessor should be used. The existing `__xonsh_*__` accessors still work,
  but issue annoying warnings.

**Removed:** None

**Fixed:** None

**Security:** None
