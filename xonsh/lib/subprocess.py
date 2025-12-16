"""DEPRECATED: Use `xonsh.lib.lazyasd` instead of `xonsh.lazyasd`."""

import warnings

warnings.warn(
    "Use `xonsh.api.subprocess` instead of `xonsh.lib.subprocess`.",
    DeprecationWarning,
    stacklevel=2,
)

from xonsh.api.subprocess import *  # noqa
