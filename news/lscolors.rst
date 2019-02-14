**Added:**

* New ``xonsh.color_tools.short_to_ints()`` function for directly
  converting a short (0 - 256) color into a 3-tuple of ints
  represeting its RGB value.
* New ``xonsh.ansi_colors.ansi_reverse_style()`` function for
  converting a mapping of color names to ANSI escape codes into
  a mapping from escape codes into color names. This is not a
  round-trippable operation.
* New ``xonsh.ansi_colors.ansi_color_escape_code_to_name()`` function
  for converting an ANSI color escape code into the closest xonsh
  color name for a given style.
* New ``xonsh.events.EventManager.exists()`` method enables the checking
  of whether events actually exist with out making the event if it
  doesn't exist.
* New command-specific event categories called ``on_pre_spec_run_<cmd-name>``
  and ``on_post_spec_run_<cmd-name>`` will be fired before and after
  ``SubpocSpec.run()`` is called.  This allows for command specific
  events to be executed.  For example, ``on_pre_spec_run_ls`` would
  be run prior to an invocation of ``ls``.
* New ``xonsh.environ.LsColors`` class for managing the ``$LS_COLORS``
  environment variable. This ensures that the ``ls`` command respects the
  ``$XONSH_COLOR_STYLE`` setting. An instance of this class is added to the
  environment when either the ``$LS_COLORS`` class is first accessed or
  the ``ls`` command is executed.
* The ``on_pre_spec_run_ls`` event is initialized with a default handler
  that ensures that ``$LS_COLORS`` is set in the actual environment prior
  to running an ``ls`` command.
* New ``xonsh.tools.detype()`` function that simply calls an objects own
  ``detype()`` method in order to detype it.
* New ``xonsh.tools.always_none()`` function that simply returns None.

**Changed:**

* The black and white style ``bw`` now uses actual black and white
  ANSI colore codes for its colors, rather than just empty color
  sequences.
* An environment variable ``detype`` operation no longer needs to be
  function, but may also be ``None``. If ``None``, this variable is
  considered not detypeable, and will not be exported to subprocess
  environments via the ``Env.detype()`` function.
* An environment variable ``detype`` function no longer needs to return
  a string, but may also return ``None``. If ``None`` is returned, this
  variable is  considered not detypeable, and will not be exported to
  subprocess environments via the ``Env.detype()`` function.
* The ``Env.detype()`` method has been updated to respect the new
  ``None`` types when detyping.
* The ``xonsh.tools.expandvars()`` function has been updated to respect
  the new ``None`` types when detyping.
* The ``xonsh.xonfig.make_xonfig_wizard()`` function has been updated to respect
  the new ``None`` types when detyping.
* Event handlers may now be added and discarded during event firing for
  normal events.  Such modifications will not be applied to until the
  current firing operation is concluded. Thus you won't see newly added
  events fired.

**Deprecated:**

* The ``xonsh.color_tools.make_pallete()`` function is no
  longer deprecated, as it is actually needed in other parts of
  xonsh still, such as ``pyghooks``.

**Removed:**

* All code references to ``$FORMATTER_DICT`` have been removed.

**Fixed:**

* Minor fixes to ``xonsh.events.debug_level()``.

**Security:**

* <news item>
