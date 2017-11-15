import pytest

from xonsh.environ import Env
import xonsh.completers.path as xcp


def test_pattern_need_quotes():
    # just make sure the regex compiles
    xcp.PATTERN_NEED_QUOTES.match('')


def test_complete_path(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = {'CASE_SENSITIVE_COMPLETIONS': False,
                                    'GLOB_SORTED': True,
                                    'SUBSEQUENCE_PATH_COMPLETION': False,
                                    'FUZZY_PATH_COMPLETION': False,
                                    'SUGGEST_THRESHOLD': 3,
                                    'CDPATH': set(),
    }
    xcp.complete_path('[1-0.1]', '[1-0.1]', 0, 7, dict())
