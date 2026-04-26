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


class TestAtSignCompletion:
    """Test @ prefix completion: bare @. (xonsh object), @name. and @name (decorator)."""

    def test_at_dot_completes_xonsh_object(self):
        """@.<TAB> completes attributes of the xonsh session interface (@)."""
        res = complete_python(CompletionContext(python=PythonContext("@.", 2, ctx={})))
        assert res is not None
        comps, _ = res
        assert "@.env[" in comps

    def test_at_name_dot_completes_attrs(self):
        """@obj.<TAB> completes attributes of obj (decorator prefix)."""

        class Obj:
            some_attr = 1

        res = complete_python(
            CompletionContext(python=PythonContext("@obj.", 5, ctx={"obj": Obj}))
        )
        assert res is not None
        comps, _ = res
        assert "@obj.some_attr" in comps

    def test_at_name_completes_decorator(self):
        """@na<TAB> completes names from ctx with @ prefix."""

        class MyDecorator:
            pass

        res = complete_python(
            CompletionContext(
                python=PythonContext("@My", 3, ctx={"MyDecorator": MyDecorator})
            )
        )
        assert res is not None
        comps, _ = res
        assert "@MyDecorator" in comps

    def test_at_dot_env_completes_methods(self):
        """@.env.<TAB> completes attributes of the session env."""
        res = complete_python(
            CompletionContext(python=PythonContext("@.env.", 6, ctx={}))
        )
        assert res is not None
        comps, _ = res
        assert "@.env.get(" in comps
        assert "@.env.swap(" in comps
        assert "@.env.keys(" in comps

    def test_at_dot_env_partial_match(self):
        """@.env.sw<TAB> narrows completions by prefix."""
        res = complete_python(
            CompletionContext(python=PythonContext("@.env.sw", 8, ctx={}))
        )
        assert res is not None
        comps, _ = res
        assert "@.env.swap(" in comps
        assert "@.env.get(" not in comps

    def test_at_dot_history_completes_methods(self, xession, monkeypatch):
        """@.history.<TAB> completes attributes of the session history."""
        from xonsh.pytest.tools import DummyHistory

        monkeypatch.setattr(xession.interface, "history", DummyHistory())
        res = complete_python(
            CompletionContext(python=PythonContext("@.history.", 10, ctx={}))
        )
        assert res is not None
        comps, _ = res
        assert "@.history.append(" in comps
        assert "@.history.flush(" in comps

    def test_at_dot_lastcmd_completes_attrs(self, xession, monkeypatch):
        """@.lastcmd.<TAB> completes attributes of the last command pipeline."""

        class FakePipeline:
            rtn = 0
            out = ""

        monkeypatch.setattr(xession.interface, "lastcmd", FakePipeline())
        res = complete_python(
            CompletionContext(python=PythonContext("@.lastcmd.", 10, ctx={}))
        )
        assert res is not None
        comps, _ = res
        assert "@.lastcmd.rtn" in comps
        assert "@.lastcmd.out[" in comps


def test_complete_python_empty_prefix_hides_noise():
    """Bare Tab on a completely empty prefix must not surface
    xonsh-syntax tokens (``!(``, ``@(``, ``$(``, …), Python operators
    and keywords from ``XONSH_TOKENS``, or underscore-prefixed builtins
    (dunders, private names). Without filtering every entry would match
    and bury actually useful completions.
    """
    res = complete_python(CompletionContext(python=PythonContext("", 0, ctx={})))
    assert res is not None
    comps, _ = res
    comps_str = {str(c) for c in comps}

    # xonsh-specific syntax — explicitly named in the user request.
    for tok in ("!(", "@(", "$(", "${", "$[", "![", "@$(", "@", "?", "??"):
        assert tok not in comps_str, f"{tok!r} leaked into bare-Tab menu"
    # Operators / keywords from XONSH_TOKENS — also noise on bare Tab.
    for tok in ("+", "==", "if", "for", "lambda"):
        assert tok not in comps_str, f"{tok!r} leaked into bare-Tab menu"
    # No underscore-prefixed names (dunders or private).
    leaked_underscore = sorted(s for s in comps_str if s.startswith("_"))
    assert not leaked_underscore, (
        f"underscore-prefixed names leaked into bare-Tab menu: {leaked_underscore}"
    )
    # Sanity: the menu is not empty — common builtins still come through.
    assert "print" in comps_str
    assert "len" in comps_str


def test_complete_python_dunder_prefix_still_shows_dunders():
    """The bare-Tab filter must only kick in for an empty prefix —
    if the user actually typed ``__``, dunder builtins must appear.
    """
    res = complete_python(CompletionContext(python=PythonContext("__", 2, ctx={})))
    assert res is not None
    comps, _ = res
    comps_str = {str(c) for c in comps}
    assert any(s.startswith("__") for s in comps_str), (
        "expected dunder builtins to be offered for prefix '__'"
    )


def test_complete_python_empty_prefix_hides_underscore_ctx():
    """Underscore-prefixed names from the local context must also be
    hidden on bare Tab (same noise rule as for builtins).
    """
    ctx = {"_hidden": 1, "visible": 2, "__dunder__": 3}
    res = complete_python(CompletionContext(python=PythonContext("", 0, ctx=ctx)))
    assert res is not None
    comps, _ = res
    comps_str = {str(c) for c in comps}
    assert "visible" in comps_str
    assert "_hidden" not in comps_str
    assert "__dunder__" not in comps_str
