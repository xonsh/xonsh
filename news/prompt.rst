**Added:**

* now ``$PROMPT_FIELDS`` is a custom class with method ``pick(field_name)`` to get the field value efficiently.
  The results are cached within the same prompt call.
* new class ``xonsh.prompt.base.PromptField`` to ease creating/extending prompt-fields

**Changed:**

* <news item>

**Deprecated:**

* <news item>

**Removed:**

* ``$XONSH_GITSTATUS_*`` is removed
  since the prompt fields can be customized easily now individually.
* ``$XONSH_GITSTATUS_FIELDS_HIDDEN`` is removed.
  Please set hidden fields in ``$PROMPT_FIELDS['gitstatus'].hidden = (...)``

**Fixed:**

* <news item>

**Security:**

* <news item>
