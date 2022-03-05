import pytest

from xonsh.prompt import gitstatus
from xonsh.prompt import base


@pytest.fixture(autouse=True)
def git_no_stash(mocker):
    return mocker.patch.object(gitstatus, "_get_stash", return_value=0)


@pytest.fixture(autouse=True)
def git_no_stash(mocker):
    return mocker.patch.object(gitstatus, "_get_stash", return_value=0)


@pytest.mark.parametrize(
    "hidden, exp",
    [
        (
            (),
            "{CYAN}gitstatus-opt↑·7↓·2{RESET}|{RED}●1{RESET}{BLUE}+3{RESET}{BLUE}+49{RESET}{RED}-26{RESET}",
        ),
        (
            ("lines_added", "lines_removed"),
            "{CYAN}gitstatus-opt↑·7↓·2{RESET}|{RED}●1{RESET}{BLUE}+3{RESET}",
        ),
    ],
)
def test_gitstatus(xession, hidden, exp, fake_process):
    xession.env["XONSH_GITSTATUS_FIELDS_HIDDEN"] = hidden
    xession.env["PROMPT_FIELDS"] = base.PROMPT_FIELDS
    fake_process.register_subprocess(
        command="git status --porcelain --branch".split(),
        stdout=b"""\
## gitstatus-opt...origin/gitstatus-opt [ahead 7, behind 2]
 M requirements/tests.txt
AM tests/prompt/test_gitstatus.py
 M tests/prompt/test_vc.py
""",
    )
    fake_process.register_subprocess(
        command="git rev-parse --git-dir".split(),
        stdout=b".git",
    )
    fake_process.register_subprocess(
        command="git diff --numstat".split(),
        stdout=b"""\
1       0       requirements/tests.txt
26      0       tests/prompt/test_gitstatus.py
22      26      tests/prompt/test_vc.py
""",
    )
    assert gitstatus.gitstatus_prompt({}, xession) == exp


def test_gitstatus_clean(xession, fake_process):
    xession.env["PROMPT_FIELDS"] = base.PROMPT_FIELDS

    fake_process.register_subprocess(
        command="git status --porcelain --branch".split(),
        stdout=b"""\
## gitstatus-opt...origin/gitstatus-opt [ahead 7, behind 2]
""",
    )
    fake_process.register_subprocess(
        command="git rev-parse --git-dir".split(),
        stdout=b".git",
    )
    fake_process.register_subprocess(
        command="git diff --numstat".split(),
        stdout=b"""\
""",
    )
    exp = "{CYAN}gitstatus-opt↑·7↓·2{RESET}|{BOLD_GREEN}✓{RESET}"
    assert gitstatus.gitstatus_prompt({}, xession) == exp
