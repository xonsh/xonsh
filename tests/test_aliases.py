# -*- coding: utf-8 -*-
"""Testing built_ins.Aliases"""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal

from xonsh.built_ins import Aliases


def cd(args, stdin=None):
    return args

ALIASES = Aliases({'o': ['omg', 'lala']},
                  color_ls=['ls', '--color=true'],
                  ls="ls '-  -'",
                  cd=cd,
                  indirect_cd='cd ..')
RAW = ALIASES._raw

def test_imports():
    assert_equal(RAW, {
        'o': ['omg', 'lala'],
        'ls': ['ls', '-  -'],
        'color_ls': ['ls', '--color=true'],
        'cd': cd,
        'indirect_cd': ['cd', '..']
    })

def test_eval_normal():
    assert_equal(ALIASES.get('o'), ['omg', 'lala'])

def test_eval_self_reference():
    assert_equal(ALIASES.get('ls'), ['ls', '-  -'])

def test_eval_recursive():
    assert_equal(ALIASES.get('color_ls'), ['ls', '-  -', '--color=true'])

def test_eval_recursive_callable_partial():
    assert_equal(ALIASES.get('indirect_cd')(['arg2', 'arg3']),
                 ['..', 'arg2', 'arg3'])

if __name__ == '__main__':
    nose.runmodule()
