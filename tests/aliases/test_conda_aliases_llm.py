"""Tests for conda activate/deactivate alias detection on Windows.

See xonsh/xonsh#3676 — `conda init xonsh` is broken on Windows, so the
`activate`/`deactivate` aliases are the practical fallback. They were
previously gated on ``ON_ANACONDA`` only, which requires xonsh itself to
be installed inside the conda env. This file covers the extended detection
that also fires when ``conda`` is reachable on ``$PATH``.
"""

import shutil

import pytest

from xonsh.aliases import make_default_aliases


def _activate_aliases(aliases):
    return aliases.get("activate"), aliases.get("deactivate")


@pytest.fixture
def force_windows(monkeypatch, xession):
    monkeypatch.setattr("xonsh.aliases.ON_WINDOWS", True)
    monkeypatch.setattr("xonsh.aliases.ON_ANACONDA", False)
    monkeypatch.setattr("xonsh.aliases._find_cmd_exe", lambda: "cmd.exe")
    return monkeypatch


def test_no_conda_no_activate_alias(force_windows, xession):
    force_windows.setattr(shutil, "which", lambda name, **kw: None)
    aliases = make_default_aliases()
    assert _activate_aliases(aliases) == (None, None)


def test_conda_on_path_sets_activate_alias(force_windows, xession):
    def fake_which(name, **kw):
        return r"C:\miniconda3\Scripts\conda.exe" if name == "conda" else None

    force_windows.setattr(shutil, "which", fake_which)
    aliases = make_default_aliases()
    activate, deactivate = _activate_aliases(aliases)
    assert activate == ["source-cmd", "activate.bat"]
    assert deactivate == ["source-cmd", "deactivate.bat"]


def test_on_anaconda_sets_activate_alias(force_windows, xession):
    force_windows.setattr("xonsh.aliases.ON_ANACONDA", True)
    force_windows.setattr(shutil, "which", lambda name, **kw: None)
    aliases = make_default_aliases()
    activate, deactivate = _activate_aliases(aliases)
    assert activate == ["source-cmd", "activate.bat"]
    assert deactivate == ["source-cmd", "deactivate.bat"]
