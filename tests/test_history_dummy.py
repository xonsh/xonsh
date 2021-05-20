# -*- coding: utf-8 -*-
"""Tests the dummy history backend."""
# pylint: disable=protected-access

from xonsh.history.dummy import DummyHistory
from xonsh.history.main import construct_history


def test_construct_history_str(xession):
    xession.env["XONSH_HISTORY_BACKEND"] = "dummy"
    assert isinstance(construct_history(), DummyHistory)


def test_construct_history_class(xession):
    xession.env["XONSH_HISTORY_BACKEND"] = DummyHistory
    assert isinstance(construct_history(), DummyHistory)


def test_construct_history_instance(xession):
    xession.env["XONSH_HISTORY_BACKEND"] = DummyHistory()
    assert isinstance(construct_history(), DummyHistory)
