import pytest

try:
    import prompt_toolkit  # NOQA
except ImportError:
    pytest.mark.skip(msg="prompt_toolkit is not available")

from xonsh.ptk2.history import PromptToolkitHistory

from tools import skip_if_lt_ptk2


@pytest.fixture
def history_obj():
    """Instantiate `PromptToolkitHistory` and append a line string"""
    hist = PromptToolkitHistory(load_prev=False)
    hist.append_string("line10")
    return hist


@skip_if_lt_ptk2
def test_obj(history_obj):
    assert ["line10"] == history_obj.get_strings()
    assert len(history_obj) == 1
    assert ["line10"] == [x for x in history_obj]
