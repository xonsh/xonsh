# -*- coding: utf-8 -*-
"""Test initialization of prompt_toolkit shell"""

import sys
import pytest
from xonsh.platform import minimum_required_ptk_version
import pyte

# verify error if ptk not installed or below min

from xonsh.ptk_shell.shell import tokenize_ansi, remove_ansi_osc
from xonsh.shell import Shell


@pytest.mark.parametrize(
    "ptk_ver, ini_shell_type, exp_shell_type, warn_snip",
    [
        (None, "prompt_toolkit", "readline", None),
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
def test_prompt_toolkit_version_checks(
    ptk_ver,
    ini_shell_type,
    exp_shell_type,
    warn_snip,
    monkeypatch,
    xonsh_builtins,
):

    mocked_warn = ""

    def mock_warning(msg):
        nonlocal mocked_warn
        mocked_warn = msg
        return

    def mock_ptk_above_min_supported():
        nonlocal ptk_ver
        return ptk_ver and (ptk_ver[:3] >= minimum_required_ptk_version)

    def mock_has_prompt_toolkit():
        nonlocal ptk_ver
        return ptk_ver is not None

    monkeypatch.setattr(
        "xonsh.shell.warnings.warn", mock_warning
    )  # hardwon: patch the caller!
    monkeypatch.setattr(
        "xonsh.shell.ptk_above_min_supported", mock_ptk_above_min_supported
    )  # have to patch both callers
    monkeypatch.setattr(
        "xonsh.platform.ptk_above_min_supported", mock_ptk_above_min_supported
    )
    monkeypatch.setattr("xonsh.platform.has_prompt_toolkit", mock_has_prompt_toolkit)

    old_syspath = sys.path.copy()

    act_shell_type = Shell.choose_shell_type(ini_shell_type, {})

    assert len(old_syspath) == len(sys.path)

    sys.path = old_syspath

    assert act_shell_type == exp_shell_type

    if warn_snip:
        assert warn_snip in mocked_warn

    pass


@pytest.mark.parametrize(
    "prompt_tokens, ansi_string_parts",
    [
        # no ansi, single token
        ([("fake style", "no ansi here")], ["no ansi here"]),
        # no ansi, multiple tokens
        ([("s1", "no"), ("s2", "ansi here")], ["no", "ansi here"]),
        # ansi only, multiple
        ([("s1", "\x1b[33mansi \x1b[1monly")], ["", "ansi ", "only"]),
        # mixed
        (
            [("s1", "no ansi"), ("s2", "mixed \x1b[33mansi")],
            ["no ansi", "mixed ", "ansi"],
        ),
    ],
)
def test_tokenize_ansi(prompt_tokens, ansi_string_parts):
    ansi_tokens = tokenize_ansi(prompt_tokens)
    for token, text in zip(ansi_tokens, ansi_string_parts):
        assert token[1] == text


@pytest.mark.parametrize(
    "raw_prompt, prompt, osc_tokens",
    [
        # no title
        ("test prompt", "test prompt", []),
        # starts w/ title
        ("\033]0;TITLE THIS\007test prompt", "test prompt", ["\033]0;TITLE THIS\007"]),
        # ends w/ title
        ("test prompt\033]0;TITLE THIS\007", "test prompt", ["\033]0;TITLE THIS\007"]),
        # title in the middle
        ("test \033]0;TITLE THIS\007prompt", "test prompt", ["\033]0;TITLE THIS\007"]),
        # title + iTerm2 OSC exapmle
        (
            "test \033]0;TITLE THIS\007prompt \033]133;A\007here",
            "test prompt here",
            ["\033]0;TITLE THIS\007", "\033]133;A\007"],
        ),
    ],
)
def test_remove_ansi_osc(raw_prompt, prompt, osc_tokens):
    checked_prompt, removed_osc = remove_ansi_osc(raw_prompt)
    assert prompt == checked_prompt
    assert len(removed_osc) == len(osc_tokens)
    for removed, ref in zip(removed_osc, osc_tokens):
        assert removed == ref


@pytest.mark.parametrize(
    "line, exp",
    [
        [repr("hello"), None],
        ["2 * 3", "6"],
    ],
)
def test_ptk_prompt(line, exp, ptk_shell, capsys):
    inp, out, shell = ptk_shell
    inp.send_text(f"{line}\nexit\n")  # note: terminate with '\n'
    shell.cmdloop()
    screen = pyte.Screen(80, 24)
    stream = pyte.Stream(screen)

    out, _ = capsys.readouterr()

    # this will remove render any color codes
    stream.feed(out.strip())
    out = screen.display[0].strip()

    assert out.strip() == (exp or line)
