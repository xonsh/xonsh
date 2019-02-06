**Added:**

* New ``xonsh.aliases.partial_eval_alias()`` function and related classes
  for dispatching and evaluating partial alias applications for callable
  aliases.

**Changed:**

* The ``xonsh.Aliases.eval_alaises()`` method updated to use
  ``xonsh.aliases.partial_eval_alias()``.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* Fixed bug with evaluating recurssive aliases that did not implement
  the full callable alias signature.

**Security:**

* <news item>
