"""Lazy imports that may apply across the xonsh package."""
import importlib

from xonsh.lazyasd import LazyObject

pygments = LazyObject(lambda: importlib.import_module('pygments'),
                      globals(), 'pygments')
pyghooks = LazyObject(lambda: importlib.import_module('xonsh.pyghooks'),
                      globals(), 'pyghooks')
