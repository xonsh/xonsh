"""Tests for sane error messages on indent/dedent/newline parse errors."""

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
