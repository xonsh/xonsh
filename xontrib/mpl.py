"""Matplotlib xontribution."""

from xonsh.proc import foreground

@foreground
def _mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xonsh.mplhooks import show
    show()


aliases['mpl'] = _mpl