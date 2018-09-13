"""Matplotlib xontribution. This xontrib should be loaded before matplotlib
is imported.
"""

from xonsh.tools import unthreadable
from xonsh.lazyasd import lazyobject


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
       not __xonsh__.env.get('XONSH_INTERACTIVE'):
        return
    # Since we are in interactive mode, let's monkey-patch plt.show
    # to try to never block.
    module.ion()
    module._INSTALL_FIG_OBSERVER = False
    plt_show = module.show

    def xonsh_show(*args, **kwargs):
        """This is a monkey patched version of matplotlib.pyplot.show()
        for xonsh's interactive mode. First it tries non-blocking mode
        (block=False). If for some reason this fails, it will run show
        in normal blocking mode (block=True).
        """
        kwargs.update(block=False)
        rtn = plt_show(*args, **kwargs)
        figmanager = pylab_helpers.Gcf.get_active()
        if figmanager is not None:
            # unblocked mode failed, try blocking.
            kwargs.update(block=True)
            rtn = plt_show(*args, **kwargs)
        return rtn

    module.show = xonsh_show

    # register figure drawer
    @events.on_postcommand
    def redraw_mpl_figure(**kwargs):
        """Redraws the current matplotlib figure after each command."""
        pylab_helpers.Gcf.draw_all()
