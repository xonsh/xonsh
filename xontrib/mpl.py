"""Matplotlib xontribution."""

from xonsh.tools import unthreadable
from xonsh.lazyasd import lazyobject
import time


__all__ = ()


@unthreadable
def mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xontrib.mplhooks import show
    show()


aliases['mpl'] = mpl


@lazyobject
def pylab_helpers():
    try:
        import matplotlib._pylab_helpers as m
    except ImportError:
        m = None
    return m


@events.on_import_post_exec_module
def interactive_pyplot(module=None, **kwargs):
    """This puts pyplot in interactive mode once it is imported."""
    if module.__name__ != 'matplotlib.pyplot' or \
       not __xonsh_env__.get('XONSH_INTERACTIVE'):
        return
    module.ion()
    module._INSTALL_FIG_OBSERVER = False

    # register figure drawer
    @events.on_postcommand
    def redraw_mpl_figure(**kwargs):
        """Redraws the current matplotlib figure after each command."""
        # module is pyplot
        if module.isinteractive():
            #print('redrawing')
            #module.ioff()
            pylab_helpers.Gcf.draw_all(force=True)
            #module.ion()
