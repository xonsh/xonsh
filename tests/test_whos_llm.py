"""Acceptance and lifecycle tests for the opt-in whos xontrib."""

from io import StringIO

from xonsh.events import events
from xonsh.xontribs import xontribs_load, xontribs_unload


def test_whos_acceptance(xonsh_session):
    ctx = xonsh_session.ctx
    ctx["rc_before"] = object()
    try:
        result = xontribs_load(["whos"])
        assert result[2] == 0, "bundled whos must load successfully"
        assert "whos" in xonsh_session.aliases, "whos must install its callable alias"
        ctx["rc_after"] = object()
        events.on_pre_cmdloop.fire()
        ctx["session_number"] = 42
        output = StringIO()
        xonsh_session.aliases["whos"]([], stdout=output)
        assert output.getvalue().splitlines() == [
            "Name\tType\tValue",
            "session_number\tint\t42",
        ]
        assert xonsh_session.ctx is ctx
    finally:
        xontribs_unload(["whos"])


def _report(session):
    output = StringIO()
    session.aliases["whos"]([], stdout=output)
    return output.getvalue()


def test_baseline_integrity_and_collection(xonsh_session):
    import gc
    import weakref

    class Value:
        pass

    ctx = xonsh_session.ctx
    value = Value()
    ref = weakref.ref(value)
    ctx.update(overwritten=value, deleted=1)
    try:
        assert xontribs_load(["whos"])[2] == 0
        events.on_pre_cmdloop.fire()
        assert ctx["overwritten"] is value
        del value
        ctx["overwritten"] = 2
        del ctx["deleted"]
        gc.collect()
        assert ref() is None
        assert _report(xonsh_session) == "No new variables.\n"
        ctx["zebra"] = [1, 2]
        ctx["alpha"] = "hello"
        before = ctx.copy()
        assert _report(xonsh_session).splitlines() == [
            "Name\tType\tValue",
            "alpha\tstr\t'hello'",
            "zebra\tlist\t[1, 2]",
        ]
        assert xonsh_session.ctx is ctx
        assert ctx.keys() == before.keys()
        assert all(ctx[key] is before[key] for key in ctx)
    finally:
        xontribs_unload(["whos"])


def test_safe_previews(xonsh_session):
    class Hostile:
        def __repr__(self):
            raise ValueError("hostile")

    class HostileType(type):
        def __getattribute__(self, name):
            if name == "__name__":
                raise ValueError("hostile type display")
            return super().__getattribute__(name)

    class BadType(metaclass=HostileType):
        pass

    class Controls:
        def __repr__(self):
            return "\n\r\t\x1b[31m\x9b\u202e" * 100

    try:
        xontribs_load(["whos"])
        events.on_pre_cmdloop.fire()
        xonsh_session.ctx.update(
            bad_type=BadType(),
            hostile=Hostile(),
            controls=Controls(),
            long="x" * 100000,
            large=list(range(10000)),
            multiline="a\nb\r\x1b",
        )
        lines = _report(xonsh_session).splitlines()
        assert len(lines) == 7
        assert [line.split("\t")[0] for line in lines[1:]] == [
            "bad_type",
            "controls",
            "hostile",
            "large",
            "long",
            "multiline",
        ]
        for line in lines[1:]:
            name, kind, preview = line.split("\t")
            assert len(preview) <= 80
            assert all(char.isprintable() for char in preview)
        assert lines[1] == "bad_type\t?\t<display failed>"
        assert "\\x1b" in lines[2]
    finally:
        xontribs_unload(["whos"])


def test_late_repeated_reload(xonsh_session):
    from xonsh.xontribs import xontribs_reload

    @events.on_pre_cmdloop
    def unrelated(**kwargs):
        pass

    xonsh_session.aliases["unrelated-whos-test"] = ["echo", "preserved"]
    unrelated_alias = xonsh_session.aliases["unrelated-whos-test"]
    events.on_pre_cmdloop.fire()
    original_handlers = set(events.on_pre_cmdloop)
    try:
        xonsh_session.ctx["earlier"] = 1
        xontribs_load(["whos"])
        installed = xonsh_session.aliases["whos"]
        xonsh_session.ctx["later"] = 2
        xontribs_load(["whos"])
        assert xonsh_session.aliases["whos"] is installed
        assert len(events.on_pre_cmdloop) == len(original_handlers) + 1
        assert "later\tint\t2" in _report(xonsh_session)
        xontribs_reload(["whos"])
        assert _report(xonsh_session) == "No new variables.\n"
        assert len(events.on_pre_cmdloop) == len(original_handlers) + 1
    finally:
        xontribs_unload(["whos"])
    assert set(events.on_pre_cmdloop) == original_handlers
    assert xonsh_session.aliases["unrelated-whos-test"] is unrelated_alias
    assert "whos" not in xonsh_session.aliases


def test_import_conflict_and_unload_before_loop(xonsh_session):
    import importlib

    before = dict(xonsh_session.aliases)
    importlib.import_module("xontrib.whos")
    assert dict(xonsh_session.aliases) == before
    xonsh_session.aliases["whos"] = ["echo", "mine"]
    existing = xonsh_session.aliases["whos"]
    handlers = set(events.on_pre_cmdloop)
    xontribs_load(["whos"])
    assert xonsh_session.aliases["whos"] is existing
    assert set(events.on_pre_cmdloop) == handlers
    xontribs_unload(["whos"])
    assert xonsh_session.aliases["whos"] is existing
    del xonsh_session.aliases["whos"]
    xontribs_load(["whos"])
    xontribs_unload(["whos"])
    events.on_pre_cmdloop.fire()
    assert set(events.on_pre_cmdloop) == handlers
    assert "whos" not in xonsh_session.aliases


def test_user_alias_changes_survive_unload(xonsh_session):
    for replacement in (["echo", "replacement"], None):
        xontribs_load(["whos"])
        if replacement is None:
            del xonsh_session.aliases["whos"]
        else:
            xonsh_session.aliases["whos"] = replacement
        xontribs_unload(["whos"])
        if replacement is None:
            assert "whos" not in xonsh_session.aliases
        else:
            assert xonsh_session.aliases["whos"] == replacement
            del xonsh_session.aliases["whos"]


def test_independent_sessions_and_gc(xonsh_session, monkeypatch):
    import gc
    import weakref

    from xonsh import xontribs
    from xonsh.aliases import Aliases
    from xonsh.built_ins import XonshSession
    from xonsh.commands_cache import CommandsCache

    events.on_pre_cmdloop.fire()
    first = xonsh_session
    second = XonshSession()
    second.commands_cache = CommandsCache(first.env, Aliases())
    second.ctx["second_baseline"] = 1
    handlers = set(events.on_pre_cmdloop)
    try:
        xontribs_load(["whos"])
        with monkeypatch.context() as patch:
            patch.setattr(xontribs, "XSH", second)
            xontribs_load(["whos"])
            second.ctx["only_second"] = 2
            # Removing the module must not lose first session's ownership state.
            xontribs_unload(["whos"])
            xontribs_load(["whos"])
        first.ctx["only_first"] = 3
        assert "only_first" in _report(first)
        assert "only_second" not in _report(first)
        assert "only_first" not in _report(second)
        ref = weakref.ref(second)
        del second
        gc.collect()
        assert ref() is None
        assert len(events.on_pre_cmdloop) == len(handlers) + 1
    finally:
        xontribs_unload(["whos"])
    assert set(events.on_pre_cmdloop) == handlers


def test_native_rc_to_cmdloop_and_lifecycle(tmp_path):
    import os
    import re
    import subprocess
    import sys

    rc = tmp_path / "rc.xsh"
    rc.write_text(
        "$PROMPT = 'WHOS_PROMPT> '\n"
        "$XONSH_HISTORY_BACKEND = 'dummy'\n"
        "assert 'whos' not in aliases\n"
        "xontrib load whos\n"
        "rc_after_load = 123\n"
        "rc_context_identity = id(__xonsh__.ctx)\n"
    )
    commands = (
        "session_variable = 42\n"
        "print('BEGIN_FIRST')\nwhos\nprint('END_FIRST')\n"
        "assert id(__xonsh__.ctx) == rc_context_identity\n"
        "xontrib reload whos\n"
        "print('BEGIN_RELOAD')\nwhos\nprint('END_RELOAD')\n"
        "xontrib unload whos\n"
        "assert 'whos' not in aliases\n"
        "before_late = 3\nxontrib load whos\nafter_late = 4\n"
        "print('BEGIN_LATE')\nwhos\nprint('END_LATE')\n"
        "xontrib unload whos\nassert 'whos' not in aliases\nexit\n"
    )
    env = dict(os.environ)
    env.update(
        XONSH_DATA_DIR=str(tmp_path / "data"),
        XONSH_CACHE_DIR=str(tmp_path / "cache"),
        XONTRIBS_AUTOLOAD_DISABLED="1",
        TERM="dumb",
    )
    result = subprocess.run(
        [sys.executable, "-m", "xonsh", "--rc", str(rc), "-i", "--shell-type", "dumb"],
        input=commands,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert "AssertionError" not in result.stderr, result.stderr
    # Readline echoes highlighted input with piped stdin. Keep only actual
    # report lines, after stripping its ANSI highlighting and prompt.
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.stdout)
    output = output.replace("WHOS_PROMPT> ", "")
    reports = [
        line
        for line in output.splitlines()
        if "\t" in line or line == "No new variables."
    ]
    assert reports == [
        "Name\tType\tValue",
        "session_variable\tint\t42",
        "No new variables.",
        "Name\tType\tValue",
        "after_late\tint\t4",
    ]
    print(result.stdout)
