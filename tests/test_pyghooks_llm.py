"""LLM-generated tests for ``xonsh/pyghooks.py``.

Currently covers:

* bg-validation state machine — ``_run_bg_validation`` must always
  populate ``_cmd_valid_cache``, even when the generation token is stale.
* PTK-only style modifier sanitization — regression for
  https://github.com/xonsh/xonsh/issues/6387 (``LS_COLORS`` carrying ANSI
  blink/reverse/hidden/strike codes used to crash pygments' ``StyleMeta``
  with ``AssertionError: wrong color format 'blink'`` at shell startup).
* Plugin-mode lenient highlighting — when ``XonshLexer`` is loaded as a
  pygments entry point outside a live xonsh session (Sphinx,
  nbconvert, jupyter), runtime checks for ``$VAR`` / subprocess
  commands / ``@()`` names cannot succeed, so the lexer must emit the
  optimistic token instead of flooding rendered output with Error
  markers.
* File-color readability guard — regression for
  https://github.com/xonsh/xonsh/issues/6516 (styles like ``rrt`` that
  collapse several ANSI names onto one hex used to render device/orphan/
  setgid file colors as fg-on-identical-bg, i.e. invisible).
"""

from unittest.mock import MagicMock, patch

import pytest

from xonsh.environ import LsColors
from xonsh.pyghooks import Token, XonshLexer, XonshStyle


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


@pytest.fixture
def plugin_mode_lexer(xession, monkeypatch):
    """Reproduce the state the lexer sees when loaded as a pygments
    plugin outside a live xonsh session (Sphinx, nbconvert, jupyter):
    ``XSH.commands_cache`` is None, ``XSH.env`` is the empty mock, and
    ``XSH.ctx`` is None. ``_is_plugin_mode`` keys off
    ``commands_cache is None``."""
    monkeypatch.setattr(xession, "commands_cache", None)
    monkeypatch.setattr(xession, "env", None)
    monkeypatch.setattr(xession, "ctx", None)
    return XonshLexer()


@pytest.mark.parametrize(
    "code",
    [
        "$THIS_VAR_DOES_NOT_EXIST = 1",
        "$ANOTHER_UNKNOWN.append('/x')",
        "$(unknown_cmd_xyz arg1 arg2)",
        "echo @(undefined_name)",
    ],
)
def test_plugin_mode_no_error_tokens(plugin_mode_lexer, code):
    """Without a live session, runtime checks for ``$VAR`` / subprocess
    commands / ``@()`` names cannot succeed (no env, no commands cache,
    no ctx).  In that mode the lexer must fall back to the optimistic
    token instead of marking everything as Error — otherwise rendered
    docs / notebooks are flooded with red error markers around tokens
    that are perfectly valid xonsh code (regression for Sphinx-rendered
    ``.xsh`` snippets in the docs build)."""
    tokens = list(plugin_mode_lexer.get_tokens(code))
    err_values = [v for t, v in tokens if t is Token.Error]
    assert err_values == [], f"{code!r}: unexpected Error tokens {err_values!r}"


def test_plugin_mode_keeps_python_lexing(plugin_mode_lexer):
    """Plugin-mode lenience must not switch the lexer into ``subproc``
    state for plain Python source.  The leading ``#`` of a comment
    matches ``COMMAND_TOKEN_RE`` and would otherwise be promoted to
    ``Name.Builtin``, leaving the rest of the file lexed as a
    subprocess command line (brackets become Error, etc.)."""
    code = "# adjust some paths\n$PATH.append('/foo')\n"
    tokens = list(plugin_mode_lexer.get_tokens(code))
    assert any(t is Token.Comment.Single for t, _ in tokens), (
        f"comment was not preserved: {tokens!r}"
    )
    assert all(t is not Token.Error for t, _ in tokens), tokens


def test_unknown_env_var_still_error_in_live_session(xession):
    """In a real session ``XSH.commands_cache`` is set, so the lexer
    keeps the strict check — a typo in a ``$VAR`` reference is still
    surfaced as Error.  Regression guard for the plugin-mode fix."""
    assert getattr(xession, "commands_cache", None) is not None
    lexer = XonshLexer()
    tokens = list(lexer.get_tokens("$THIS_VAR_DOES_NOT_EXIST = 1\n"))
    err_values = [v for t, v in tokens if t is Token.Error]
    assert "$THIS_VAR_DOES_NOT_EXIST" in err_values


# ---------------------------------------------------------------------------
# Readability guard for file colors -- regression for
# https://github.com/xonsh/xonsh/issues/6516.
#
# Some built-in styles map several distinct ANSI color names onto a single
# hex (e.g. ``rrt`` resolves BLACK, RED and YELLOW all to ``#ff0000``).  A
# file-type color that combines a foreground and background name -- block
# devices, fifos, orphan links, setgid files, ... -- then renders as e.g.
# red-on-red and is invisible.  ``_join_fg_bg`` drops the background when it
# collides with the foreground.
# ---------------------------------------------------------------------------


def test_join_fg_bg_drops_colliding_background():
    from xonsh.pyghooks import _join_fg_bg

    # identical fg/bg -> background dropped, foreground + modifiers preserved
    assert _join_fg_bg("bg:#ff0000", "#ff0000") == "#ff0000"
    assert _join_fg_bg("bg:#ff0000", "bold #ff0000") == "bold #ff0000"
    # order-independent: the foreground piece may come first
    assert _join_fg_bg("bold #ff0000", "bg:#ff0000") == "bold #ff0000"


def test_join_fg_bg_preserves_distinct_colors():
    from xonsh.pyghooks import _join_fg_bg

    assert _join_fg_bg("bg:#ff0000", "#00ff00") == "bg:#ff0000 #00ff00"
    # a reset/default background is not a hex color -> never a collision
    assert _join_fg_bg("bg:ansidefault", "#ff0000") == "bg:ansidefault #ff0000"
    assert _join_fg_bg("noinherit", "#ff0000") == "noinherit #ff0000"


def test_join_fg_bg_collision_is_case_and_shorthand_insensitive():
    from xonsh.pyghooks import _join_fg_bg

    # some styles (vim, vs) store hexes uppercase
    assert _join_fg_bg("bg:#FF0000", "#ff0000") == "#ff0000"
    # #RGB shorthand equals its #RRGGBB expansion
    assert _join_fg_bg("bg:#f00", "#ff0000") == "#ff0000"


@pytest.mark.parametrize(
    "name, exp",
    [
        # rrt maps BLACK, RED and YELLOW all to #ff0000
        ("BACKGROUND_BLACK__YELLOW", "#ff0000"),  # bd, cd, pi
        ("BACKGROUND_BLACK__BOLD_YELLOW", "bold #ff0000"),
        ("BACKGROUND_BLACK__RED", "#ff0000"),  # or
        # distinct colors are left untouched
        ("BACKGROUND_BLACK__GREEN", "bg:#ff0000 #00ff00"),
    ],
)
def test_code_by_name_guards_invisible_rrt_colors(name, exp):
    from xonsh.pyghooks import STYLES, code_by_name

    assert code_by_name(name, dict(STYLES["rrt"])) == exp


def test_color_token_by_name_drops_colliding_background():
    """The runtime file-color path (used by ``on_lscolors_change`` and
    ``XonshStyle``) must not cache a fg==bg style for device files."""
    from xonsh.pyghooks import STYLES, Color, color_token_by_name

    styles = dict(STYLES["rrt"])
    ct = color_token_by_name(("BACKGROUND_BLACK", "YELLOW"), styles)
    assert ct == Color.BACKGROUND_BLACK__YELLOW
    assert "bg:" not in styles[ct]
    assert styles[ct] == "#ff0000"


def test_no_builtin_style_renders_invisible_file_colors():
    """No built-in style may resolve a fg+bg file-type color to fg==bg."""
    from xonsh.pyghooks import STYLES, code_by_name

    combos = sorted(
        {"__".join(v) for v in LsColors.default_settings.values() if len(v) == 2}
    )

    def fg_bg(code):
        fg = bg = None
        for tok in code.split():
            if tok.startswith("bg:#"):
                bg = tok[3:].lower()
            elif tok.startswith("#"):
                fg = tok.lower()
        return fg, bg

    offenders = []
    for style_name in STYLES:
        for combo in combos:
            fg, bg = fg_bg(code_by_name(combo, dict(STYLES[style_name])))
            if fg and bg and fg == bg:
                offenders.append((style_name, combo))
    assert not offenders, f"invisible fg==bg file colors: {offenders}"
