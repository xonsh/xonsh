# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import assert_equal, assert_true, assert_false

from xonsh.wizard import (Node, Wizard, Pass, PrettyFormatter, 
    Message, Question, StateVisitor)


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


def test_state_visitor_store():
    exp = {'rick': [{}, {}, {'and': 'morty'}]}
    sv = StateVisitor()
    sv.store('/rick/2/and', 'morty')
    obs = sv.state
    yield assert_equal, exp, obs

    exp['rick'][1]['mr'] = 'meeseeks'
    sv.store('/rick/-2/mr', 'meeseeks')
    yield assert_equal, exp, obs


if __name__ == '__main__':
    nose.runmodule()
