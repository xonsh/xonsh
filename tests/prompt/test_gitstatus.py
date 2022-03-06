import pytest

from xonsh.prompt import gitstatus


@pytest.fixture(autouse=True)
def git_no_stash(mocker):
    return mocker.patch.object(gitstatus, "get_stash_count", return_value=0)


@pytest.fixture
def prompts(xession):
    fields = xession.env["PROMPT_FIELDS"]
    yield fields
    fields.clear()


@pytest.fixture
def fake_proc(fake_process):
    def wrap(map: "dict"):
        for command, stdout in map.items():
            fake_process.register_subprocess(command=command, stdout=stdout)
        return fake_process

    return wrap


@pytest.mark.parametrize(
    "hidden, exp",
    [
        (
            (),
            "{CYAN}gitstatus-opt↑·7↓·2{RESET}|{RED}●1{RESET}{BLUE}+3{RESET}{BLUE}+49{RESET}{RED}-26{RESET}",
        ),
        (
            ("gs_lines_added", "gs_lines_removed"),
            "{CYAN}gitstatus-opt↑·7↓·2{RESET}|{RED}●1{RESET}{BLUE}+3{RESET}",
        ),
    ],
)
def test_gitstatus_dirty(prompts, fake_proc, hidden, exp):
    if hidden:
        prompts["gitstatus"].remove(*hidden)
    dirty = {
        "git status --porcelain --branch": b"""\
## gitstatus-opt...origin/gitstatus-opt [ahead 7, behind 2]
 M requirements/tests.txt
AM tests/prompt/test_gitstatus.py
 M tests/prompt/test_vc.py""",
        "git rev-parse --git-dir": b".git",
        "git diff --numstat": b"""\
1       0       requirements/tests.txt
26      0       tests/prompt/test_gitstatus.py
22      26      tests/prompt/test_vc.py""",
    }
    fake_proc(dirty)

    # finally assert
    assert format(prompts.pick("gitstatus")) == exp


def test_gitstatus_clean(prompts, fake_proc):
    clean = {
        "git status --porcelain --branch": b"## gitstatus-opt...origin/gitstatus-opt [ahead 7, behind 2]",
        "git rev-parse --git-dir": b".git",
        "git diff --numstat": b"",
    }
    fake_proc(clean)

    exp = "{CYAN}gitstatus-opt↑·7↓·2{RESET}|{BOLD_GREEN}✓{RESET}"
    assert format(prompts.pick("gitstatus")) == exp
