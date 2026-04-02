"""Tests sample inputs to PTK multiline and checks parser response"""

from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document

from xonsh.tools import ON_WINDOWS

Context = namedtuple("Context", ["indent", "buffer", "accept", "cli", "cr"])


@pytest.fixture
def ctx(xession):
    """Context in which the ptk multiline functionality will be tested."""
    xession.env["INDENT"] = "    "
    from xonsh.shells.ptk_shell.key_bindings import carriage_return

    ptk_buffer = Buffer()
    ptk_buffer.accept_action = MagicMock(name="accept")
    cli = MagicMock(name="cli", spec=Application)
    yield Context(
        indent="    ",
        buffer=ptk_buffer,
        accept=ptk_buffer.accept_action,
        cli=cli,
        cr=carriage_return,
    )


def test_colon_indent(ctx):
    document = Document("for i in range(5):")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ctx.indent


def test_dedent(ctx):
    document = Document("\n" + ctx.indent + "pass")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ""

    document = Document("\n" + 2 * ctx.indent + "continue")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ctx.indent


def test_nodedent(ctx):
    """don't dedent if first line of ctx.buffer"""
    mock = MagicMock(return_value=True)
    with patch("xonsh.shells.ptk_shell.key_bindings.can_compile", mock):
        document = Document("pass")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None

    mock = MagicMock(return_value=True)
    with patch("xonsh.shells.ptk_shell.key_bindings.can_compile", mock):
        document = Document(ctx.indent + "pass")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None


def test_continuation_line(ctx):
    document = Document("\nsecond line")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ""


def test_trailing_slash(ctx):
    mock = MagicMock(return_value=True)
    with patch("xonsh.shells.ptk_shell.key_bindings.can_compile", mock):
        document = Document("this line will \\")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        if not ON_WINDOWS:
            assert ctx.buffer.document.current_line == ""
        else:
            assert ctx.accept.mock_calls is not None


def test_cant_compile_newline(ctx):
    mock = MagicMock(return_value=False)
    with patch("xonsh.shells.ptk_shell.key_bindings.can_compile", mock):
        document = Document("for i in (1, 2, ")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.buffer.document.current_line == ""


@pytest.mark.parametrize("keyword", ["pass", "break", "continue", "return", "raise"])
def test_dedent_token_at_col0_not_truncated(ctx, keyword):
    """Dedent tokens at column 0 must not be truncated.

    Regression: 'pass' became 'p' because newline(copy_margin) copied 0
    spaces (line already at col 0), then delete_before_cursor(4) ate into
    the keyword itself.
    """
    document = Document("\n" + keyword)
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    # The keyword must survive intact on the previous line
    prev_line = ctx.buffer.document.lines[-2]
    assert prev_line == keyword, f"{keyword!r} was truncated to {prev_line!r}"


@pytest.mark.parametrize("keyword", ["pass", "break", "continue"])
def test_dedent_token_with_indent_removes_one_level(ctx, keyword):
    """Dedent tokens with sufficient indent should lose one indent level."""
    document = Document("\n" + ctx.indent + keyword)
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ""


def test_can_compile_and_executes(ctx):
    mock = MagicMock(return_value=True)
    with patch("xonsh.shells.ptk_shell.key_bindings.can_compile", mock):
        document = Document("ls")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None
