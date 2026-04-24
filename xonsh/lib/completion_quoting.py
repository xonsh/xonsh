"""Shared helper for deciding whether a completion candidate needs
shell-quoting in xonsh.

Used by both the built-in path completer
(:mod:`xonsh.completers.path`) and the bash-completion bridge
(:mod:`xonsh.completers.bash_completion`), which historically carried
near-identical copies of this regex that drifted over time.

Pure-Python, no side effects on import — safe for standalone use, as
:mod:`xonsh.completers.bash_completion` requires.
"""

import os
import platform
import re

# Characters the xonsh parser would treat specially in a subprocess
# argument, verified by feeding ``ls fi<ch>le`` through
# ``CompletionContextParser``:
#
#   whitespace, ``|`` ``;`` ``<`` ``>`` ``&``      — split the token
#   ``(`` ``)`` ``[`` ``]`` ``{`` ``}`` ``,``      — grouping / glob syntax
#   ``*`` ``?``                                     — glob wildcards
#   `` ` `` ``$``                                   — command/var substitution
#   ``"`` ``'``                                     — string boundaries
#   ``#``                                           — comment
#   ``%`` (Windows only)                            — env var reference
#
# The word boundaries catch ``and``/``or`` appearing as whole tokens,
# since those are xonsh keywords.
_PATTERN = re.compile(
    r"""[\s`$\{\}\[\]\,\*\(\)"'\?&#|;<>"""
    + ("%" if platform.system() == "Windows" else "")
    + r"]|\band\b|\bor\b"
)


def name_needs_quotes(name: str, sep: str | None = None) -> bool:
    """Return True if *name* would be mangled by the xonsh parser and
    therefore needs to be wrapped in quotes when emitted as a completion.

    Parameters
    ----------
    name :
        The candidate completion string (a path, an executable name, …).
    sep :
        The path separator the caller treats as safe (``os.sep`` on
        POSIX, ``os.altsep`` in forced-POSIX mode on Windows). When a
        backslash appears in *name* but *sep* is not backslash, the
        backslash is a shell metacharacter and forces quoting. Defaults
        to :data:`os.sep`.
    """
    if sep is None:
        sep = os.sep
    if _PATTERN.search(name):
        return True
    return "\\" in name and sep != "\\"
