"""Tests the dummy history backend."""

import pytest

from xonsh.history.dummy import DummyHistory
from xonsh.history.main import construct_history


@pytest.mark.parametrize("backend", ["dummy", DummyHistory, DummyHistory()])
def test_construct_history_str(xession, backend):
    xession.env["XONSH_HISTORY_BACKEND"] = backend
    assert isinstance(construct_history(), DummyHistory)
