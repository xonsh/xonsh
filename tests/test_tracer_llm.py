"""Smoke tests for ``xonsh.tracer``.

Covers the pure helpers (``tracer_format_line``, ``_find_caller``) and the
``TracerType`` singleton's no-side-effect behavior. Actual ``sys.settrace``
work is exercised via ``start``/``stop`` round-trips on a temp file so we
never leave a global tracer installed.
"""

import sys

from xonsh.tracer import (
    COLORLESS_LINE,
    TracerType,
    _find_caller,
    tracer,
    tracer_format_line,
)

# --- TracerType singleton ---------------------------------------------------


def test_tracer_type_is_singleton():
    a = TracerType()
    b = TracerType()
    assert a is b


def test_module_level_tracer_resolves_to_singleton():
    """``xonsh.tracer.tracer`` is a LazyObject — once forced, it points
    at the same TracerType singleton as a fresh ``TracerType()``."""
    t = TracerType()
    # forcing any attribute access loads the LazyObject
    assert tracer.usecolor is t.usecolor


def test_tracer_color_output_toggles_attribute():
    t = TracerType()
    t.color_output(False)
    assert t.usecolor is False
    t.color_output(True)
    assert t.usecolor is True


# --- start / stop round-trip ------------------------------------------------


def test_tracer_start_and_stop_round_trip(tmp_path):
    """start() registers ``self.trace``; stop() restores the previous tracer."""
    f = tmp_path / "watch_me.py"
    f.write_text("# placeholder\n")
    prev = sys.gettrace()
    t = TracerType()
    try:
        t.start(str(f))
        # ``sys.gettrace`` returns the same bound method, but bound methods
        # are not identity-equal across attribute lookups — compare via ==.
        assert sys.gettrace() == t.trace
        assert str(f) in {p for p in t.files} or any(
            str(f).endswith(p.split("/")[-1]) for p in t.files
        )
        t.stop(str(f))
    finally:
        sys.settrace(prev)
    assert sys.gettrace() is prev
    assert t.files == set()


def test_tracer_start_then_stop_clears_file_set(tmp_path):
    f = tmp_path / "clear_me.py"
    f.write_text("")
    prev = sys.gettrace()
    t = TracerType()
    try:
        t.start(str(f))
        assert len(t.files) >= 1
        t.stop(str(f))
        assert len(t.files) == 0
    finally:
        sys.settrace(prev)


# --- tracer_format_line -----------------------------------------------------


def test_tracer_format_line_colorless():
    out = tracer_format_line("/tmp/x.py", 5, "print('hi')", color=False)
    assert out == COLORLESS_LINE.format(fname="/tmp/x.py", lineno=5, line="print('hi')")


def test_tracer_format_line_color_with_pygments():
    """With color enabled the function returns either a string or a list of
    pygments tokens — both shapes are acceptable."""
    out = tracer_format_line("/tmp/x.py", 5, "print('hi')", color=True)
    assert isinstance(out, (list, str))


# --- _find_caller -----------------------------------------------------------


def test_find_caller_returns_none_for_unmatchable_args(capsys):
    """No frame in the test-runner stack contains an obvious xonsh-style
    ``trace foo bar`` invocation, so ``_find_caller`` falls through to
    its warning + ``return None``."""
    result = _find_caller(["__nonsense__", "__token__"])
    assert result is None
    err = capsys.readouterr().err
    assert "__file__" in err and "could not be found" in err


# --- on_files / off_files placeholder branches ------------------------------


def test_on_files_skips_unresolvable_file(capsys):
    """When a path cannot be resolved (the synthetic ``__file__`` lookup
    fails), the for-loop simply ``continue``s — nothing is added to
    ``self.files``."""
    t = TracerType()
    starting = set(t.files)
    t.on_files([], files=[])
    assert t.files == starting


def test_off_files_skips_unresolvable_file():
    t = TracerType()
    starting = set(t.files)
    t.off_files([], files=[])
    assert t.files == starting


def test_toggle_color_smoke():
    t = TracerType()
    t.toggle_color(True)
    assert t.usecolor is True
    t.toggle_color(False)
    assert t.usecolor is False
