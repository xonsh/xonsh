# -*- coding: utf-8 -*-
"""Tests some tools function for prompt_toolkit integration."""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal
from unittest.mock import MagicMock

import builtins
from xonsh.ptk.key_bindings import carriage_return
from xonsh.environ import Env

from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.document import Document
from prompt_toolkit.buffer import Buffer, AcceptAction

builtins.__xonsh_env__ = Env()
builtins.__xonsh_env__['INDENT'] = '    '
env = builtins.__xonsh_env__
##setup
document = Document('for i in range(5):')
buffer = Buffer(initial_document=document)
bufaccept = MagicMock(name='accept', spec=AcceptAction)
cli = MagicMock(name='cli', spec=CommandLineInterface)

buffer.accept_action = bufaccept

def test_newline_indent():
    carriage_return(buffer, cli, env.get('INDENT'))
    assert_equal(buffer.document.current_line, env.get('INDENT'))

if __name__ == '__main__':
    nose.runmodule()
