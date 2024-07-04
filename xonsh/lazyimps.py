"""DEPRECATED: Use `xonsh.lib.lazyasd` instead of `xonsh.lazyimps`."""

import warnings

warnings.warn(
    "Use `xonsh.lib.lazyimps` instead of `xonsh.lazyimps`.",
    DeprecationWarning,
    stacklevel=2,
)

from xonsh.lib.lazyimps import *  # noqa
