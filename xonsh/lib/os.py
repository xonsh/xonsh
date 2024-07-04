"""DEPRECATED: Use `xonsh.lib.lazyasd` instead of `xonsh.lazyasd`."""

import warnings

warnings.warn(
    "Use `xonsh.api.os` instead of `xonsh.lib.os`.", DeprecationWarning, stacklevel=2
)

from xonsh.api.os import *  # noqa
