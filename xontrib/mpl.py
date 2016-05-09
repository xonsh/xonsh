"""Matplotlib xontribution."""

from xonsh.proc import foreground as _foreground

@_foreground
def _mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xontrib.mplhooks import show
    show()


aliases['mpl'] = _mpl
