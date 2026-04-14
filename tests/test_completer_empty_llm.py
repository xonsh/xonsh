"""Tests for empty-completion fallthrough in ``xonsh.completer``.

See https://github.com/xonsh/xonsh/issues/5810 and the related
https://github.com/xonsh/xonsh/issues/5809 — an exclusive completer that
returns only empty or whitespace-only items must not short-circuit the
completer pipeline, so that fallback completers (``python``, ``path``,
etc.) still get a chance to run.
"""

import pytest

from xonsh.completer import Completer
from xonsh.completers.tools import (
    RichCompletion,
    complete_from_sub_proc,
    completion_from_cmd_output,
    non_exclusive_completer,
)


@pytest.fixture(scope="session")
def completer():
    return Completer()


@pytest.fixture
def completers_mock(xession, monkeypatch):
    completers = {}
    monkeypatch.setattr(xession, "_completers", completers)
    return completers


@pytest.mark.parametrize(
    "bad_result",
    (
        {""},
        {" "},
        {"  ", "\t"},
        {"\n"},
    ),
)
def test_empty_completer_falls_through_to_next(completer, completers_mock, bad_result):
    """An exclusive completer returning only blanks must not block the chain."""
    completers_mock["bad"] = lambda *a: bad_result
    completers_mock["good"] = lambda *a: {"real"}

    assert completer.complete("pre", "", 0, 0) == (("real",), 3)


def test_mixed_valid_and_empty_filters_empty(completer, completers_mock):
    """Blank items are filtered, but valid ones keep the completer exclusive."""
    completers_mock["mixed"] = lambda *a: {"real1", "", "real2", "  "}
    completers_mock["fallback"] = lambda *a: {"fallback"}

    comps, _ = completer.complete("pre", "", 0, 0)
    # Empties are dropped; the valid items remain and fallback is NOT reached.
    assert set(comps) == {"real1", "real2"}


def test_rich_completion_with_empty_value_is_skipped(completer, completers_mock):
    """``RichCompletion`` with an empty value must be skipped just like ``''``."""
    completers_mock["bad"] = lambda *a: {RichCompletion("", display="hint")}
    completers_mock["good"] = lambda *a: {"real"}

    comps, _ = completer.complete("pre", "", 0, 0)
    assert "real" in comps
    assert "" not in (str(c) for c in comps)


def test_non_exclusive_empty_still_yields_to_others(completer, completers_mock):
    """Even a non-exclusive completer's blanks should not leak into results."""
    completers_mock["a"] = non_exclusive_completer(lambda *a: {"", " "})
    completers_mock["b"] = lambda *a: {"real"}

    comps, _ = completer.complete("pre", "", 0, 0)
    assert set(comps) == {"real"}


def test_complete_from_sub_proc_skips_blank_lines(fake_process, xession):
    """``complete_from_sub_proc`` must not emit empty RichCompletion objects.

    Simulates a subprocess whose stdout has interleaved blank lines — a common
    symptom of the original #5809 ``aws s3 cp`` issue at the helper layer.
    """
    fake_process.register_subprocess(
        command=["somecmd", fake_process.any()],
        stdout=b"good1\n\n  \n\ngood2\n",
    )

    results = list(complete_from_sub_proc("somecmd", "arg"))
    values = [str(r) for r in results]
    assert values == ["good1", "good2"]
    # ``completion_from_cmd_output`` uses ``append_space=True`` only when
    # there is a single candidate; two here means no trailing space.
    assert all(not v.endswith(" ") for v in values)


def test_completion_from_cmd_output_strips_whitespace():
    """Sanity: the helper still trims whitespace on non-blank input."""
    comp = completion_from_cmd_output("  hello  ")
    assert str(comp) == "hello"
