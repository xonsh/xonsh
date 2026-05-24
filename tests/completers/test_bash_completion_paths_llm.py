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

import os
import pathlib
import shutil

import pytest

from xonsh import platform as plat_mod
from xonsh.completers import bash_completion as bc_mod


def test_bridge_fallback_delegates_to_canonical_default():
    """The bridge fallback returns the same tuple as the canonical
    env-var default — they are bound, not parallel copies."""
    assert bc_mod._bash_completion_paths_default() == tuple(
        plat_mod.BASH_COMPLETIONS_DEFAULT
    )


def test_get_bash_completions_source_loads_framework_then_user_dir(tmp_path):
    """User completion directories supplement the first framework script.

    This lets defaults such as Homebrew's ``bash_completion`` coexist
    with extra user scripts in ``~/.bash_completions``.
    """
    homebrew = tmp_path / "homebrew" / "bash_completion"
    fallback = tmp_path / "fallback" / "bash_completion"
    user_dir = tmp_path / ".bash_completions"
    custom_a = user_dir / "a_custom"
    custom_b = user_dir / "b_custom"
    for path in (homebrew, fallback, custom_a, custom_b):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test completion\n")

    source = bc_mod._get_bash_completions_source([homebrew, fallback, user_dir])

    assert source == "\n".join(
        bc_mod._source_bash_completion_file(path)
        for path in (homebrew, custom_a, custom_b)
    )
    assert fallback.as_posix() not in source


def test_source_bash_completion_file_uses_msys_path_on_windows(monkeypatch):
    """Native Windows paths must be translated before Bash's source builtin.

    Git/MSYS Bash path conversion does not apply to shell builtins, so
    ``source "C:/..."`` is not portable there.
    """
    monkeypatch.setattr(bc_mod.platform, "system", lambda: "Windows")

    path = pathlib.PureWindowsPath(
        r"C:\Users\runneradmin\AppData\Local\Temp\.bash_completions\foo"
    )

    expected = "source /c/Users/runneradmin/AppData/Local/Temp/.bash_completions/foo"
    assert bc_mod._source_bash_completion_file(path) == expected


def test_bash_completions_executes_user_dir_scripts(tmp_path):
    """Scripts in supplemental completion directories must affect results."""
    command = bc_mod._bash_command()
    if shutil.which(command) is None:
        pytest.skip("bash not found on PATH")

    framework = tmp_path / "bash_completion"
    user_dir = tmp_path / ".bash_completions"
    user_script = user_dir / "foo"
    framework.write_text("# empty test framework\n")
    user_dir.mkdir()
    user_script.write_text(
        """
_foo_completion()
{
    COMPREPLY=(bar)
}
complete -F _foo_completion foo
"""
    )

    completions, lprefix = bc_mod.bash_completions(
        "",
        "foo ",
        4,
        4,
        paths=[framework, user_dir],
        command=command,
    )

    assert completions == {"bar "}
    assert lprefix == 0


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
    # User-defined
    assert os.path.expanduser("~/.bash_completions") in paths
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


def test_canonical_bsd_default_covers_ports_prefix():
    """BSD installs bash-completion outside the base system, under
    ``/usr/local`` (FreeBSD/DragonFly ports & pkg, OpenBSD pkg) or
    ``/usr/pkg`` (NetBSD pkgsrc). Without these the default is empty
    and the bridge has nothing to source — bash completion silently
    breaks for every user on BSD.

    Only the library file ``bash_completion`` (no extension) is listed
    — the user-facing wrapper ``bash_completion.sh`` shipped by
    bash-completion 2.17+ short-circuits in non-interactive bash, so
    sourcing it from xonsh's ``bash -c`` bridge produces empty
    completions. Pin both behaviours so a future regression that adds
    the wrapper back in front gets caught.
    """
    if not plat_mod.ON_BSD:
        import pytest

        pytest.skip("BSD-only assertion")
    paths = tuple(plat_mod.BASH_COMPLETIONS_DEFAULT)
    # /usr/local — FreeBSD ports / pkg, OpenBSD pkg
    assert "/usr/local/share/bash-completion/bash_completion" in paths
    # /usr/pkg — NetBSD pkgsrc
    assert "/usr/pkg/share/bash-completion/bash_completion" in paths
    # The interactive-only wrapper must NOT be listed — it produces
    # empty completions when sourced from xonsh's non-interactive bash.
    for path in paths:
        assert not path.endswith("bash_completion.sh"), (
            f"interactive-only wrapper leaked into BASH_COMPLETIONS_DEFAULT: {path!r}"
        )
