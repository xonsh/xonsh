import pytest

import shutil

has_gh = shutil.which("gh")
pytestmark = pytest.mark.skipif(not has_gh, reason="gh is not available")


@pytest.mark.parametrize(
    "line, exp",
    [
        ["gh rep", {"repo"}],
        ["gh repo ", {"archive", "clone", "create", "delete", "edit", "fork"}],
    ],
)
def test_completions(line, exp, check_completer, xsh_with_env):
    # use the actual PATH from os. Otherwise subproc will fail on windows. `unintialized python...`
    comps = check_completer(line, prefix=None)

    if callable(exp):
        exp = exp()
    assert comps.intersection(exp)
