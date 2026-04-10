"""Tests for sane error messages, SyntaxError fields, and AST locations."""

import ast

import pytest


def test_unexpected_indent_error_message(parser):
    """Leading indent should report 'unexpected indent', not 'code: '."""
    with pytest.raises(SyntaxError, match="unexpected indent"):
        parser.parse("  x = 1\n")


def test_unexpected_indent_extra_level(parser):
    """Extra indentation inside a block should report 'unexpected indent'."""
    with pytest.raises(SyntaxError, match="unexpected indent"):
        parser.parse("if True:\n        pass\n            x\n")


def test_unexpected_newline_in_expr(parser):
    """A newline mid-expression should report 'unexpected newline'."""
    with pytest.raises(SyntaxError, match="unexpected newline"):
        parser.parse("x +\n  y\n")


def test_unexpected_newline_lambda_body(parser):
    """Lambda with indented body should report 'unexpected newline'."""
    with pytest.raises(SyntaxError, match="unexpected newline"):
        parser.parse("lambda:\n    x\n")


def test_unexpected_newline_annotation(parser):
    """Annotation followed by newline+indent should report 'unexpected newline'."""
    with pytest.raises(SyntaxError, match="unexpected newline"):
        parser.parse("x: \n    int\n")


def test_unexpected_indent_preserves_lineno(parser):
    """The SyntaxError should carry a correct line number."""
    with pytest.raises(SyntaxError, match="unexpected indent") as exc_info:
        parser.parse("  x = 1\n")
    assert exc_info.value.lineno == 1


def test_unexpected_newline_preserves_lineno(parser):
    """The SyntaxError for newline should carry the correct line number."""
    with pytest.raises(SyntaxError, match="unexpected newline") as exc_info:
        parser.parse("x =\n  1\n")
    assert exc_info.value.lineno == 1


def test_syntax_error_offset_matches_cpython(parser):
    """SyntaxError.offset should be 1-indexed, matching CPython."""
    code = "def f(:\n"
    with pytest.raises(SyntaxError) as xonsh_exc:
        parser.parse(code)
    with pytest.raises(SyntaxError) as cpython_exc:
        compile(code, "<test>", "exec")
    assert xonsh_exc.value.offset == cpython_exc.value.offset


@pytest.mark.parametrize(
    "code",
    [
        "import os\n",
        "import os as o\n",
        "from os import path\n",
        "from os import path as p\n",
        "import os.path\n",
    ],
)
def test_import_alias_location_matches_cpython(parser, code):
    """ast.alias lineno/col_offset should match CPython."""
    xonsh_tree = parser.parse(code)
    cpython_tree = ast.parse(code)
    xa = xonsh_tree.body[0].names[0]
    ca = cpython_tree.body[0].names[0]
    assert xa.lineno == ca.lineno
    assert xa.col_offset == ca.col_offset


@pytest.mark.parametrize(
    "code, node_type",
    [
        ("{}", ast.Dict),
        ("{1: 2}", ast.Dict),
        ("{1: 2, 3: 4}", ast.Dict),
        ("{1: 2,}", ast.Dict),
        ('{**{"a": 1}}', ast.Dict),
        ("{1, 2}", ast.Set),
        ("{1,}", ast.Set),
        ("{1, 2, 3}", ast.Set),
    ],
)
def test_dict_set_no_ctx_field(parser, code, node_type):
    """ast.Dict and ast.Set must not have a ctx attribute (breaks Python 3.15)."""
    tree = parser.parse(code)
    node = tree.body
    assert isinstance(node, node_type)
    assert not hasattr(node, "ctx")
