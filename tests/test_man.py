import os

import pytest  # noqa F401

from tools import skip_if_on_windows, skip_if_not_on_darwin
from xonsh.completers.man import complete_from_man


@skip_if_on_windows
@pytest.mark.parametrize(
    "cmd,exp",
    [
        [
            "yes -",
            {"--version", "--help"},
        ],
        [
            "man -",
            {
                "--all",
                "--apropos",
                "--ascii",
                "--catman",
                "--config-file",
                "--debug",
                "--default",
                "--ditroff",
                "--encoding",
                "--extension",
                "--global-apropos",
                "--gxditview",
                "--help",
                "--html",
                "--ignore-case",
                "--local-file",
                "--locale",
                "--location",
                "--location-cat",
                "--manpath",
                "--match-case",
                "--names-only",
                "--nh",
                "--nj",
                "--no-subpages",
                "--pager",
                "--preprocessor",
                "--prompt",
                "--recode",
                "--regex",
                "--sections",
                "--systems",
                "--troff",
                "--troff-device",
                "--update",
                "--usage",
                "--version",
                "--warnings",
                "--whatis",
                "--wildcard",
            },
        ],
    ],
)
def test_man_completion(xession, check_completer, cmd, exp):
    xession.env["MANPATH"] = os.path.dirname(os.path.abspath(__file__))
    completions = check_completer(cmd, complete_fn=complete_from_man, prefix=None)
    assert completions == exp


@skip_if_not_on_darwin
@pytest.mark.parametrize(
    "cmd,exp",
    [
        [
            "man -",
            {
                "--path",
                "--preformat",
                "-B",
                "-C",
                "-D",
                "-H",
                "-K",
                "-M",
                "-P",
                "-S",
                "-W",
                "-a",
                "-c",
                "-d",
                "-f",
                "-h",
                "-k",
                "-m",
                "-p",
                "-t",
            },
        ],
    ],
)
def test_bsd_man_page_completions(xession, check_completer, cmd, exp):
    # BSD & Linux have different man page version
    completions = check_completer(cmd, complete_fn=complete_from_man, prefix=None)
    assert completions == exp
