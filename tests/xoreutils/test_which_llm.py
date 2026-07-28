"""Tests for the ``which`` xoreutil (``xonsh/xoreutils/which.py``)."""

import io
import os

import pytest

from xonsh.pytest.tools import skip_if_on_windows
from xonsh.xoreutils.which import which

APP = "whichtestapp1"


@pytest.fixture
def which_session(xsh_with_aliases, tmp_path):
    """Session with ``APP`` both aliased and present as a lone executable on PATH."""
    exe = tmp_path / APP
    exe.write_bytes(b"")
    exe.chmod(0o755)
    xsh_with_aliases.env["PATH"] = [str(tmp_path)]
    xsh_with_aliases.aliases[APP] = ["echo", "hi"]
    return xsh_with_aliases


def run_which(*args):
    """Run the which alias, returning its stdout as a list of lines."""
    stdout = io.StringIO()
    which(list(args), stdout=stdout, stderr=io.StringIO())
    return stdout.getvalue().splitlines()


def app_path(tmp_path):
    """The path ``_which.whichgen`` reports for the executable in ``tmp_path``."""
    return os.path.abspath(os.path.normpath(os.path.join(str(tmp_path), APP)))


ALIAS_PLAIN = "echo hi"
ALIAS_VERBOSE = f"aliases['{APP}'] = ['echo', 'hi']"


@skip_if_on_windows
@pytest.mark.parametrize(
    "flags, alias_line, want_path, path_verbose",
    [
        ([], ALIAS_PLAIN, False, False),
        (["-v"], ALIAS_VERBOSE, False, False),
        (["-a"], ALIAS_PLAIN, True, False),
        (["-a", "-v"], ALIAS_VERBOSE, True, True),
    ],
    ids=["default", "verbose", "all", "all-verbose"],
)
def test_which_flag_matrix(
    which_session, tmp_path, flags, alias_line, want_path, path_verbose
):
    """``--all`` and ``--verbose`` are orthogonal: neither implies the other."""
    expected = [alias_line]
    if want_path:
        path = app_path(tmp_path)
        expected.append(f"{path} (from given path element 0)" if path_verbose else path)
    assert run_which(*flags, APP) == expected


@skip_if_on_windows
def test_which_all_does_not_imply_verbose(which_session):
    """Regression for #5031: ``-a`` used to produce byte-identical output to ``-a -v``."""
    assert run_which("-a", APP) != run_which("-a", "-v", APP)


@skip_if_on_windows
@pytest.mark.parametrize(
    "flags",
    [["-p", "-v"], ["-p", "-a", "-v"], ["-p", "-a"]],
    ids=["plain-verbose", "plain-all-verbose", "plain-all"],
)
def test_which_plain_overrides_verbose(which_session, tmp_path, flags):
    """``--plain`` wins over ``--verbose`` whether or not ``--all`` is present."""
    expected = [ALIAS_PLAIN]
    if "-a" in flags:
        expected.append(app_path(tmp_path))
    assert run_which(*flags, APP) == expected


@pytest.mark.parametrize(
    "flags, expected",
    [([], ALIAS_PLAIN), (["-v"], ALIAS_VERBOSE)],
    ids=["default", "verbose"],
)
def test_which_alias_only(xsh_with_aliases, flags, expected):
    """An alias with no PATH match short-circuits before any path lookup."""
    xsh_with_aliases.aliases[APP] = ["echo", "hi"]
    assert run_which(*flags, APP) == [expected]


@skip_if_on_windows
@pytest.mark.parametrize("flags", [[], ["-v"], ["-a"], ["-a", "-v"]])
def test_which_skip_alias(which_session, tmp_path, flags):
    """``--skip-alias`` drops the alias line under every verbosity combination."""
    lines = run_which("-s", *flags, APP)
    path = app_path(tmp_path)
    assert lines == [f"{path} (from given path element 0)" if "-v" in flags else path]
