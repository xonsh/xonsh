import builtins

import pytest
from unittest.mock import patch

from xonsh.environ import Env
import xonsh.completers.path as xcp


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_builtins, xonsh_execer):
    return xonsh_execer


def test_pattern_need_quotes():
    # just make sure the regex compiles
    xcp.PATTERN_NEED_QUOTES.match("")


def test_complete_path(xonsh_builtins):
    xonsh_builtins.__xonsh__.env = {
        "CASE_SENSITIVE_COMPLETIONS": False,
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    xcp.complete_path("[1-0.1]", "[1-0.1]", 0, 7, dict())


@patch("xonsh.completers.path._add_cdpaths")
def test_cd_path_no_cd(mock_add_cdpaths, xonsh_builtins):
    xonsh_builtins.__xonsh__.env = {
        "CASE_SENSITIVE_COMPLETIONS": False,
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": ["/"],
    }
    xcp.complete_path("a", "cat a", 4, 5, dict())
    mock_add_cdpaths.assert_not_called()
