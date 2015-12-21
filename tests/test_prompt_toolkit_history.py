# -*- coding: utf-8 -*-
"""Tests for the PromptToolkitHistory class."""
import os

import nose
from nose.tools import assert_equal


def is_prompt_toolkit_available():
    try:
        import prompt_toolkit
        return True
    except ImportError:
        return False

if not is_prompt_toolkit_available():
    from nose.plugins.skip import SkipTest
    raise SkipTest('prompt_toolkit is not available')


from xonsh.prompt_toolkit_history import PromptToolkitHistory


def test_obj():
    history_obj = PromptToolkitHistory(load_prev=False)
    history_obj.append('line10')
    yield assert_equal, ['line10'], history_obj.strings
    yield assert_equal, 1, len(history_obj)
    yield assert_equal, ['line10'], [x for x in history_obj]


if __name__ == '__main__':
    nose.runmodule()
