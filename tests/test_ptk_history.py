import pytest

try:
    import prompt_toolkit  # NOQA
except ImportError:
    pytest.mark.skip(msg="prompt_toolkit is not available")


@pytest.fixture
def history_obj():
    """Instantiate `PromptToolkitHistory` and append a line string"""
    from xonsh.ptk_shell.history import PromptToolkitHistory
    hist = PromptToolkitHistory(load_prev=False)
    hist.append_string("line10")
    return hist


def test_obj(history_obj):
    assert ["line10"] == history_obj.get_strings()
    assert len(history_obj) == 1
    assert ["line10"] == [x for x in history_obj]


def test_ptk2_backcompat():
    """
    Test that legacy code (ahem, xontribs) can still reference xonsh.ptk2 (for a while)
    """

    import xonsh.ptk_shell.shell as imports_new
    import xonsh.ptk2.shell as imports_legacy

    assert dir(imports_legacy) == dir(imports_new)

    # the following is true, but unexpected.  
    # legacy package key in sys.modules is legacy path, but package __name__ is the source pagage
    # but code doesn't care.
    assert imports_legacy is imports_new

# prove that legacy API is usable

@pytest.fixture
def history_obj_legacy():
    """Instantiate `PromptToolkitHistory` via legacy alias and append a line string"""
    from xonsh.ptk2.history import PromptToolkitHistory
    hist = PromptToolkitHistory(load_prev=False)
    hist.append_string("line10")
    return hist


def test_obj_legacy(history_obj_legacy):
    history_obj = history_obj_legacy
    assert ["line10"] == history_obj.get_strings()
    assert len(history_obj) == 1
    assert ["line10"] == [x for x in history_obj]
