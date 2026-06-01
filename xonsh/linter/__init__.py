"""Static lint rules for xonsh source code.

Where :mod:`xonsh.checker` answers "does it parse?" and :mod:`xonsh.formatter`
answers "is it formatted?", :mod:`xonsh.linter` answers "is it likely *wrong*?"
— without executing the code. It runs a small set of rules over the transformed
xonsh AST, drawing on xonsh's own registries (the environment-variable table in
:mod:`xonsh.environ`) for checks no generic linter could make.

Public API:

- :func:`lint_source` — lint a string of xonsh source, returning ``Finding``\\ s.
- :class:`Finding` — one diagnostic (line, col, code, message).

The CLI entry point used by ``xonsh lint ...`` lives in :mod:`xonsh.linter.cli`.
"""

from xonsh.linter.cli import lint_source
from xonsh.linter.rules import Finding

__all__ = ["lint_source", "Finding"]
