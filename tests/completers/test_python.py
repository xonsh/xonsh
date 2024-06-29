import pytest

from xonsh.completers.imports import complete_import
from xonsh.completers.python import complete_python, python_signature_complete
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
