"""DEPRECATED: Use `xonsh.lib.lazyjson` instead of `xonsh.lazyjson`."""

import warnings

warnings.warn(
    "Use `xonsh.lib.lazyjson` instead of `xonsh.lazyjson`.",
    DeprecationWarning,
    stacklevel=2,
)

from xonsh.lib.lazyjson import *  # noqa
