# -*- coding: utf-8 -*-
"""Testing inspectors"""
import inspect
from xonsh.inspectors import getouterframes


def test_getouterframes():
    """Just test that this works."""
    curr = inspect.currentframe()
    getouterframes(curr, context=0)
