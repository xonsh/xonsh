import sys
import pytest
from inspect import signature
from unittest.mock import MagicMock

from xonsh.aliases import Aliases
from xonsh.completer import Completer
from tests.test_ptk_completer import EXPANSION_CASES

XonshKernel = None


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    global XonshKernel
    if XonshKernel is None:
        monkeypatch.setitem(sys.modules, "zmq", MagicMock())
        monkeypatch.setitem(sys.modules, "zmq.eventloop", MagicMock())
        monkeypatch.setitem(sys.modules, "zmq.error", MagicMock())
        import xonsh.jupyter_kernel

        XonshKernel = xonsh.jupyter_kernel.XonshKernel


@pytest.mark.parametrize("code, index, expected_args", EXPANSION_CASES)
def test_completion_alias_expansion(
    code,
    index,
    expected_args,
    monkeypatch,
    xession,
):
    xonsh_completer_mock = MagicMock(spec=Completer)
    xonsh_completer_mock.complete.return_value = set(), 0

    kernel = MagicMock()
    kernel.completer = xonsh_completer_mock

    monkeypatch.setattr(xession, "aliases", Aliases(gb=["git branch"]))
    monkeypatch.setattr(xession.shell, "ctx", None, raising=False)

    XonshKernel.do_complete(kernel, code, index)
    mock_call = xonsh_completer_mock.complete.call_args
    args, kwargs = mock_call
    expected_args["self"] = None
    expected_args["ctx"] = None
    assert (
        signature(Completer.complete).bind(None, *args, **kwargs).arguments
        == expected_args
    )
