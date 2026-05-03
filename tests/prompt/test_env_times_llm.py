"""Smoke tests for ``xonsh.prompt.env`` and ``xonsh.prompt.times``.

Both modules feed the prompt-formatter system. Tests cover ``env_name``,
``find_env_name`` (incl. its pyvenv.cfg parser), ``_localtime``, and the
non-OSC ``emit_osc7`` short-circuits.
"""

import time

import pytest

from xonsh.prompt.env import (
    _determine_env_name,
    emit_osc7,
    env_name,
    find_env_name,
    vte_new_tab_cwd,
)
from xonsh.prompt.times import _localtime


@pytest.fixture(autouse=True)
def _reset_lru_cache():
    """``_determine_env_name`` is lru-cached — reset between tests."""
    _determine_env_name.cache_clear()
    yield
    _determine_env_name.cache_clear()


# --- _determine_env_name ----------------------------------------------------


def test_determine_env_name_falls_back_to_dir_name(tmp_path):
    venv = tmp_path / "myenv"
    venv.mkdir()
    assert _determine_env_name(str(venv)) == "myenv"


def test_determine_env_name_uses_pyvenv_cfg_prompt(tmp_path):
    venv = tmp_path / "v"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("prompt = my-prompt\n")
    assert _determine_env_name(str(venv)) == "my-prompt"


def test_determine_env_name_strips_quotes_from_prompt(tmp_path):
    venv = tmp_path / "v"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("prompt = 'quoted-prompt'\n")
    assert _determine_env_name(str(venv)) == "quoted-prompt"


def test_determine_env_name_strips_double_quotes(tmp_path):
    venv = tmp_path / "v"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text('prompt="double-quoted"\n')
    assert _determine_env_name(str(venv)) == "double-quoted"


def test_determine_env_name_no_prompt_falls_back(tmp_path):
    venv = tmp_path / "fallback"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    assert _determine_env_name(str(venv)) == "fallback"


# --- find_env_name ---------------------------------------------------------


def test_find_env_name_uses_virtual_env(xession, tmp_path):
    venv = tmp_path / "vve"
    venv.mkdir()
    xession.env["VIRTUAL_ENV"] = str(venv)
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    assert find_env_name() == "vve"


def test_find_env_name_falls_back_to_conda(xession):
    xession.env.pop("VIRTUAL_ENV", None)
    xession.env["CONDA_DEFAULT_ENV"] = "myconda"
    assert find_env_name() == "myconda"


def test_find_env_name_returns_none_when_unset(xession):
    xession.env.pop("VIRTUAL_ENV", None)
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    assert find_env_name() is None


# --- env_name ---------------------------------------------------------------


def test_env_name_disabled_returns_empty(xession):
    xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = True
    assert env_name() == ""


def test_env_name_with_virtual_env_prompt_passthrough(xession, tmp_path):
    """If ``$VIRTUAL_ENV_PROMPT`` is set and doesn't match the inferred name,
    it's used verbatim."""
    venv = tmp_path / "venv"
    venv.mkdir()
    xession.env.pop("VIRTUAL_ENV_DISABLE_PROMPT", None)
    xession.env["VIRTUAL_ENV"] = str(venv)
    xession.env["VIRTUAL_ENV_PROMPT"] = "custom-prompt"
    assert env_name() == "custom-prompt"


def test_env_name_returns_empty_when_no_env(xession):
    xession.env.pop("VIRTUAL_ENV", None)
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV_PROMPT", None)
    xession.env.pop("VIRTUAL_ENV_DISABLE_PROMPT", None)
    assert env_name() == ""


# --- emit_osc7 / vte_new_tab_cwd -------------------------------------------


def test_emit_osc7_no_tty_short_circuits(monkeypatch, capsys):
    """When stdout is not a tty (test runner case), emit_osc7 silently returns."""
    # The default sys.__stdout__ inside pytest is captured, not a tty.
    emit_osc7()
    out = capsys.readouterr()
    # No escape sequence written.
    assert "\033]7" not in out.out
    assert "\033]7" not in out.err


def test_emit_osc7_skips_on_none_stdout(monkeypatch):
    """When ``sys.__stdout__`` is None (very unusual setup), no error."""
    import sys as real_sys

    monkeypatch.setattr(real_sys, "__stdout__", None)
    # must complete without raising
    emit_osc7()


def test_vte_new_tab_cwd_calls_emit_osc7(monkeypatch):
    called = {"count": 0}

    def fake():
        called["count"] += 1

    monkeypatch.setattr("xonsh.prompt.env.emit_osc7", fake)
    vte_new_tab_cwd()
    assert called["count"] == 1


# --- _localtime ------------------------------------------------------------


def test_localtime_default_format(xession):
    xession.env["PROMPT_FIELDS"] = {}
    out = _localtime()
    # default format is %H:%M:%S
    assert len(out) == 8
    assert out.count(":") == 2


def test_localtime_custom_format(xession):
    xession.env["PROMPT_FIELDS"] = {"time_format": "%Y"}
    out = _localtime()
    assert out == time.strftime("%Y", time.localtime())


def test_localtime_with_no_prompt_fields(xession):
    """Even if PROMPT_FIELDS is missing, we get a sensible default-format
    string back."""
    xession.env.pop("PROMPT_FIELDS", None)
    out = _localtime()
    assert isinstance(out, str)
    assert len(out) >= 1
