"""Regression tests for the platform default search paths used to
locate the ``bash_completion`` framework script.

The defaults used to live in two places:

* ``xonsh.platform.BASH_COMPLETIONS_DEFAULT`` — the canonical default
  surfaced via the ``$BASH_COMPLETIONS`` env var.
* ``xonsh.completers.bash_completion._bash_completion_paths_default``
  — a standalone fallback inside the bash-completion bridge.

They drifted: ``/opt/homebrew/...`` was added to the canonical list
but forgotten in the bridge fallback, leaving Apple Silicon Macs
without auto-discovery. The bridge fallback now delegates to the
canonical list — these tests pin both ends down so they can't drift
again.
"""

from xonsh import platform as plat_mod
from xonsh.completers import bash_completion as bc_mod


def test_bridge_fallback_delegates_to_canonical_default():
    """The bridge fallback returns the same tuple as the canonical
    env-var default — they are bound, not parallel copies."""
    assert bc_mod._bash_completion_paths_default() == tuple(
        plat_mod.BASH_COMPLETIONS_DEFAULT
    )


def test_canonical_darwin_default_includes_apple_silicon():
    """The Homebrew Apple Silicon path must appear in the canonical
    Darwin default. Regression for the original bug where
    ``$BASH_COMPLETIONS`` had no entry pointing at
    ``/opt/homebrew``-installed bash-completion frameworks, so brew
    completions silently never loaded on M-series Macs.
    """
    if not plat_mod.ON_DARWIN:
        # The lazyobject realises platform-conditionally at import
        # time; on Linux/Windows CI there's nothing meaningful to
        # check here. The cross-binding test above still runs.
        import pytest

        pytest.skip("Darwin-only assertion")
    paths = tuple(plat_mod.BASH_COMPLETIONS_DEFAULT)
    assert "/opt/homebrew/share/bash-completion/bash_completion" in paths
    assert "/usr/local/share/bash-completion/bash_completion" in paths
