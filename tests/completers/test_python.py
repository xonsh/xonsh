import pytest

from xonsh.completers.imports import complete_import
from xonsh.completers.python import (
    complete_python,
    complete_xonsh_imp,
    python_signature_complete,
)
from xonsh.parsers.completion_context import CompletionContext, PythonContext
from xonsh.pytest.tools import skip_if_pre_3_8


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer, monkeypatch):
    monkeypatch.setitem(xession.env, "COMPLETIONS_BRACKETS", True)
    return xonsh_execer


def foo(x, y, z):
    pass


def bar(wakka="wow", jawaka="mom"):
    pass


def baz(sonata, artica=True):
    pass


def always_true(x, y):
    return True


BASE_CTX = {"foo": foo, "bar": bar, "baz": baz}
FOO_ARGS = {"x=", "y=", "z="}
BAR_ARGS = {"wakka=", "jawaka="}
BAZ_ARGS = {"sonata=", "artica="}


@pytest.mark.parametrize(
    "line, end, exp",
    [
        ("foo(", 4, FOO_ARGS),  # I have no idea why this one needs to be first
        ("foo()", 3, set()),
        ("foo()", 4, FOO_ARGS),
        ("foo()", 5, set()),
        ("foo(x, ", 6, FOO_ARGS),
        ("foo(x, )", 6, FOO_ARGS),
        ("bar()", 4, BAR_ARGS),
        ("baz()", 4, BAZ_ARGS),
        ("foo(bar(", 8, BAR_ARGS),
        ("foo(bar()", 9, FOO_ARGS),
        ("foo(bar())", 4, FOO_ARGS),
    ],
)
def test_complete_python_signatures(line, end, exp):
    ctx = dict(BASE_CTX)
    obs = python_signature_complete("", line, end, ctx, always_true)
    assert exp == obs


@pytest.mark.parametrize(
    "code, exp",
    (
        ("x = su", "sum"),
        ("imp", "import"),
        ("{}.g", "{}.get("),
        # no signature for native builtins under 3.7:
        pytest.param("''.split(ma", "maxsplit=", marks=skip_if_pre_3_8),
    ),
)
def test_complete_python(code, exp):
    res = complete_python(
        CompletionContext(python=PythonContext(code, len(code), ctx={}))
    )
    assert res and len(res) == 2
    comps, _ = res
    assert exp in comps


def test_complete_python_ctx():
    class A:
        def wow(self):
            pass

    a = A()

    res = complete_python(
        CompletionContext(python=PythonContext("a.w", 2, ctx=locals()))
    )
    assert res and len(res) == 2
    comps, _ = res
    assert "a.wow(" in comps


@pytest.mark.parametrize(
    "command, exp",
    [
        ("import pathli", {"pathlib"}),
        ("from pathli", {"pathlib"}),
        ("import os.pa", {"os.path"}),
        ("import sys,os.pa", {"os.path"}),
        ("from x ", {"import"}),
        ("import os, pathli", {"pathlib"}),
        ("from pathlib import PurePa", {"PurePath"}),
        ("from pathlib import PosixPath,PurePa", {"PurePath"}),
        ("from pathlib import PosixPath PurePa", {"PurePath"}),
    ],
)
@pytest.mark.flaky(reruns=2, reruns_delay=2)
def test_complete_import(command, exp, completer_obj):
    result = complete_import(completer_obj.parse(command))
    if isinstance(result, tuple):
        result, _ = result
    result = set(result)
    assert result == exp


@pytest.mark.parametrize(
    "code, exp_in",
    [
        # Basic module completion
        ("__xonsh__.imp.sy", "__xonsh__.imp.sys"),
        ("__xonsh__.imp.o", "__xonsh__.imp.os"),
        ("__xonsh__.imp.js", "__xonsh__.imp.json"),
        # Nested module completion
        ("__xonsh__.imp.os.pa", "__xonsh__.imp.os.path"),
        # Edge cases
        ("__xonsh__.imp.", "__xonsh__.imp.sys"),  # Should show all modules
        ("__xonsh__.imp.nonexistent", None),  # No matches
    ],
)
def test_complete_xonsh_imp(code, exp_in):
    """Test completion for __xonsh__.imp.<module> syntax."""
    res = complete_xonsh_imp(
        CompletionContext(python=PythonContext(code, len(code), ctx={}))
    )

    if exp_in is None:
        # Expecting no results or empty results
        assert res is None or (isinstance(res, tuple) and len(res[0]) == 0)
    else:
        assert res is not None and len(res) == 2
        comps, lprefix = res
        # Check that the expected completion is in the results
        assert exp_in in comps, f"Expected {exp_in} to be in {comps}"


def test_complete_xonsh_imp_no_context():
    """Test that complete_xonsh_imp returns None when not in Python context."""
    res = complete_xonsh_imp(CompletionContext(python=None))
    assert res is None


def test_complete_xonsh_imp_not_matching():
    """Test that complete_xonsh_imp returns None for non-matching patterns."""
    # Not a __xonsh__.imp pattern
    res = complete_xonsh_imp(
        CompletionContext(python=PythonContext("import sy", 9, ctx={}))
    )
    assert res is None

    # Different attribute path
    res = complete_xonsh_imp(
        CompletionContext(python=PythonContext("__xonsh__.env", 13, ctx={}))
    )
    assert res is None


def test_complete_python_callable_with_attributes():
    """Test that callable classes show plain name only (no duplicate with parentheses)."""
    import datetime

    res = complete_python(
        CompletionContext(
            python=PythonContext("datetime.date", 13, ctx={"datetime": datetime})
        )
    )
    assert res and len(res) == 2
    comps, _ = res

    # Classes with attributes should show plain name only (not with parentheses)
    assert "datetime.datetime" in comps, (
        "Should have plain 'datetime' for attribute access"
    )
    assert "datetime.datetime(" not in comps, (
        "Should NOT have 'datetime(' to avoid duplicates"
    )


def test_complete_python_simple_function():
    """Test that simple functions/methods show with parentheses only (no plain name)."""

    class SimpleClass:
        def simple_method(self):
            """A simple method with no useful attributes."""
            pass

    obj = SimpleClass()

    res = complete_python(
        CompletionContext(python=PythonContext("obj.simple", 10, ctx=locals()))
    )
    assert res and len(res) == 2
    comps, _ = res

    # Simple methods should show with ( only (not plain name)
    assert "obj.simple_method(" in comps, (
        "Should have 'simple_method(' for calling method"
    )
    assert "obj.simple_method" not in comps, (
        "Should NOT have plain 'simple_method' to avoid duplicates"
    )
