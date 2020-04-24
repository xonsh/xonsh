# -*- coding: utf-8 -*-
"""Test initialization of prompt_toolkit shell"""

import pytest

from xonsh.platform import minimum_required_ptk_version

# verify error if ptk not installed or below min

from xonsh.shell import Shell


@pytest.mark.parametrize(
    "ptk_ver, ini_shell_type, exp_shell_type, warn_snip",
    [
        (None, "prompt_toolkit", "readline", "prompt_toolkit is not available"),
        ((0, 5, 7), "prompt_toolkit", "readline", "is not supported"),
        ((1, 0, 0), "prompt_toolkit", "readline", "is not supported"),
        ((2, 0, 0), "prompt_toolkit", "prompt_toolkit", None),
        ((2, 0, 0), "best", "prompt_toolkit", None),
        ((2, 0, 0), "readline", "readline", None),
        ((3, 0, 0), "prompt_toolkit", "prompt_toolkit", None),
        ((3, 0, 0), "best", "prompt_toolkit", None),
        ((3, 0, 0), "readline", "readline", None),
        ((4, 0, 0), "prompt_toolkit", "prompt_toolkit", None),
    ],
)
def test_prompt_toolkit_version_checks(ptk_ver, ini_shell_type, exp_shell_type, warn_snip, monkeypatch, xonsh_builtins):

    mocked_warn = ""

    def mock_warning(msg):
        nonlocal mocked_warn
        mocked_warn = msg
        return

    def mock_ptk_above_min_supported():
        nonlocal ptk_ver
        return ptk_ver and (ptk_ver[:2] >= minimum_required_ptk_version)

    def mock_has_prompt_toolkit():
        nonlocal ptk_ver
        return ptk_ver is not None

    monkeypatch.setattr("xonsh.shell.warnings.warn", mock_warning)      # hardwon: patch the caller!
    monkeypatch.setattr("xonsh.shell.ptk_above_min_supported", mock_ptk_above_min_supported)    # have to patch both callers
    monkeypatch.setattr("xonsh.platform.ptk_above_min_supported", mock_ptk_above_min_supported)
    monkeypatch.setattr("xonsh.shell.has_prompt_toolkit", mock_has_prompt_toolkit)
    monkeypatch.setattr("xonsh.platform.has_prompt_toolkit", mock_has_prompt_toolkit)

    act_shell_type = Shell.choose_shell_type(ini_shell_type, {})

    assert act_shell_type == exp_shell_type

    if warn_snip:
        assert warn_snip in mocked_warn

    pass

# someday: initialize PromptToolkitShell and have it actually do something.
