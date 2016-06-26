# -*- coding: utf-8 -*-
"""Tests for the PromptToolkitHistory class."""
import os
import sys

import pytest

def is_prompt_toolkit_available():
    try:
        import prompt_toolkit
        return True
    except ImportError:
        return False

if not is_prompt_toolkit_available():
    pytest.skip(msg='prompt_toolkit is not available')


from xonsh.ptk.history import PromptToolkitHistory


def test_obj():
    history_obj = PromptToolkitHistory(load_prev=False)
    history_obj.append('line10')
    assert ['line10'] == history_obj.strings
    assert len(history_obj) == 1
    assert ['line10'] == [x for x in history_obj]
