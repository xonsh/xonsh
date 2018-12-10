**Added:**

* Aliases from foreign shells (e.g. Bash) that are more than single expressions,
  or contain sub-shell executions, are now evaluated and run in the foreign shell.
  Previously, xonsh would attempt to translate the alias from sh-lang into
  xonsh. These restrictions have been removed.  For example, the following now
  works:

  .. code-block:: sh

      $ source-bash 'alias eee="echo aaa \$(echo b)"'
      $ eee
      aaa b

* New ``ForeignShellBaseAlias``, ``ForeignShellFunctionAlias``, and
  ``ForeignShellExecAlias`` classes have been added which manage foreign shell
  alias execution.

**Changed:**

* String aliases will now first be checked to see if they contain sub-expressions
  that require evaluations, such as ``@(expr)``, ``$[cmd]``, etc. If they do,
  then an ``ExecAlias`` will be constructed, rather than a simple list-of-strs
  substitutiuon alias being used. For example:

  .. code-block:: sh

      $ aliases['uuu'] = "echo ccc $(echo ddd)"
      $ aliases['uuu']
      ExecAlias('echo ccc $(echo ddd)\n', filename='<exec-alias:uuu>')
      $ uuu
      ccc ddd

* The ``parse_aliases()`` function now requires the shell name.
* ``ForeignShellFunctionAlias`` now inherits from ``ForeignShellBaseAlias``
  rather than ``object``.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* <news item>

**Security:**

* <news item>
