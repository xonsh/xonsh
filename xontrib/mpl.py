"""Matplotlib xontribution."""

from xonsh.tools import unthreadable

__all__ = ()


@unthreadable
def mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xontrib.mplhooks import show
    show()


aliases['mpl'] = mpl
