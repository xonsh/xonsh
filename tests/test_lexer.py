"""Tests the xonsh lexer."""
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

import nose
from nose.tools import assert_equal

from xonsh.lexer import Lexer

def test_int_literal():
    l = Lexer()
    l.build()
    l.input('42')
    toks = list(l)
    assert_equal(['42'], toks)
    

if __name__ == '__main__':
    nose.runmodule()