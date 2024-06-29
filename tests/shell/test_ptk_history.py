import pytest

try:
    import prompt_toolkit  # NOQA
except ImportError:
    pytest.mark.skip(msg="prompt_toolkit is not available")


@pytest.fixture
def history_obj():
    """Instantiate `PromptToolkitHistory` and append a line string"""
    from xonsh.shells.ptk_shell.history import PromptToolkitHistory

    hist = PromptToolkitHistory(load_prev=False)
    hist.append_string("line10")
    return hist


def test_obj(history_obj):
    assert ["line10"] == history_obj.get_strings()
    assert len(history_obj) == 1
    assert ["line10"] == [x for x in history_obj]
