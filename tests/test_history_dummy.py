"""Tests the dummy history backend."""

import pytest

from xonsh.history.dummy import DummyHistory
from xonsh.history.main import construct_history


@pytest.mark.parametrize("backend", ["dummy", DummyHistory, DummyHistory()])
def test_construct_history_str(xession, backend):
    xession.env["XONSH_HISTORY_BACKEND"] = backend
    assert isinstance(construct_history(), DummyHistory)


def test_ignore_regex_invalid(xession, capsys):
    xession.env["XONSH_HISTORY_BACKEND"] = "dummy"
    xession.env["XONSH_HISTORY_IGNORE_REGEX"] = "**"
    history = construct_history()
    assert history.history_ignore_regex is None
    captured = capsys.readouterr()
    assert (
        "XONSH_HISTORY_IGNORE_REGEX is not a valid regular expression and will be ignored"
        in captured.err
    )


def test_ignore_regex_valid(xession):
    xession.env["XONSH_HISTORY_BACKEND"] = "dummy"
    xession.env["XONSH_HISTORY_IGNORE_REGEX"] = "ls"
    history = construct_history()
    assert history.history_ignore_regex is not None
