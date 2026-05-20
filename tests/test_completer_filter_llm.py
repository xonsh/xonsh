"""Tests for the ``on_completer_filter`` event (xonsh/completer.py)."""

import pytest

from xonsh.completer import Completer
from xonsh.completers.tools import contextual_command_completer
from xonsh.events import events
from xonsh.parsers.completion_context import CommandContext


@pytest.fixture(scope="session")
def completer():
    return Completer()


@pytest.fixture
def completers_mock(xession, monkeypatch):
    completers = {}
    monkeypatch.setattr(xession, "_completers", completers)
    return completers


def test_filter_false_skips_completer(completer, completers_mock):
    called = []

    def comp(*a):
        called.append("ran")
        return {"x"}

    completers_mock["bash"] = comp

    @events.on_completer_filter
    def _veto(completer, context, **_):
        return False

    assert completer.complete("", "", 0, 0) == ((), 0)
    assert called == []


def test_filter_true_lets_completer_run(completer, completers_mock):
    called = []

    def comp(*a):
        called.append("ran")
        return {"x"}

    completers_mock["bash"] = comp

    @events.on_completer_filter
    def _allow(completer, context, **_):
        return True

    res, _ = completer.complete("", "", 0, 0)
    assert res == ("x",)
    assert called == ["ran"]


def test_filter_none_lets_completer_run(completer, completers_mock):
    called = []

    def comp(*a):
        called.append("ran")
        return {"x"}

    completers_mock["bash"] = comp

    @events.on_completer_filter
    def _noop(completer, context, **_):
        return None

    res, _ = completer.complete("", "", 0, 0)
    assert res == ("x",)
    assert called == ["ran"]


def test_filter_any_false_vetoes(completer, completers_mock):
    called = []

    def comp(*a):
        called.append("ran")
        return {"x"}

    completers_mock["bash"] = comp

    @events.on_completer_filter
    def _allow(completer, context, **_):
        return True

    @events.on_completer_filter
    def _veto(completer, context, **_):
        return False

    assert completer.complete("", "", 0, 0) == ((), 0)
    assert called == []


def test_filter_no_handlers_is_passthrough(completer, completers_mock):
    completers_mock["bash"] = lambda *a: {"x"}
    res, _ = completer.complete("", "", 0, 0)
    assert res == ("x",)


def test_filter_handler_exception_does_not_block(completer, completers_mock):
    called = []

    def comp(*a):
        called.append("ran")
        return {"x"}

    completers_mock["bash"] = comp

    @events.on_completer_filter
    def _boom(completer, context, **_):
        raise RuntimeError("boom")

    res, _ = completer.complete("", "", 0, 0)
    assert res == ("x",)
    assert called == ["ran"]


def test_filter_receives_completer_name_command_and_context(completer, completers_mock):
    seen = []

    @contextual_command_completer
    def comp(context: CommandContext):
        return {"x"}

    completers_mock["bash"] = comp

    @events.on_completer_filter
    def _capture(completer, command, context, **_):
        seen.append((completer, command, context))
        return True

    completer.complete("p", "ls p", 3, 4, {}, multiline_text="ls p", cursor_index=4)
    assert len(seen) == 1
    name, command, ctx = seen[0]
    assert name == "bash"
    assert command == "ls"
    assert ctx is not None
    assert ctx.command is not None
    assert ctx.command.args[0].value == "ls"


def test_filter_command_is_basename_of_full_path(completer, completers_mock):
    """``/usr/bin/kubectl`` should arrive at the handler as ``kubectl``."""
    seen = []

    completers_mock["bash"] = lambda *a: {"x"}

    @events.on_completer_filter
    def _capture(command, **_):
        seen.append(command)
        return True

    completer.complete(
        "p",
        "/usr/bin/kubectl p",
        17,
        18,
        {},
        multiline_text="/usr/bin/kubectl p",
        cursor_index=18,
    )
    assert seen and seen[0] == "kubectl"


def test_filter_command_is_empty_when_no_command(completer, completers_mock):
    seen = []

    completers_mock["bash"] = lambda *a: {"x"}

    @events.on_completer_filter
    def _capture(command, **_):
        seen.append(command)
        return True

    completer.complete("", "", 0, 0)
    assert seen and seen[0] == ""


def test_filter_per_completer_selectivity(completer, completers_mock):
    """Returning False for one completer must not affect the others."""
    completers_mock["bash"] = lambda *a: {"from-bash"}
    completers_mock["path"] = lambda *a: {"from-path"}

    @events.on_completer_filter
    def _no_bash(completer, context, **_):
        if completer == "bash":
            return False

    res, _ = completer.complete("", "", 0, 0)
    assert "from-bash" not in res
    assert "from-path" in res


def test_filter_trace_reports_skip_with_handler_name(
    completer, completers_mock, xession, monkeypatch
):
    monkeypatch.setitem(xession.env, "XONSH_COMPLETER_TRACE", True)
    completers_mock["bash"] = lambda *a: {"x"}

    @events.on_completer_filter
    def _veto_for_test(completer, context, **_):
        return False

    messages = []
    monkeypatch.setattr(
        "xonsh.completer.print_above_prompt", lambda msg: messages.append(msg)
    )

    completer.complete("", "", 0, 0)
    assert any("Skipped 'bash' by on_completer_filter handler" in m for m in messages)
    assert any("_veto_for_test" in m for m in messages)
