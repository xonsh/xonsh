.. _api:

=================
Xonsh API
=================
For those of you who want the gritty details.


**Language:**

.. autosummary::
    :toctree: _autosummary/lang
    :template: api-summary-module.rst
    :recursive:

    xonsh.parsers.lexer
    xonsh.parser
    xonsh.parsers.ast
    xonsh.execer
    xonsh.imphooks


**Command Prompt:**

.. autosummary::
    :toctree: _autosummary/cmd
    :template: api-summary-module.rst
    :recursive:

    xonsh.built_ins
    xonsh.environ
    xonsh.aliases
    xonsh.dirstack
    xonsh.procs
    xonsh.lib.inspectors
    xonsh.history
    xonsh.completer
    xonsh.completers
    xonsh.prompt
    xonsh.shells
    xonsh.shells.base_shell
    xonsh.shells.readline_shell
    xonsh.shells.ptk_shell
    xonsh.lib.pretty
    xonsh.history.diff_history
    xonsh.xoreutils


**Helpers:**

.. autosummary::
    :toctree: _autosummary/helpers
    :template: api-summary-module.rst
    :recursive:

    xonsh.events
    xonsh.lib
    xonsh.tools
    xonsh.platform
    xonsh.lazyjson
    xonsh.lazyasd
    xonsh.lib.openpy
    xonsh.foreign_shells
    xonsh.commands_cache
    xonsh.tracer
    xonsh.main
    xonsh.color_tools
    xonsh.pyghooks
    xonsh.shells.dumb_shell
    xonsh.wizard
    xonsh.xonfig
    xonsh.xontribs
    xonsh.codecache
    xonsh.contexts


**Xontribs:**

.. autosummary::
    :toctree: _autosummary/xontribs
    :template: api-summary-module.rst
    :recursive:

    xontrib
