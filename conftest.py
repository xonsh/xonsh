import os
import sys

# Ensure the source tree is on sys.path so that xonsh is imported from here,
# not from site-packages. This is needed for bare `pytest` and IDE runners.
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import xonsh as _xonsh  # noqa: E402

_expected = os.path.abspath(os.path.join(_root, "xonsh", "__init__.py"))
_actual = os.path.abspath(_xonsh.__file__)
if _actual != _expected:
    raise RuntimeError(
        "\nXonsh package is installed. The `pytest` command will not work correctly and will use it instead of the "
        "source tree:\n"
        f" * Source tree: {_expected!r}\n"
        f" * Site-packages: {_actual!r}\n"
        "Use `python -m pytest` to ensure that xonsh is imported from the source tree rather than site-packages."
    )

# Load the xonsh pytest plugin (provides xession fixture, etc.).
# With `python -m pytest` it's already loaded via the entry point;
# with bare `pytest` or IDE runners it needs to be loaded explicitly.
if "xonsh.pytest.plugin" not in sys.modules:
    pytest_plugins = ("xonsh.pytest.plugin",)
