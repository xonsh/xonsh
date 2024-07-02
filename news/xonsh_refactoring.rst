**Added:**

* Created ``xonsh.api`` to use xonsh functionality in pure python code and downstream projects (#5383 #5538).
  It's usable but don't treat this serios because it's mostly to move some functions into distinct
  submodule to reflect the intention to have the API. We need review and improvements here.

**Changed:**

* Big refactoring of internal modules structure to give clear understanding of internal xonsh components (#5538).
  E.g. if you have ``import xonsh.jobs`` convert this to ``import xonsh.procs.jobs``.
  This kind of refactoring occurs once per many years.

**Deprecated:**

* Starting from this release we notify that in the future we will not recommend to use ``xonsh.procs.run_subproc``
  and ``xonsh.built_ins.subproc_*`` functions for downstream projects because of #5383.
  We will develop ``xonsh.api`` as alternative.

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
