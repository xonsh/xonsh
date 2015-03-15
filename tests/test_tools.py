"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys

from nose.tools import assert_equal, assert_true

from xonsh.lexer import Lexer
from xonsh.tools import subproc_toks

LEXER = Lexer()
LEXER.build()

INDENT = '    '

def test_subproc_toks_x():
    exp = '$[x]'
    obs = subproc_toks('x', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_l():
    exp = '$[ls -l]'
    obs = subproc_toks('ls -l', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_git():
    s = 'git commit -am "hello doc"'
    exp = '$[{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_git_semi():
    s = 'git commit -am "hello doc"'
    exp = '$[{0}];'.format(s)
    obs = subproc_toks(s + ';', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_git_nl():
    s = 'git commit -am "hello doc"'
    exp = '$[{0}]\n'.format(s)
    obs = subproc_toks(s + '\n', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_indent_ls():
    s = 'ls -l'
    exp = INDENT + '$[{0}]\n'.format(s)
    obs = subproc_toks(INDENT + s + '\n', mincol=len(INDENT), lexer=LEXER, 
                       returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_comment():
    s = 'ls -l'
    com = '  # lets list'
    exp = '$[{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_42_comment():
    s = 'ls 42'
    com = '  # lets list'
    exp = '$[{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_str_comment():
    s = 'ls "wakka"'
    com = '  # lets list'
    exp = '$[{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_l_semi_ls_first():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '$[{0}]; {1}'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_l_semi_ls_first():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '$[{0}]; {1}'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, maxcol=6, returnline=True)
    assert_equal(exp, obs)

def test_subproc_toks_ls_l_semi_ls_second():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '{0}; $[{1}]'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, mincol=7, returnline=True)
    assert_equal(exp, obs)

def test_subproc_hello_mom_first():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = '{0}; {1}'.format(fst, sec)
    exp = '$[{0}]; {1}'.format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, maxcol=len(fst)+1, returnline=True)
    assert_equal(exp, obs)

def test_subproc_hello_mom_second():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = '{0}; {1}'.format(fst, sec)
    exp = '{0}; $[{1}]'.format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, mincol=len(fst), returnline=True)
    assert_equal(exp, obs)


if __name__ == '__main__':
    nose.runmodule()
