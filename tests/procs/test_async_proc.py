import contextlib
import sys

import pytest

from xonsh.procs import async_proc as ap
from xonsh.procs.specs import run_subproc


def test_ls(xession):
    proc = ap.AsyncProc(["ls"], stdout=sys.stdout, stderr=sys.stderr)
    assert proc.proc.pid


@pytest.fixture
def run_proc(tmp_path):
    def factory(cmds: "list[str]", captured):
        out_file = tmp_path / "stdout"
        with out_file.open("wb") as fw:
            with contextlib.redirect_stdout(fw):
                return_val = run_subproc([cmds], captured)
        return return_val, out_file.read_text()

    return factory


@pytest.mark.parametrize(
    "captured,exp_out,exp_rtn",
    [
        pytest.param(False, "hello", None, id="$[]"),
        pytest.param("stdout", "", "hello", id="$()"),
    ],
)
def test_run_subproc(xession, run_proc, captured, exp_out, exp_rtn):
    xession.env["XONSH_SHOW_TRACEBACK"] = True
    cmds = ["echo", "hello"]

    rtn, out = run_proc(cmds, captured)

    assert rtn == exp_rtn
    assert out.strip() == exp_out
