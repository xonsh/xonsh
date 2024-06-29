import pytest

from xonsh.procs import jobs


@pytest.mark.parametrize(
    "args, prefix, exp",
    [
        (
            "disown",
            "-",
            {"-h", "--help", "-c", "--continue"},
        ),
        (
            "disown",
            "",
            {"1", "2"},
        ),
    ],
)
def test_disown_completion(
    args, prefix, exp, xsh_with_aliases, monkeypatch, check_completer
):
    job = {
        "cmds": (["git-cola", "2>", "/dev/null"], "&"),
        "pids": [37078],
        "bg": True,
        "pgrp": None,
        "started": 1630158319.697764,
        "status": "running",
    }
    all_jobs = {1: job, 2: job}

    monkeypatch.setattr(jobs._jobs_thread_local, "jobs", all_jobs, raising=False)
    monkeypatch.setattr(jobs._jobs_thread_local, "tasks", [2, 1], raising=False)
    assert check_completer(args, prefix=prefix) == exp
