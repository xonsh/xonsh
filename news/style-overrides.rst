**Added:**

* Added new env-var ``XONSH_STYLE_OVERRIDES``. The variable is
  a dictionary containing custom prompt_toolkit style definitions.
  For instance
  ```
  $XONSH_STYLE_OVERRIDES['completion-menu'] = 'bg:#333333 #EEEEEE'
  ```
  will provide for more visually pleasing completion menu style whereas
  ```
  $XONSH_STYLE_OVERRIDES['bottom-toolbar'] = 'noreverse'
  ```
  will prevent prompt_toolkit from inverting the bottom toolbar colors
  (useful for powerline extension users)

  Note: This only works with prompt_toolkit 2 prompter.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
