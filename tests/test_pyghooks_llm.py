"""LLM-generated tests for ``xonsh/pyghooks.py``.

Currently covers:

* bg-validation state machine — ``_run_bg_validation`` must always
  populate ``_cmd_valid_cache``, even when the generation token is stale.
* PTK-only style modifier sanitization — regression for
  https://github.com/xonsh/xonsh/issues/6387 (``LS_COLORS`` carrying ANSI
  blink/reverse/hidden/strike codes used to crash pygments' ``StyleMeta``
  with ``AssertionError: wrong color format 'blink'`` at shell startup).
"""

from unittest.mock import MagicMock, patch

import pytest

from xonsh.environ import LsColors
from xonsh.pyghooks import XonshStyle


@pytest.fixture(autouse=True)
def _reset_bg_validation_globals():
    """Reset module-level bg-validation state before each test."""
    from xonsh import pyghooks as ph

    ph._cmd_valid_cache.clear()
    ph._pending_cmds.clear()
    ph._validation_gen = 0
    ph._ptk_app = None
    yield
    ph._cmd_valid_cache.clear()
    ph._pending_cmds.clear()
    ph._validation_gen = 0
    ph._ptk_app = None


def test_stale_gen_still_caches():
    from xonsh import pyghooks as ph

    # Simulate: a command was scheduled at gen=1, but by the time
    # the bg thread runs, gen has moved to 5 (new keystrokes).
    ph._pending_cmds.add("python3")
    ph._validation_gen = 5

    stale_gen = 1

    with patch.object(ph, "locate_executable", return_value="/usr/bin/python3"):
        ph._run_bg_validation(stale_gen)

    # Result MUST be in cache despite stale gen
    assert "python3" in ph._cmd_valid_cache
    assert ph._cmd_valid_cache["python3"] is True


def test_stale_gen_skips_invalidation():
    from xonsh import pyghooks as ph

    mock_app = MagicMock()
    ph._ptk_app = mock_app
    ph._pending_cmds.add("git")
    ph._validation_gen = 5

    stale_gen = 1

    with patch.object(ph, "locate_executable", return_value="/usr/bin/git"):
        ph._run_bg_validation(stale_gen)

    assert ph._cmd_valid_cache["git"] is True
    # invalidate() must NOT be called — gen is stale
    mock_app.invalidate.assert_not_called()


def test_current_gen_caches_and_invalidates():
    from xonsh import pyghooks as ph

    mock_app = MagicMock()
    mock_app.layout.find_all_controls.return_value = []
    ph._ptk_app = mock_app
    ph._pending_cmds.add("ls")
    ph._validation_gen = 3

    current_gen = 3

    with patch.object(ph, "locate_executable", return_value="/bin/ls"):
        ph._run_bg_validation(current_gen)

    assert ph._cmd_valid_cache["ls"] is True
    mock_app.invalidate.assert_called_once()


# --- PTK-only style modifier sanitization (#6387) ---------------------------


@pytest.fixture
def xs_LS_COLORS(xession, os_env, monkeypatch):
    """Xonsh environment including default LS_COLORS."""
    monkeypatch.setattr(xession, "env", os_env)
    xession.env["LS_COLORS"] = LsColors(LsColors.default_settings)
    xession.env["INTENSIFY_COLORS_ON_WIN"] = False
    xession.shell.shell_type = "prompt_toolkit"
    xession.shell.shell.styler = XonshStyle()
    yield xession


@pytest.mark.parametrize(
    "value, expected",
    [
        ("blink", ""),
        ("blink ansired", "ansired"),
        ("bold blink ansired", "bold ansired"),
        ("bold reverse hidden ansired", "bold ansired"),
        ("bold strike ansired", "bold ansired"),
        ("bold ansired", "bold ansired"),
        ("", ""),
        ("noinherit", "noinherit"),
    ],
)
def test_strip_ptk_specific_modifiers(value, expected):
    from xonsh.pyghooks import _strip_ptk_specific_modifiers

    assert _strip_ptk_specific_modifiers(value) == expected


def test_xonsh_style_proxy_strips_ptk_modifiers_from_ls_colors(xs_LS_COLORS):
    """``xonsh_style_proxy`` must sanitize PTK-only modifiers so pygments'
    ``StyleMeta`` does not raise ``AssertionError: wrong color format``.
    """
    from xonsh.pyghooks import (
        PTK_SPECIFIC_VALUES,
        color_token_by_name,
        xonsh_style_proxy,
    )

    xs = XonshStyle()
    # ANSI codes 5 (slow blink), 7 (reverse), 8 (hidden), 9 (strike) on red fg
    blink_token = color_token_by_name(("SLOWBLINK_RED",), xs.styles)
    reverse_token = color_token_by_name(("INVERT_RED",), xs.styles)
    hidden_token = color_token_by_name(("CONCEAL_RED",), xs.styles)
    strike_token = color_token_by_name(("STRIKETHROUGH_RED",), xs.styles)

    # Pre-condition: the live style cache does carry PTK-only modifiers
    assert "blink" in xs.styles[blink_token]

    # Building the proxy must not raise ``AssertionError`` from
    # pygments.style.colorformat — this is the actual bug.
    proxy = xonsh_style_proxy(xs)

    for token in (blink_token, reverse_token, hidden_token, strike_token):
        sanitized = proxy.styles[token]
        for modifier in PTK_SPECIFIC_VALUES:
            assert modifier not in sanitized.split(), (
                f"PTK-only modifier {modifier!r} leaked into pygments styles "
                f"for {token}: {sanitized!r}"
            )
        # Color information must be preserved
        assert "ansired" in sanitized
