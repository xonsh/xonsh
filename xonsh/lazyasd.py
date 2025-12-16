"""DEPRECATED: Use `xonsh.lib.lazyasd` instead of `xonsh.lazyasd`."""

import warnings

warnings.warn(
    "Use `xonsh.lib.lazyasd` instead of `xonsh.lazyasd`.",
    DeprecationWarning,
    stacklevel=2,
)

from xonsh.lib.lazyasd import *  # noqa
