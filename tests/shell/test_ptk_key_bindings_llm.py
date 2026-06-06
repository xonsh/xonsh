"""Tests for the eager vi <Esc> bindings and key-sequence timeouts.

Regression tests for https://github.com/xonsh/xonsh/issues/6507: a lone
<Esc> in vi mode used to wait ``ttimeoutlen`` (0.5s, vt100 parser) plus
``timeoutlen`` (1s, key processor waiting for a possible continuation of
the ``(Escape, ControlJ)`` binding) before leaving insert mode.
"""

import pytest
from prompt_toolkit.application.current import set_app
from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.keys import Keys


@pytest.fixture
def ptk_app(ptk_shell):
    """The shell's ptk application with xonsh key bindings installed.

    ``singleline()`` passes the merged key bindings to ``prompt()`` on
    every prompt; install them on the session the same way so the key
    processor sees them. ``timeoutlen`` is disabled because the auto
    flush timer needs a running event loop.
    """
    _, _, shell = ptk_shell
    shell.prompter.key_bindings = shell._key_bindings_merge
    app = shell.prompter.app
    app.timeoutlen = None
    # Buffer.on_text_changed handlers schedule async completion and
    # auto-suggest coroutines; there is no running event loop in tests.
    app.create_background_task = lambda coro: coro.close()
    return app


def press_escape(app):
    app.key_processor.feed(KeyPress(Keys.Escape))
    app.key_processor.process_keys()


def test_vi_escape_has_eager_binding(ptk_shell):
    _, _, shell = ptk_shell
    bindings = shell.key_bindings.get_bindings_for_keys((Keys.Escape,))
    assert any(b.eager() for b in bindings)


def test_esc_leaves_vi_insert_mode_without_flush(ptk_app):
    """<Esc> must be handled from the very first ``process_keys`` call —
    not stay buffered as a possible prefix of ``(Escape, ControlJ)``."""
    ptk_app.editing_mode = EditingMode.VI
    ptk_app.vi_state.input_mode = InputMode.INSERT
    with set_app(ptk_app):
        press_escape(ptk_app)
        assert ptk_app.vi_state.input_mode == InputMode.NAVIGATION
        assert ptk_app.key_processor.key_buffer == []


def test_esc_leaves_vi_replace_mode_without_flush(ptk_app):
    ptk_app.editing_mode = EditingMode.VI
    ptk_app.vi_state.input_mode = InputMode.REPLACE
    with set_app(ptk_app):
        press_escape(ptk_app)
        assert ptk_app.vi_state.input_mode == InputMode.NAVIGATION
        assert ptk_app.key_processor.key_buffer == []


def test_esc_stays_buffered_in_emacs_mode(ptk_app):
    """In emacs mode <Esc> is a prefix of Meta bindings (escape-b,
    escape-f, ...) and must keep waiting for a continuation — the eager
    bindings are scoped to vi mode only."""
    ptk_app.editing_mode = EditingMode.EMACS
    with set_app(ptk_app):
        press_escape(ptk_app)
        assert [kp.key for kp in ptk_app.key_processor.key_buffer] == [Keys.Escape]


def test_esc_cancels_completion_menu_and_stays_in_insert_mode(ptk_app, xession):
    """With the completions menu open and $COMPLETIONS_CONFIRM set, <Esc>
    cancels the menu without leaving insert mode (and without waiting for
    a possible longer match)."""
    assert xession.env.get("COMPLETIONS_CONFIRM")
    ptk_app.editing_mode = EditingMode.VI
    ptk_app.vi_state.input_mode = InputMode.INSERT
    buff = ptk_app.current_buffer
    buff.complete_state = CompletionState(original_document=buff.document)
    with set_app(ptk_app):
        press_escape(ptk_app)
        assert buff.complete_state is None
        assert ptk_app.vi_state.input_mode == InputMode.INSERT
        assert ptk_app.key_processor.key_buffer == []


def test_esc_ctrl_j_still_executes_block(ptk_app):
    """The ``(Escape, ControlJ)`` execute-block binding must keep working
    in emacs mode, where no eager <Esc> binding shadows it."""
    ptk_app.editing_mode = EditingMode.EMACS
    accepted = []
    ptk_app.current_buffer.accept_handler = lambda buff: accepted.append(buff.text)
    with set_app(ptk_app):
        ptk_app.current_buffer.text = "echo hi"
        ptk_app.key_processor.feed(KeyPress(Keys.Escape))
        ptk_app.key_processor.feed(KeyPress(Keys.ControlJ))
        ptk_app.key_processor.process_keys()
    assert accepted == ["echo hi"]


def test_singleline_applies_default_key_timeouts(ptk_shell):
    """Without the (unregistered) env vars set, singleline() must lower
    ptk's ttimeoutlen from 0.5 to 0.05 and keep timeoutlen at 1.0."""
    _, _, shell = ptk_shell
    shell.prompter.prompt = lambda **kwargs: "echo ok"
    assert shell.singleline() == "echo ok"
    assert shell.prompter.app.ttimeoutlen == 0.05
    assert shell.prompter.app.timeoutlen == 1.0


@pytest.mark.parametrize("value", [0.123, "0.123"], ids=["float", "str"])
def test_singleline_applies_key_timeouts_from_env(ptk_shell, xession, value):
    """$XONSH_PTK_TTIMEOUTLEN / $XONSH_PTK_TIMEOUTLEN are not registered
    in environ.py, so values inherited from os.environ (or set with -D)
    are strings — singleline() must coerce them to float."""
    _, _, shell = ptk_shell
    xession.env["XONSH_PTK_TTIMEOUTLEN"] = value
    xession.env["XONSH_PTK_TIMEOUTLEN"] = value
    shell.prompter.prompt = lambda **kwargs: "echo ok"
    assert shell.singleline() == "echo ok"
    assert shell.prompter.app.ttimeoutlen == 0.123
    assert shell.prompter.app.timeoutlen == 0.123
