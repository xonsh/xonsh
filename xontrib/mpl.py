"""Matplotlib xontribution."""

from xonsh.tools import foreground

__all__ = ()


@foreground
def mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xontrib.mplhooks import show
    show()


aliases['mpl'] = mpl
