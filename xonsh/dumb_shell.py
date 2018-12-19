"""A dumb shell for when $TERM == 'dumb', which usually happens in emacs."""
import builtins

from xonsh.readline_shell import ReadlineShell


class DumbShell(ReadlineShell):
    """A dumb shell for when $TERM == 'dumb', which usually happens in emacs."""

    def __init__(self, *args, **kwargs):
        builtins.__xonsh__.env["XONSH_COLOR_STYLE"] = "emacs"
        super().__init__(*args, **kwargs)
