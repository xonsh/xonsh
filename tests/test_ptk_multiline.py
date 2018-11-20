# -*- coding: utf-8 -*-
"""Tests sample inputs to PTK multiline and checks parser response"""
import builtins
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.buffer import Buffer

from xonsh.tools import ON_WINDOWS
from xonsh.built_ins import XonshSession

from tools import DummyEnv, skip_if_lt_ptk2


Context = namedtuple("Context", ["indent", "buffer", "accept", "cli", "cr"])


@pytest.fixture(scope="module")
def ctx():
    """Context in which the ptk multiline functionality will be tested."""
    builtins.__xonsh__ = XonshSession()
    builtins.__xonsh__.env = DummyEnv()
    builtins.__xonsh__.env["INDENT"] = "    "
    from xonsh.ptk2.key_bindings import carriage_return

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
    del builtins.__xonsh__.env
    del builtins.__xonsh__


@skip_if_lt_ptk2
def test_colon_indent(ctx):
    document = Document("for i in range(5):")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ctx.indent


@skip_if_lt_ptk2
def test_dedent(ctx):
    document = Document("\n" + ctx.indent + "pass")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ""

    document = Document("\n" + 2 * ctx.indent + "continue")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ctx.indent


@skip_if_lt_ptk2
def test_nodedent(ctx):
    """don't dedent if first line of ctx.buffer"""
    mock = MagicMock(return_value=True)
    with patch("xonsh.ptk2.key_bindings.can_compile", mock):
        document = Document("pass")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None

    mock = MagicMock(return_value=True)
    with patch("xonsh.ptk2.key_bindings.can_compile", mock):
        document = Document(ctx.indent + "pass")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None


@skip_if_lt_ptk2
def test_continuation_line(ctx):
    document = Document("\nsecond line")
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ""


@skip_if_lt_ptk2
def test_trailing_slash(ctx):
    mock = MagicMock(return_value=True)
    with patch("xonsh.ptk2.key_bindings.can_compile", mock):
        document = Document("this line will \\")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        if not ON_WINDOWS:
            assert ctx.buffer.document.current_line == ""
        else:
            assert ctx.accept.mock_calls is not None


@skip_if_lt_ptk2
def test_cant_compile_newline(ctx):
    mock = MagicMock(return_value=False)
    with patch("xonsh.ptk2.key_bindings.can_compile", mock):
        document = Document("for i in (1, 2, ")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.buffer.document.current_line == ""


@skip_if_lt_ptk2
def test_can_compile_and_executes(ctx):
    mock = MagicMock(return_value=True)
    with patch("xonsh.ptk2.key_bindings.can_compile", mock):
        document = Document("ls")
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None
