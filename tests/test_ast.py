"""Xonsh AST tests."""
from nose.tools import assert_equal

from xonsh import ast
from xonsh.ast import Tuple, Name, Store


def test_gather_names_name():
    node = Name(id='y', ctx=Store())
    exp = {'y'}
    obs = ast.gather_names(node)
    assert_equal(exp, obs)


def test_gather_names_tuple():
    node = Tuple(elts=[Name(id='y', ctx=Store()),
                       Name(id='z', ctx=Store())])
    exp = {'y', 'z'}
    obs = ast.gather_names(node)
    assert_equal(exp, obs)
