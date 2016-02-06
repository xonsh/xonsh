# -*- coding: utf-8 -*-
"""Testing inspectors"""
import inspect

from nose.tools import assert_equal, assert_not_equal

from xonsh.inspectors import getouterframes


def test_getouterframes():
    """Just test that this works."""
    curr = inspect.currentframe()
    getouterframes(curr, context=0)


if __name__ == '__main__':
    nose.runmodule()
