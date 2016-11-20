import pytest

try:
    import prompt_toolkit  # NOQA
except ImportError:
    pytest.mark.skip(msg='prompt_toolkit is not available')

from xonsh.ptk.history import PromptToolkitHistory


@pytest.fixture
def history_obj():
    """Instatiate `PromptToolkitHistory` and append a line string"""
    hist = PromptToolkitHistory(load_prev=False)
    hist.append('line10')
    return hist


def test_obj(history_obj):
    assert ['line10'] == history_obj.strings
    assert len(history_obj) == 1
    assert ['line10'] == [x for x in history_obj]
