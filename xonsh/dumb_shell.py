"""A dumb shell for when $TERM == 'dumb', which usually happens in emacs."""

import xonsh.session as xsh
from xonsh.readline_shell import ReadlineShell


class DumbShell(ReadlineShell):
    """A dumb shell for when $TERM == 'dumb', which usually happens in emacs."""

    def __init__(self, *args, **kwargs):
        xsh.XSH.env["XONSH_COLOR_STYLE"] = "emacs"
        super().__init__(*args, **kwargs)
