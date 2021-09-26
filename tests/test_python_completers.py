import pytest

from tests.tools import skip_if_pre_3_8
from xonsh.completers.python import (
    python_signature_complete,
    complete_python,
)
from xonsh.completers.imports import complete_import
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
    PythonContext,
)


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
    (
        (
            CommandContext(args=(CommandArg("import"),), arg_index=1, prefix="pathli"),
            {"pathlib"},
        ),
        (
            CommandContext(args=(CommandArg("from"),), arg_index=1, prefix="pathli"),
            {"pathlib"},
        ),
        (
            CommandContext(args=(CommandArg("import"),), arg_index=1, prefix="os.pa"),
            {"os.path"},
        ),
        (
            CommandContext(
                args=(CommandArg("import"),), arg_index=1, prefix="sys,os.pa"
            ),
            {"os.path"},
        ),
        (
            CommandContext(
                args=(
                    CommandArg("from"),
                    CommandArg("x"),
                ),
                arg_index=2,
            ),
            {"import"},
        ),
        (
            CommandContext(
                args=(
                    CommandArg("import"),
                    CommandArg("os,"),
                ),
                arg_index=2,
                prefix="pathli",
            ),
            {"pathlib"},
        ),
        (
            CommandContext(
                args=(
                    CommandArg("from"),
                    CommandArg("pathlib"),
                    CommandArg("import"),
                ),
                arg_index=3,
                prefix="PurePa",
            ),
            {"PurePath"},
        ),
        (
            CommandContext(
                args=(
                    CommandArg("from"),
                    CommandArg("pathlib"),
                    CommandArg("import"),
                ),
                arg_index=3,
                prefix="PosixPath,PurePa",
            ),
            {"PurePath"},
        ),
        (
            CommandContext(
                args=(
                    CommandArg("from"),
                    CommandArg("pathlib"),
                    CommandArg("import"),
                    CommandArg("PosixPath"),
                ),
                arg_index=4,
                prefix="PurePa",
            ),
            {"PurePath"},
        ),
    ),
)
def test_complete_import(command, exp):
    result = complete_import(
        CompletionContext(
            command, python=PythonContext("", 0)  # `complete_import` needs this
        )
    )
    if isinstance(result, tuple):
        result, _ = result
    result = set(result)
    assert result == exp
