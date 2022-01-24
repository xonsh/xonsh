import os

import pytest  # noqa F401

from tools import skip_if_on_windows
from xonsh.completers.man import complete_from_man


@skip_if_on_windows
@pytest.mark.parametrize(
    "cmd,exp,set_manpath",
    [
        ["yes --", {"--version", "--help"}, True],
        [
            "man --",
            {"-k", "-F", "-P", "-W", "-a", "-m", "-H"},
            False,
        ],
    ],
)
def test_man_completion(tmpdir, xession, completer_obj, cmd, exp, set_manpath):
    if set_manpath:
        xession.env["MANPATH"] = os.path.dirname(os.path.abspath(__file__))
    ctx = completer_obj.parse(cmd)
    completions = set(map(str, complete_from_man(ctx)))
    if set_manpath:
        assert completions == exp
    else:
        # BSD & Linux have different man page version
        assert completions.issuperset(exp)
