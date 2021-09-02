"""Tests bashisms xontrib."""
import pytest
import sys


@pytest.fixture(name="bash_preproc", scope="module")
def _bash_preproc():
    from xontrib.bashisms import bash_preproc

    yield bash_preproc
    del sys.modules["xontrib.bashisms"]


@pytest.mark.parametrize(
    "history, inp, exp",
    [
        # No history:
        ([], "!!", ""),
        ([], "!$", ""),
        ([], "!^", ""),
        ([], "!*", ""),
        ([], "!echo", ""),
        # No substitution:
        (["aa 1 2", "ab 3 4"], "ls", "ls"),
        (["aa 1 2", "ab 3 4"], "x = 42", "x = 42"),
        (["aa 1 2", "ab 3 4"], "!", "!"),
        # Bang command only:
        (["aa 1 2", "ab 3 4"], "!!", "ab 3 4"),
        (["aa 1 2", "ab 3 4"], "!$", "4"),
        (["aa 1 2", "ab 3 4"], "!^", "ab"),
        (["aa 1 2", "ab 3 4"], "!*", "3 4"),
        (["aa 1 2", "ab 3 4"], "!a", "ab 3 4"),
        (["aa 1 2", "ab 3 4"], "!aa", "aa 1 2"),
        (["aa 1 2", "ab 3 4"], "!ab", "ab 3 4"),
        # Bang command with others:
        (["aa 1 2", "ab 3 4"], "echo !! >log", "echo ab 3 4 >log"),
        (["aa 1 2", "ab 3 4"], "echo !$ >log", "echo 4 >log"),
        (["aa 1 2", "ab 3 4"], "echo !^ >log", "echo ab >log"),
        (["aa 1 2", "ab 3 4"], "echo !* >log", "echo 3 4 >log"),
        (["aa 1 2", "ab 3 4"], "echo !a >log", "echo ab 3 4 >log"),
        (["aa 1 2", "ab 3 4"], "echo !aa >log", "echo aa 1 2 >log"),
        (["aa 1 2", "ab 3 4"], "echo !ab >log", "echo ab 3 4 >log"),
    ],
)
def test_preproc(history, inp, exp, xession, bash_preproc):
    """Test the bash preprocessor."""

    xession.history.inps = history
    obs = bash_preproc(inp)
    assert exp == obs
