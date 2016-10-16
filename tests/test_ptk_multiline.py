# -*- coding: utf-8 -*-
"""Tests sample inputs to PTK multiline and checks parser response"""
import builtins
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.document import Document
from prompt_toolkit.buffer import Buffer, AcceptAction

from xonsh.tools import ON_WINDOWS

from tools import DummyEnv


Context = namedtuple('Context', ['indent', 'buffer', 'accept', 'cli', 'cr'])


@pytest.yield_fixture(scope='module')
def ctx():
    """Context in which the ptk multiline functionality will be tested."""
    builtins.__xonsh_env__ = DummyEnv()
    builtins.__xonsh_env__['INDENT'] = '    '
    from xonsh.ptk.key_bindings import carriage_return
    ptk_buffer = Buffer()
    ptk_buffer.accept_action = MagicMock(name='accept', spec=AcceptAction)
    cli = MagicMock(name='cli', spec=CommandLineInterface)
    yield Context(indent='    ',
                  buffer=ptk_buffer,
                  accept=ptk_buffer.accept_action,
                  cli=cli,
                  cr=carriage_return)
    del builtins.__xonsh_env__


def test_colon_indent(ctx):
    document = Document('for i in range(5):')
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ctx.indent


def test_dedent(ctx):
    document = Document('\n'+ctx.indent+'pass')
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ''

    document = Document('\n'+2*ctx.indent+'continue')
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ctx.indent


def test_nodedent(ctx):
    '''don't dedent if first line of ctx.buffer'''
    mock = MagicMock(return_value=True)
    with patch('xonsh.ptk.key_bindings.can_compile', mock):
        document = Document('pass')
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None

    mock = MagicMock(return_value=True)
    with patch('xonsh.ptk.key_bindings.can_compile', mock):
        document = Document(ctx.indent+'pass')
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None


def test_continuation_line(ctx):
    document = Document('\nsecond line')
    ctx.buffer.set_document(document)
    ctx.cr(ctx.buffer, ctx.cli)
    assert ctx.buffer.document.current_line == ''


def test_trailing_slash(ctx):
    mock = MagicMock(return_value=True)
    with patch('xonsh.ptk.key_bindings.can_compile', mock):
        document = Document('this line will \\')
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        if not ON_WINDOWS:
            assert ctx.buffer.document.current_line == ''
        else:
            assert ctx.accept.mock_calls is not None


def test_cant_compile_newline(ctx):
    mock = MagicMock(return_value=False)
    with patch('xonsh.ptk.key_bindings.can_compile', mock):
        document = Document('for i in (1, 2, ')
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.buffer.document.current_line == ''


def test_can_compile_and_executes(ctx):
    mock = MagicMock(return_value=True)
    with patch('xonsh.ptk.key_bindings.can_compile', mock):
        document = Document('ls')
        ctx.buffer.set_document(document)
        ctx.cr(ctx.buffer, ctx.cli)
        assert ctx.accept.mock_calls is not None
