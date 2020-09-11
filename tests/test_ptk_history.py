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

    # defining the ptk2 package this way leaves out the internal global names (which all start with '_')

    s_new = set(dir(imports_new))
    s_legacy = set(dir(imports_legacy))
    extra_names = s_new - s_legacy

    for name in extra_names:
        assert name.startswith("_")

    assert s_legacy.issubset(s_new)


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
