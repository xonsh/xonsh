"""Tests for xonsh.debug.XonshDebug and $XONSH_DEBUG_BREAKPOINT_ENGINE."""

import builtins
import importlib
import sys
import types

import pytest

from xonsh.debug import (
    CANONIC_BREAKPOINT_ENGINES,
    XonshDebug,
    XonshDebugQuit,
    is_breakpoint_engine,
    to_breakpoint_engine,
)

# ---------------------------------------------------------------------------
# validator helpers in tools.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", sorted(CANONIC_BREAKPOINT_ENGINES))
def test_is_breakpoint_engine_accepts_canonical(value):
    assert is_breakpoint_engine(value)


@pytest.mark.parametrize("value", ["", "foo", 1, None, "PDB"])
def test_is_breakpoint_engine_rejects_other(value):
    assert not is_breakpoint_engine(value)


def test_to_breakpoint_engine_passthrough():
    for value in CANONIC_BREAKPOINT_ENGINES:
        assert to_breakpoint_engine(value) == value


def test_to_breakpoint_engine_lowercases():
    assert to_breakpoint_engine("PDB") == "pdb"
    assert to_breakpoint_engine("Auto") == "auto"


def test_to_breakpoint_engine_unknown_falls_back():
    with pytest.warns(RuntimeWarning):
        assert to_breakpoint_engine("nonsense") == "auto"


# ---------------------------------------------------------------------------
# engine resolution
# ---------------------------------------------------------------------------


@pytest.fixture
def dbg():
    return XonshDebug()


@pytest.fixture
def fake_specs(monkeypatch):
    """Control the result of ``importlib.util.find_spec`` per engine."""

    def make(available):
        def find_spec(name):
            return object() if name in available else None

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)

    return make


@pytest.fixture
def isolate_env(monkeypatch):
    """Detach the real session so ``_env_default`` returns ``'auto'``."""
    monkeypatch.setattr(
        builtins, "__xonsh__", types.SimpleNamespace(env=None), raising=False
    )


def test_resolve_auto_prefers_pdbp(dbg, fake_specs, isolate_env):
    fake_specs({"pdbp", "ipdb", "pdb"})
    assert dbg._resolve_engine("auto") == "pdbp"


def test_resolve_auto_falls_to_ipdb(dbg, fake_specs, isolate_env):
    fake_specs({"ipdb", "pdb"})
    assert dbg._resolve_engine("auto") == "ipdb"


def test_resolve_auto_falls_to_pdb(dbg, fake_specs, isolate_env):
    fake_specs({"pdb"})
    assert dbg._resolve_engine("auto") == "pdb"


def test_resolve_auto_falls_to_eval_when_none_found(dbg, fake_specs, isolate_env):
    fake_specs(set())
    assert dbg._resolve_engine("auto") == "eval"


def test_resolve_explicit_engine_passes_through(dbg, fake_specs, isolate_env):
    # Availability of the module is not consulted for an explicit choice.
    fake_specs(set())
    assert dbg._resolve_engine("pdb") == "pdb"
    assert dbg._resolve_engine("eval") == "eval"


def test_resolve_unknown_engine_raises(dbg):
    with pytest.raises(ValueError, match="Unknown breakpoint engine"):
        dbg._resolve_engine("gdb")


# ---------------------------------------------------------------------------
# env var interaction
# ---------------------------------------------------------------------------


def test_env_var_overrides_auto(dbg, xession, fake_specs):
    xession.env["XONSH_DEBUG_BREAKPOINT_ENGINE"] = "pdb"
    # pdbp would win the priority walk, but env var forces pdb.
    fake_specs({"pdbp", "ipdb", "pdb"})
    assert dbg._resolve_engine("auto") == "pdb"


def test_explicit_arg_beats_env_var(dbg, xession, fake_specs):
    xession.env["XONSH_DEBUG_BREAKPOINT_ENGINE"] = "pdb"
    fake_specs({"pdbp", "ipdb", "pdb"})
    assert dbg._resolve_engine("ipdb") == "ipdb"


def test_env_var_auto_walks_priority(dbg, xession, fake_specs):
    xession.env["XONSH_DEBUG_BREAKPOINT_ENGINE"] = "auto"
    fake_specs({"ipdb", "pdb"})
    assert dbg._resolve_engine("auto") == "ipdb"


# ---------------------------------------------------------------------------
# breakpoint() dispatch — frame handling
# ---------------------------------------------------------------------------


def _stand_in_module(name, recorder):
    """Build a stub debugger module that records the frame arg."""
    mod = types.ModuleType(name)

    if name == "pdb":
        # pdb must be invoked via Pdb().set_trace(frame)
        class Pdb:
            def set_trace(self, frame):
                recorder.append(("pdb", frame))

        mod.Pdb = Pdb  # type: ignore[attr-defined]
    else:
        # ipdb / pdbp expose a module-level set_trace(frame=...)
        def set_trace(frame=None):
            recorder.append((name, frame))

        mod.set_trace = set_trace  # type: ignore[attr-defined]

    return mod


@pytest.fixture
def debugger_recorder(monkeypatch):
    """Install stub pdb/ipdb/pdbp and record invocations."""
    recorder: list = []
    stubs = {name: _stand_in_module(name, recorder) for name in ("pdbp", "ipdb", "pdb")}
    real_import = importlib.import_module

    def fake_import(name, *a, **kw):
        if name in stubs:
            return stubs[name]
        return real_import(name, *a, **kw)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    return recorder


def test_breakpoint_dispatches_to_pdb_with_caller_frame(dbg, debugger_recorder):
    expected_line = sys._getframe().f_lineno + 1
    dbg.breakpoint(engine="pdb")
    assert len(debugger_recorder) == 1
    engine, frame = debugger_recorder[0]
    assert engine == "pdb"
    # The frame belongs to *this* function, not to dbg.breakpoint itself.
    assert frame.f_code is sys._getframe().f_code
    # Line just after entering the test's call site.
    assert frame.f_lineno >= expected_line


def test_breakpoint_dispatches_to_ipdb(dbg, debugger_recorder):
    dbg.breakpoint(engine="ipdb")
    assert debugger_recorder == [("ipdb", sys._getframe())] or (
        debugger_recorder[0][0] == "ipdb"
    )


def test_breakpoint_dispatches_to_pdbp(dbg, debugger_recorder):
    dbg.breakpoint(engine="pdbp")
    assert debugger_recorder[0][0] == "pdbp"


def test_breakpoint_auto_uses_first_available(
    dbg, debugger_recorder, fake_specs, isolate_env
):
    fake_specs({"ipdb", "pdb"})  # pdbp missing
    dbg.breakpoint(engine="auto")
    assert debugger_recorder[0][0] == "ipdb"


def test_breakpoint_unknown_engine_raises(dbg):
    with pytest.raises(ValueError):
        dbg.breakpoint(engine="gdb")


@pytest.mark.parametrize("engine", ["pdb", "ipdb", "pdbp"])
def test_breakpoint_uses_explicit_frame(dbg, debugger_recorder, engine):
    """An explicit ``frame=`` overrides ``sys._getframe(1)``."""

    def helper():
        return sys._getframe()

    helper_frame = helper()
    dbg.breakpoint(engine=engine, frame=helper_frame)
    assert len(debugger_recorder) == 1
    recorded_engine, recorded_frame = debugger_recorder[0]
    assert recorded_engine == engine
    # The engine received the explicit frame, not breakpoint()'s own caller.
    assert recorded_frame is helper_frame
    assert recorded_frame.f_code is helper.__code__


@pytest.mark.parametrize("engine", ["pdb", "ipdb", "pdbp"])
def test_breakpoint_default_frame_is_caller(dbg, debugger_recorder, engine):
    """Omitting ``frame=`` must still default to the immediate caller."""
    dbg.breakpoint(engine=engine)
    assert len(debugger_recorder) == 1
    # Frame belongs to *this* test function, not to dbg.breakpoint itself.
    assert debugger_recorder[0][1].f_code is sys._getframe().f_code


# ---------------------------------------------------------------------------
# eval REPL — plain Python
# ---------------------------------------------------------------------------


def _feed_lines(monkeypatch, lines):
    """Replace builtins.input with an iterator over ``lines``."""
    it = iter(lines)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr(builtins, "input", fake_input)


def test_eval_repl_python_continue_returns(dbg, monkeypatch, capsys, isolate_env):
    _feed_lines(monkeypatch, ["c"])
    dbg.breakpoint(engine="eval")  # returns without raising
    out = capsys.readouterr().out
    assert "python REPL" in out


def test_eval_repl_python_prints_expression(dbg, monkeypatch, capsys, isolate_env):
    _feed_lines(monkeypatch, ["1 + 2", "c"])
    dbg.breakpoint(engine="eval")
    out = capsys.readouterr().out
    assert "3" in out


def test_eval_repl_python_runs_statement(dbg, monkeypatch, capsys, isolate_env):
    _feed_lines(monkeypatch, ["marker = 41 + 1", "marker", "c"])
    dbg.breakpoint(engine="eval")
    out = capsys.readouterr().out
    assert "42" in out


def test_eval_repl_python_recovers_from_error(dbg, monkeypatch, capsys, isolate_env):
    _feed_lines(monkeypatch, ["1/0", "2 + 2", "c"])
    dbg.breakpoint(engine="eval")
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "ZeroDivisionError" in combined
    assert "4" in captured.out


def test_eval_repl_python_eof_continues(dbg, monkeypatch, capsys, isolate_env):
    # EOFError on first read should behave like 'continue', not abort.
    _feed_lines(monkeypatch, [])
    dbg.breakpoint(engine="eval")  # returns without raising


@pytest.mark.parametrize("cmd", ["c", "cont", "continue"])
def test_eval_repl_continue_aliases(dbg, monkeypatch, cmd, isolate_env):
    _feed_lines(monkeypatch, [cmd])
    dbg.breakpoint(engine="eval")  # returns


@pytest.mark.parametrize("cmd", ["exit", "quit", "q"])
def test_eval_repl_abort_aliases_raise(dbg, monkeypatch, cmd, isolate_env):
    _feed_lines(monkeypatch, [cmd])
    with pytest.raises(XonshDebugQuit):
        dbg.breakpoint(engine="eval")


def test_eval_repl_abort_runs_after_computation(dbg, monkeypatch, capsys, isolate_env):
    # User evaluates an expression, then aborts.
    _feed_lines(monkeypatch, ["1 + 2", "exit"])
    with pytest.raises(XonshDebugQuit):
        dbg.breakpoint(engine="eval")
    out = capsys.readouterr().out
    assert "3" in out


def test_eval_repl_uses_explicit_frame(dbg, monkeypatch, capsys, isolate_env):
    """The eval REPL evaluates against the passed frame, not the caller."""
    sentinel = "unique-eval-frame-marker-7q"

    def helper():
        my_sentinel = sentinel  # noqa: F841 - read via frame inspection
        return sys._getframe()

    helper_frame = helper()
    _feed_lines(monkeypatch, ["my_sentinel", "c"])
    dbg.breakpoint(engine="eval", frame=helper_frame)
    out = capsys.readouterr().out
    assert sentinel in out


# ---------------------------------------------------------------------------
# execer REPL
# ---------------------------------------------------------------------------


class _ExecerStub:
    def __init__(self):
        self.calls: list = []
        self.frames: list = []

    def exec(self, input, mode="exec", glbs=None, locs=None, **kw):
        self.calls.append((input, mode))
        self.frames.append((glbs, locs))


def _install_session_with_execer(monkeypatch, execer):
    monkeypatch.setattr(
        builtins,
        "__xonsh__",
        types.SimpleNamespace(env=None, execer=execer),
        raising=False,
    )


def test_execer_repl_uses_execer(dbg, monkeypatch, capsys):
    stub = _ExecerStub()
    _install_session_with_execer(monkeypatch, stub)
    _feed_lines(monkeypatch, ["echo hi", "c"])
    dbg.breakpoint(engine="execer")
    out = capsys.readouterr().out
    assert "execer REPL" in out
    assert stub.calls == [("echo hi", "single")]


def test_execer_repl_shows_traceback_on_error(dbg, monkeypatch, capsys):
    class Boom(_ExecerStub):
        def exec(self, input, mode="exec", glbs=None, locs=None, **kw):
            raise RuntimeError("bang")

    _install_session_with_execer(monkeypatch, Boom())
    _feed_lines(monkeypatch, ["anything", "c"])
    dbg.breakpoint(engine="execer")
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "RuntimeError" in combined
    assert "bang" in combined


def test_execer_repl_requires_execer(dbg, monkeypatch, isolate_env):
    # isolate_env leaves __xonsh__ with env=None, no execer attribute.
    with pytest.raises(RuntimeError, match="requires an active xonsh session"):
        dbg.breakpoint(engine="execer")


def test_eval_repl_ignores_execer(dbg, monkeypatch, capsys):
    """engine='eval' must NOT route through execer even when present."""
    stub = _ExecerStub()
    _install_session_with_execer(monkeypatch, stub)
    _feed_lines(monkeypatch, ["1 + 1", "c"])
    dbg.breakpoint(engine="eval")
    out = capsys.readouterr().out
    assert "python REPL" in out
    assert stub.calls == []  # execer was never called
    assert "2" in out  # python eval produced the result


def test_execer_repl_uses_explicit_frame(dbg, monkeypatch, capsys):
    """Execer REPL must run against the explicit frame's globals/locals."""
    stub = _ExecerStub()
    _install_session_with_execer(monkeypatch, stub)

    def helper():
        helper_local = "execer-helper-local-marker"  # noqa: F841 - via frame
        return sys._getframe()

    helper_frame = helper()
    _feed_lines(monkeypatch, ["echo hi", "c"])
    dbg.breakpoint(engine="execer", frame=helper_frame)

    assert stub.frames, "stub.exec was not invoked"
    glbs, locs = stub.frames[0]
    # Module globals are a stable dict — identity holds.
    assert glbs is helper_frame.f_globals
    # Locals must contain the helper's local variable.
    assert locs.get("helper_local") == "execer-helper-local-marker"


# ---------------------------------------------------------------------------
# execer/eval in the auto priority walk
# ---------------------------------------------------------------------------


def test_resolve_auto_falls_to_execer_when_session_has_one(
    dbg, fake_specs, monkeypatch
):
    fake_specs(set())  # no external debuggers installed
    _install_session_with_execer(monkeypatch, _ExecerStub())
    assert dbg._resolve_engine("auto") == "execer"


def test_resolve_auto_final_fallback_is_eval(dbg, fake_specs, isolate_env):
    # No debuggers, no execer attached.
    fake_specs(set())
    assert dbg._resolve_engine("auto") == "eval"


# ---------------------------------------------------------------------------
# per-engine hint line
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("engine", ["pdb", "ipdb", "pdbp"])
def test_external_debugger_prints_hint(dbg, debugger_recorder, capsys, engine):
    dbg.breakpoint(engine=engine)
    out = capsys.readouterr().out
    assert f"BREAKPOINT WITH {engine!r}" in out
    assert engine in out  # engine name appears in the hint line
    assert "'c'" in out and "'q'" in out  # continue + quit


def test_eval_engine_prints_hint(dbg, monkeypatch, capsys, isolate_env):
    _feed_lines(monkeypatch, ["c"])
    dbg.breakpoint(engine="eval")
    out = capsys.readouterr().out
    assert "eval REPL" in out
    assert "'c'/'continue'" in out
    assert "'q'/'quit'/'exit'" in out


def test_execer_engine_prints_hint(dbg, monkeypatch, capsys):
    _install_session_with_execer(monkeypatch, _ExecerStub())
    _feed_lines(monkeypatch, ["c"])
    dbg.breakpoint(engine="execer")
    out = capsys.readouterr().out
    assert "execer REPL" in out
    assert "'c'/'continue'" in out
    assert "'q'/'quit'/'exit'" in out


# ---------------------------------------------------------------------------
# __tracebackhide__ — parity with hand-rolled pdbp helpers
# ---------------------------------------------------------------------------


def test_intermediate_frames_are_tracebackhidden(dbg, monkeypatch):
    """pdbp/pytest look at frame.f_locals['__tracebackhide__'] to hide a
    frame from `where`/`u`/`d` listings. Our wrapper frames between the
    user's code and the real debugger must set the flag so the frame
    chain stays clean (matching the common pdbp pause() recipe).
    """
    captured: dict = {}

    def fake_set_trace(frame=None):
        # Walk up from the user's frame toward the root, collecting
        # __tracebackhide__ from every frame in between. The 'frame'
        # arg is the user's frame (the outermost caller), so we scan
        # from the call site back up to include our wrapper frames.
        seen = {}
        f = sys._getframe()  # fake_set_trace itself
        while f is not None:
            name = f.f_code.co_name
            seen[name] = f.f_locals.get("__tracebackhide__", False)
            f = f.f_back
        captured.update(seen)

    fake_pdbp = types.ModuleType("pdbp")
    fake_pdbp.set_trace = fake_set_trace  # type: ignore[attr-defined]
    real_import = importlib.import_module

    def fake_import(name, *a, **kw):
        if name == "pdbp":
            return fake_pdbp
        return real_import(name, *a, **kw)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    dbg.breakpoint(engine="pdbp")

    # Each of our wrapper methods must be tracebackhidden.
    assert captured.get("breakpoint") is True
    assert captured.get("_break_at") is True
    assert captured.get("_start_debugger") is True


def test_hook_frame_is_tracebackhidden(dbg, restore_breakpointhook, monkeypatch):
    """The sys.breakpointhook closure is also a wrapper frame — it must
    be tracebackhidden so pdbp's `where` skips it too.
    """
    seen: dict = {}

    def probing_set_trace(frame=None):
        f = sys._getframe()
        while f is not None:
            seen[f.f_code.co_name] = f.f_locals.get("__tracebackhide__", False)
            f = f.f_back

    fake_pdbp = types.ModuleType("pdbp")
    fake_pdbp.set_trace = probing_set_trace  # type: ignore[attr-defined]
    real_import = importlib.import_module

    def fake_import(name, *a, **kw):
        if name == "pdbp":
            return fake_pdbp
        return real_import(name, *a, **kw)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    dbg.replace_builtin_breakpoint(engine="pdbp")
    breakpoint()  # noqa: T100 - feature under test
    assert seen.get("hook") is True


# ---------------------------------------------------------------------------
# replace_builtin_breakpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_breakpointhook():
    """Restore sys.breakpointhook after the test."""
    original = sys.breakpointhook
    yield
    sys.breakpointhook = original


def test_replace_builtin_breakpoint_installs_hook(
    dbg, restore_breakpointhook, debugger_recorder
):
    dbg.replace_builtin_breakpoint(engine="pdb")
    assert sys.breakpointhook is not sys.__breakpointhook__


def test_builtin_breakpoint_routes_to_debugger(
    dbg, restore_breakpointhook, debugger_recorder
):
    dbg.replace_builtin_breakpoint(engine="pdb")
    # Call the builtin breakpoint, which should fire our hook.
    breakpoint()  # noqa: T100 - this is the feature under test
    assert len(debugger_recorder) == 1
    engine, frame = debugger_recorder[0]
    assert engine == "pdb"
    # The hook must hand the *caller's* frame (this test function), not
    # the hook's own frame, to the debugger.
    assert frame.f_code is sys._getframe().f_code


def test_builtin_breakpoint_passes_through_args(
    dbg, restore_breakpointhook, debugger_recorder
):
    # PEP 553: breakpoint(*args, **kwargs) forwards to sys.breakpointhook.
    # We accept and silently ignore them — should not raise.
    dbg.replace_builtin_breakpoint(engine="pdb")
    breakpoint(1, 2, key="value")  # noqa: T100
    assert debugger_recorder[0][0] == "pdb"


def test_replace_builtin_breakpoint_honours_engine_arg(
    dbg, restore_breakpointhook, debugger_recorder
):
    dbg.replace_builtin_breakpoint(engine="ipdb")
    breakpoint()  # noqa: T100
    assert debugger_recorder[0][0] == "ipdb"


def test_builtin_breakpoint_forwards_frame(
    dbg, restore_breakpointhook, debugger_recorder
):
    """PEP 553 forwards kwargs to ``sys.breakpointhook`` — honour ``frame=``."""
    dbg.replace_builtin_breakpoint(engine="pdb")

    def helper():
        return sys._getframe()

    custom_frame = helper()
    breakpoint(frame=custom_frame)  # noqa: T100
    assert debugger_recorder[0][0] == "pdb"
    assert debugger_recorder[0][1] is custom_frame


def test_builtin_breakpoint_handles_frame_with_other_kwargs(
    dbg, restore_breakpointhook, debugger_recorder
):
    """Mixing ``frame=`` with positional/extra kwargs must not raise."""
    dbg.replace_builtin_breakpoint(engine="pdb")

    def helper():
        return sys._getframe()

    custom_frame = helper()
    breakpoint(1, 2, frame=custom_frame, key="value")  # noqa: T100
    assert debugger_recorder[0][0] == "pdb"
    assert debugger_recorder[0][1] is custom_frame


# ---------------------------------------------------------------------------
# session wiring
# ---------------------------------------------------------------------------


def test_xsh_has_debug(xession):
    assert isinstance(xession.debug, XonshDebug)
    assert xession.interface.debug is xession.debug


def test_env_var_default_is_auto(xession):
    assert xession.env.get("XONSH_DEBUG_BREAKPOINT_ENGINE") == "auto"


def test_env_var_validator_rejects_invalid(xession):
    with pytest.warns(RuntimeWarning):
        xession.env["XONSH_DEBUG_BREAKPOINT_ENGINE"] = "nonsense"
    assert xession.env["XONSH_DEBUG_BREAKPOINT_ENGINE"] == "auto"
