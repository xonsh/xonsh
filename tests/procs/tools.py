import platform

import pytest


ON_WINDOWS = platform.system() == "Windows"

skip_if_on_windows = pytest.mark.skipif(ON_WINDOWS, reason="Unix stuff")
