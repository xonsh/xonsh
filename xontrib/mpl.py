"""Matplotlib xontribution."""

from xonsh.proc import foreground as foreground

__all__ = ()


@foreground
def mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xontrib.mplhooks import show
    show()


aliases['mpl'] = mpl
