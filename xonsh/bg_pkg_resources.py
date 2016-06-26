"""Background thread loader for pkg_resources."""
import os
import sys
import time
import builtins
import threading
import importlib


class PkgResourcesProxy(object):
    """Proxy object for pkg_resources module that throws an ImportError
    whenever an attribut is accessed.
    """

    def __getattr__(self, name):
        raise ImportError('cannot access ' + name + 'on PkgResourcesProxy, '
                          'please wait for pkg_resources module to be fully '
                          'loaded.')


class PkgResourcesLoader(threading.Thread):
    """Thread to load the pkg_resources module."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.start()

    def run(self):
        # wait for other modules to stop being imported
        i = 0
        last = -6
        hist = [-5, -4, -3, -2, -1]
        while not all(last == x for x in hist):
            time.sleep(0.001)
            last = hist[i%5] = len(sys.modules)
            i += 1
        # now import pkg_resources properly
        if isinstance(sys.modules['pkg_resources'], PkgResourcesProxy):
            del sys.modules['pkg_resources']
        pr = importlib.import_module('pkg_resources')
        if 'pygments.plugin' in sys.modules:
            sys.modules['pygments.plugin'].pkg_resources = pr


def load_pkg_resources_in_background():
    """Entry point for loading pkg_resources module in background."""
    if 'pkg_resources' in sys.modules:
        return
    env = getattr(builtins, '__xonsh_env__', os.environ)
    if env.get('XONSH_DEBUG', None):
        import pkg_resources
        return
    sys.modules['pkg_resources'] = PkgResourcesProxy()
    PkgResourcesLoader()
