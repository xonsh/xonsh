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


def test_canonical_darwin_default_covers_all_install_prefixes():
    """All four mac install prefixes (Homebrew Intel + Apple Silicon,
    MacPorts, Nix) must appear so the bridge auto-discovers
    bash-completion regardless of which package manager the user
    chose. Regression for two distinct bugs:

    * ``/opt/homebrew/...`` was missing — broke Apple Silicon
      Homebrew users.
    * MacPorts paths were never in the defaults despite an explicit
      docs section (``docs/platforms.rst``) telling MacPorts users to
      add them by hand.
    """
    if not plat_mod.ON_DARWIN:
        # The lazyobject realises platform-conditionally at import
        # time; on Linux/Windows CI there's nothing meaningful to
        # check here. The cross-binding test above still runs.
        import pytest

        pytest.skip("Darwin-only assertion")
    paths = tuple(plat_mod.BASH_COMPLETIONS_DEFAULT)
    # Homebrew Intel + Apple Silicon
    assert "/usr/local/share/bash-completion/bash_completion" in paths
    assert "/opt/homebrew/share/bash-completion/bash_completion" in paths
    # MacPorts
    assert "/opt/local/share/bash-completion/bash_completion" in paths
    # Nix shared profile (nix-darwin)
    assert "/run/current-system/sw/share/bash-completion/bash_completion" in paths


def test_canonical_linux_default_covers_brew_and_nix():
    """Linux defaults probe more than just the FHS path: Linuxbrew
    (servers/CI commonly use it) and Nix (NixOS, single-user nix-env)
    are first-class. Without this, users on either get zero
    completion auto-discovery.
    """
    if not plat_mod.ON_LINUX:
        import pytest

        pytest.skip("Linux-only assertion")
    paths = tuple(plat_mod.BASH_COMPLETIONS_DEFAULT)
    assert "/usr/share/bash-completion/bash_completion" in paths
    assert "/home/linuxbrew/.linuxbrew/share/bash-completion/bash_completion" in paths
    assert "/run/current-system/sw/share/bash-completion/bash_completion" in paths
