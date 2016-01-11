# -*- coding: utf-8 -*-
"""Tests some tools function for prompt_toolkit integration."""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal
from unittest.mock import MagicMock, patch

import builtins
from xonsh.ptk.key_bindings import carriage_return
from xonsh.environ import Env

from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.document import Document
from prompt_toolkit.buffer import Buffer, AcceptAction

builtins.__xonsh_env__ = Env()
builtins.__xonsh_env__['INDENT'] = '    '
indent_ = '    '
##setup
buffer = Buffer()
bufaccept = MagicMock(name='accept', spec=AcceptAction)
cli = MagicMock(name='cli', spec=CommandLineInterface)


buffer.accept_action = bufaccept

def test_colon_indent():
    document = Document('for i in range(5):')
    buffer.set_document(document)
    carriage_return(buffer, cli, indent_)
    assert_equal(buffer.document.current_line, indent_)

def test_dedent():
    document = Document(indent_+'pass')
    buffer.set_document(document)
    carriage_return(buffer, cli, indent_)
    assert_equal(buffer.document.current_line, '')

    document = Document(2*indent_+'continue')
    buffer.set_document(document)
    carriage_return(buffer, cli, indent_)
    assert_equal(buffer.document.current_line,indent_)

def test_continuation_line():
    document = Document('\nsecond line')
    buffer.set_document(document)
    carriage_return(buffer, cli, '')
    assert_equal(buffer.document.current_line, '')

def test_trailing_slash():
    document = Document('this line will \\')
    buffer.set_document(document)
    carriage_return(buffer, cli, '')
    assert_equal(buffer.document.current_line, '')

def test_cant_compile_newline():
    mock = MagicMock(return_value = False)
    with patch('xonsh.ptk.key_bindings.can_compile', mock):
        document = Document('for i in (1, 2, ')
        buffer.set_document(document)
        carriage_return(buffer, cli, '')
        assert_equal(buffer.document.current_line, '')

if __name__ == '__main__':
    nose.runmodule()
