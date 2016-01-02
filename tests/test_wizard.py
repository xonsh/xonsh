# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import assert_equal, assert_true, assert_false

from xonsh.wizard import (Node, Wizard, Pass, PrettyFormatter, 
    Message, Question)


TREE0 = Wizard(children=[Pass(), Message(message='yo')])
TREE1 = Question('wakka?', {'jawaka': Pass()})

def test_pretty_format_tree0():
    exp = ('Wizard(children=[\n'
           ' Pass(),\n'
           " Message('yo')\n"
           '])')
    obs = PrettyFormatter(TREE0).visit()
    yield assert_equal, exp, obs
    yield assert_equal, exp, str(TREE0)
    yield assert_equal, exp.replace('\n', ''), repr(TREE0)


def test_pretty_format_tree1():
    exp = ('Question(\n'
           " question='wakka?',\n"
           ' responses={\n'
           "  'jawaka': Pass()\n"
           ' }\n'
           ')')
    obs = PrettyFormatter(TREE1).visit()
    yield assert_equal, exp, obs
    yield assert_equal, exp, str(TREE1)
    yield assert_equal, exp.replace('\n', ''), repr(TREE1)

if __name__ == '__main__':
    nose.runmodule()
