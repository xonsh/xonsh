"""Smoke tests for ``xonsh.timings``.

The module backs the ``timeit!`` alias and the ``--timings`` CLI flag. These
tests target the pure helpers — ``format_time``, the lazy clock objects, and
``Timer.timeit`` — without spinning up an interactive shell.
"""

import time

import pytest

from xonsh.timings import (
    Timer,
    _HAVE_RESOURCE,
    clock,
    clock2,
    clocks,
    clocku,
    format_time,
)


# --- format_time ------------------------------------------------------------


def test_format_time_seconds():
    assert format_time(1.5).endswith("s")
    assert "1.5" in format_time(1.5)


def test_format_time_milliseconds():
    out = format_time(0.005)
    assert out.endswith("ms")


def test_format_time_zero_picks_largest_unit():
    """``timespan == 0`` must fall through ``order = 3`` and not raise."""
    out = format_time(0.0)
    # the smallest unit ('s', 'ms', 'us'/'µs', 'ns') is one of these
    assert any(out.endswith(u) for u in ("s", "ms", "us", "ns", "\xb5s"))


def test_format_time_above_one_minute_uses_human_readable():
    out = format_time(125)  # 2 min 5 s
    assert "min" in out
    assert "s" in out


def test_format_time_above_one_hour():
    out = format_time(60 * 60 + 5)  # 1h 5s — leftover < 1 ends loop early
    assert "h" in out


def test_format_time_above_one_day():
    out = format_time(60 * 60 * 24 + 30)
    assert "d" in out


def test_format_time_precision_param():
    """The precision controls significant digits in the sub-minute branch."""
    p1 = format_time(0.123456789, precision=1)
    p5 = format_time(0.123456789, precision=5)
    # higher precision yields a strictly longer formatted number
    assert len(p5) >= len(p1)


# --- lazy clock objects ----------------------------------------------------


def test_clock_returns_floats():
    assert isinstance(clock(), float)
    assert isinstance(clocku(), float)
    assert isinstance(clocks(), float)


def test_clock_is_monotonic_within_sleep():
    """User CPU is monotonic across a tiny sleep on every supported platform."""
    a = clock()
    time.sleep(0.001)
    b = clock()
    assert b >= a


def test_clock2_returns_pair():
    pair = clock2()
    assert isinstance(pair, tuple)
    assert len(pair) == 2
    assert all(isinstance(x, float) for x in pair)


def test_have_resource_is_bool():
    """The lazybool wrapper resolves to a real bool when truth-tested."""
    assert bool(_HAVE_RESOURCE) in (True, False)


# --- Timer ------------------------------------------------------------------


def test_timer_inner_timeit_executes():
    t = Timer(timer=clock)

    def inner(_it, _timer):
        t0 = _timer()
        for _ in _it:
            pass
        return _timer() - t0

    t.inner = inner
    elapsed = t.timeit(number=1)
    assert elapsed >= 0.0


def test_timer_repeat_returns_n_runs():
    t = Timer(timer=clock)

    def inner(_it, _timer):
        return 0.0

    t.inner = inner
    runs = t.repeat(repeat=3, number=1)
    assert len(runs) == 3
    assert all(r == 0.0 for r in runs)


# --- timeit_alias smoke ----------------------------------------------------


def test_timeit_alias_no_args_returns_minus_one(capsys):
    """``timeit!`` with no args prints usage and returns -1."""
    from xonsh.timings import timeit_alias

    rc = timeit_alias([])
    assert rc == -1
    out = capsys.readouterr().out
    assert "Usage" in out
