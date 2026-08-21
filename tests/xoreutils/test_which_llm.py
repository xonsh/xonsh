"""Tests for the ``which`` alias in ``xonsh.xoreutils.which``."""

import io
import os

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.xoreutils import which as xxw

#: Name of the file created on ``$PATH``; on Windows the extension is needed
#: so that ``whichgen`` picks it up via ``$PATHEXT``.
APP_FILE = "whichtestapp1.exe" if ON_WINDOWS else "whichtestapp1"

#: Name the ``which`` alias is called with.
APP = "whichtestapp1"


class FakeSpec:
    """Stand-in for the ``SubprocSpec`` a callable alias receives as ``spec``."""

    def __init__(self, captured):
        self.captured = captured


@pytest.fixture
def which_path(tmp_path, xession):
    """Put two directories holding the same executable name on ``$PATH``."""
    dirs = []
    for name in ("bin1", "bin2"):
        d = tmp_path / name
        d.mkdir()
        app = d / APP_FILE
        app.write_bytes(b"")
        os.chmod(app, 0o755)
        dirs.append(str(d))
    xession.env["PATH"] = dirs
    xession.env["PATHEXT"] = [".EXE", ".BAT", ".CMD", ".COM"]
    return dirs


def _run(args, spec=None):
    """Run the ``which`` alias and return ``(retcode, stdout, stderr)``."""
    stdout, stderr = io.StringIO(), io.StringIO()
    rtn = xxw.which(args, stdout=stdout, stderr=stderr, spec=spec)
    return rtn, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize(
    "spec",
    [
        None,
        FakeSpec(False),
        FakeSpec("stdout"),
        FakeSpec("object"),
        FakeSpec("hiddenobject"),
    ],
    ids=["no-spec", "uncaptured", "stdout", "object", "hiddenobject"],
)
def test_all_plain_prints_one_path_per_line(which_path, spec):
    """``which -ap`` must separate matches by newlines however it is called.

    Under a capturing spec the paths used to be printed with ``end=""``,
    which glued every match into a single unusable line.
    """
    rtn, out, err = _run(["-ap", APP], spec=spec)
    assert rtn == 0
    assert err == ""
    assert out.count("\n") == 2
    assert [os.path.dirname(line) for line in out.splitlines()] == which_path
    assert all(os.path.basename(line) == APP_FILE for line in out.splitlines())


@pytest.mark.parametrize(
    "spec", [FakeSpec(False), FakeSpec("stdout")], ids=["uncaptured", "stdout"]
)
def test_single_match_is_one_line(which_path, spec):
    """Without ``-a`` exactly one match is printed, as a single line.

    ``$(which app)`` strips that trailing newline in
    ``CommandPipeline.get_formatted_lines`` (single-line output only), so
    the capture stays free of a trailing newline without ``which`` having
    to suppress it.
    """
    rtn, out, err = _run(["-p", APP], spec=spec)
    assert rtn == 0
    assert err == ""
    assert out.splitlines() == [os.path.join(which_path[0], APP_FILE)]
    assert out.endswith("\n")


def test_all_verbose_prints_one_path_per_line(which_path):
    """``-a`` alone implies verbose; matches stay newline separated."""
    rtn, out, err = _run(["-a", APP], spec=FakeSpec("stdout"))
    assert rtn == 0
    assert out.count("\n") == 2
    assert all(line.endswith(")") for line in out.splitlines())


def test_alias_and_paths_are_separated(which_path, xession):
    """An alias match and the ``$PATH`` matches must not be glued together."""
    xession.aliases[APP] = ["echo", "hi"]
    rtn, out, err = _run(["-ap", APP], spec=FakeSpec("stdout"))
    assert rtn == 0
    lines = out.splitlines()
    assert len(lines) == 3
    assert lines[0] == "echo hi"
    assert [os.path.dirname(line) for line in lines[1:]] == which_path


def test_missing_command_reports_failure(which_path):
    rtn, out, err = _run(["-ap", "not_a_command_at_all"], spec=FakeSpec("stdout"))
    assert rtn == 1
    assert out == ""
    assert "not_a_command_at_all not in " in err
