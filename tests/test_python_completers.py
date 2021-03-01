from xonsh.parsers.completion_context import CommandArg, CommandContext, CompletionContext, CompletionContextParser, PythonContext
import pytest

from xonsh.completers.python import python_signature_complete, complete_import


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_builtins, xonsh_execer):
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


@pytest.mark.parametrize("command, exp", (
    (CommandContext(args=(CommandArg("import"),), arg_index=1, prefix="pathli"), {"pathlib"}),
    (CommandContext(args=(CommandArg("from"),), arg_index=1, prefix="pathli"), {"pathlib "}),
    (CommandContext(args=(CommandArg("import"),), arg_index=1, prefix="os.pa"), {"os.path"}),
    (CommandContext(args=(
        CommandArg("import"), CommandArg("os,"),
        ), arg_index=2, prefix="pathli"), {"pathlib"}),
    (CommandContext(args=(
        CommandArg("from"), CommandArg("pathlib"), CommandArg("import"),
        ), arg_index=3, prefix="PurePa"), {"PurePath"}),
))
def test_complete_import(command, exp):
    result = complete_import(CompletionContext(command,
        python=PythonContext("", 0)  # `complete_import` needs this
    ))
    assert result == exp
