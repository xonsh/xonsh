"""Smoke tests for the pure helpers in ``xonsh.procs.jobs``.

The full job-control machinery requires a live shell with a controlling
terminal, so the tests here focus on the platform-independent helpers:
``add_job`` / ``get_jobs`` / ``get_tasks`` / ``get_next_job_number`` /
``_clear_dead_jobs`` / ``format_job_string`` / ``hup_all_jobs`` / etc.
"""

import collections
import sys

import pytest

from xonsh.procs import jobs


class _FakeProc:
    """Stand-in for ``subprocess.Popen`` — supports ``poll()``."""

    def __init__(self, returncode=None, pid=12345):
        self.returncode = returncode
        self.pid = pid

    def poll(self):
        return self.returncode


class _FakeSpec:
    captured = "stdout"


class _FakePipeline:
    """Stand-in for ``CommandPipeline`` — has a .spec.captured chain."""

    spec = _FakeSpec()


@pytest.fixture
def thread_local_jobs(monkeypatch):
    """Install fresh thread-local jobs/tasks for each test.

    ``tasks`` must be a ``collections.deque`` because ``add_job`` calls
    ``appendleft`` on it.
    """
    fresh_jobs: dict = {}
    fresh_tasks: collections.deque = collections.deque()
    monkeypatch.setattr(jobs._jobs_thread_local, "jobs", fresh_jobs, raising=False)
    monkeypatch.setattr(
        jobs._jobs_thread_local, "tasks", fresh_tasks, raising=False
    )
    return fresh_jobs, fresh_tasks


# --- get_jobs / get_tasks ---------------------------------------------------


def test_get_jobs_returns_thread_local(thread_local_jobs):
    fresh_jobs, _ = thread_local_jobs
    assert jobs.get_jobs() is fresh_jobs


def test_get_tasks_returns_thread_local(thread_local_jobs):
    _, fresh_tasks = thread_local_jobs
    assert jobs.get_tasks() is fresh_tasks


# --- add_job / get_next_job_number ------------------------------------------


def test_add_job_assigns_first_number(thread_local_jobs):
    info = {
        "cmds": [["echo", "hi"]],
        "bg": False,
        "pids": [1],
        "obj": _FakeProc(),
        "pipeline": _FakePipeline(),
    }
    jobs.add_job(info)
    fresh_jobs, _ = thread_local_jobs
    assert 1 in fresh_jobs


def test_add_job_increments_numbers(thread_local_jobs):
    for _ in range(3):
        jobs.add_job(
            {
                "cmds": [["echo", "hi"]],
                "bg": False,
                "pids": [1],
                "obj": _FakeProc(),
                "pipeline": _FakePipeline(),
            }
        )
    fresh_jobs, _ = thread_local_jobs
    assert set(fresh_jobs.keys()) == {1, 2, 3}


def test_add_job_default_status_is_running(thread_local_jobs):
    jobs.add_job(
        {
            "cmds": [["a"]],
            "bg": False,
            "pids": [1],
            "obj": _FakeProc(),
            "pipeline": _FakePipeline(),
        }
    )
    fresh_jobs, _ = thread_local_jobs
    assert fresh_jobs[1]["status"] == "running"


def test_add_job_preserves_explicit_status(thread_local_jobs):
    jobs.add_job(
        {
            "cmds": [["a"]],
            "bg": False,
            "pids": [1],
            "obj": _FakeProc(),
            "status": "stopped",
            "pipeline": _FakePipeline(),
        }
    )
    fresh_jobs, _ = thread_local_jobs
    assert fresh_jobs[1]["status"] == "stopped"


def test_add_job_pushes_onto_task_queue(thread_local_jobs):
    jobs.add_job(
        {
            "cmds": [["a"]],
            "bg": False,
            "pids": [1],
            "obj": _FakeProc(),
            "pipeline": _FakePipeline(),
        }
    )
    _, fresh_tasks = thread_local_jobs
    assert list(fresh_tasks) == [1]


def test_add_job_starts_recorded_time(thread_local_jobs):
    jobs.add_job(
        {
            "cmds": [["a"]],
            "bg": False,
            "pids": [1],
            "obj": _FakeProc(),
            "pipeline": _FakePipeline(),
        }
    )
    fresh_jobs, _ = thread_local_jobs
    assert isinstance(fresh_jobs[1]["started"], float)
    assert fresh_jobs[1]["started"] > 0


def test_get_next_job_number_skips_existing(thread_local_jobs):
    jobs.add_job(
        {
            "cmds": [["a"]],
            "bg": False,
            "pids": [1],
            "obj": _FakeProc(),
            "pipeline": _FakePipeline(),
        }
    )
    jobs.add_job(
        {
            "cmds": [["b"]],
            "bg": False,
            "pids": [2],
            "obj": _FakeProc(),
            "pipeline": _FakePipeline(),
        }
    )
    # both jobs are alive (poll returns None), next job number is 3
    assert jobs.get_next_job_number() == 3


# --- _clear_dead_jobs ------------------------------------------------------


def test_clear_dead_jobs_removes_finished_jobs(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {"obj": _FakeProc(returncode=0), "bg": False, "status": "done", "cmds": [["a"]]}
    fresh_jobs[2] = {"obj": _FakeProc(returncode=None), "bg": False, "status": "running", "cmds": [["b"]]}
    fresh_tasks.extend([1, 2])
    jobs._clear_dead_jobs()
    assert 1 not in fresh_jobs
    assert 2 in fresh_jobs


def test_clear_dead_jobs_removes_jobs_without_obj(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {"obj": None, "bg": False, "status": "done", "cmds": [["a"]]}
    fresh_tasks.append(1)
    jobs._clear_dead_jobs()
    assert 1 not in fresh_jobs


def test_clear_dead_jobs_handles_missing_task_dict_entry(thread_local_jobs):
    """A task ID in the deque without a corresponding jobs entry should be
    silently dropped (KeyError caught internally)."""
    _, fresh_tasks = thread_local_jobs
    fresh_tasks.append(99)
    # this must not raise
    jobs._clear_dead_jobs()
    assert 99 not in fresh_tasks


# --- get_next_task ---------------------------------------------------------


def test_get_next_task_returns_first_running_fg_task(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["a"]],
    }
    fresh_jobs[2] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["b"]],
    }
    fresh_tasks.extend([1, 2])
    task = jobs.get_next_task()
    assert task is fresh_jobs[1]


def test_get_next_task_skips_bg_jobs(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": True,
        "status": "running",
        "cmds": [["a"]],
    }
    fresh_jobs[2] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["b"]],
    }
    fresh_tasks.extend([1, 2])
    task = jobs.get_next_task()
    assert task is fresh_jobs[2]


def test_get_next_task_returns_none_when_no_active_tasks(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "stopped",
        "cmds": [["a"]],
    }
    fresh_tasks.append(1)
    assert jobs.get_next_task() is None


def test_get_next_task_promotes_selected_to_left(thread_local_jobs):
    """The chosen task is moved to the front of the deque."""
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": True,
        "status": "running",
        "cmds": [["a"]],
    }
    fresh_jobs[2] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["b"]],
    }
    fresh_tasks.extend([1, 2])
    jobs.get_next_task()
    assert fresh_tasks[0] == 2


# --- format_job_string -----------------------------------------------------


def test_format_job_string_unknown_returns_empty(thread_local_jobs):
    assert jobs.format_job_string(99) == ""


def test_format_job_string_dict(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["echo", "hi"]],
        "pids": [123],
    }
    fresh_tasks.append(1)
    out = jobs.format_job_string(1)
    assert "1" in out
    assert "running" in out
    assert "echo hi" in out


def test_format_job_string_posix_format_marks_first(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["a"]],
        "pids": [123],
    }
    fresh_tasks.append(1)
    out = jobs.format_job_string(1, format="posix")
    assert "[1]+" in out
    assert "running" in out


def test_format_job_string_posix_format_marks_second(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["a"]],
        "pids": [1],
    }
    fresh_jobs[2] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["b"]],
        "pids": [2],
    }
    fresh_tasks.extend([1, 2])
    out = jobs.format_job_string(2, format="posix")
    assert "[2]-" in out


def test_format_job_string_posix_marks_bg_with_ampersand(thread_local_jobs):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": True,
        "status": "running",
        "cmds": [["a"]],
        "pids": [123],
    }
    fresh_tasks.append(1)
    out = jobs.format_job_string(1, format="posix")
    assert "&" in out


# --- print_one_job ---------------------------------------------------------


def test_print_one_job_writes_to_outfile(thread_local_jobs, capsys):
    fresh_jobs, fresh_tasks = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["echo", "hi"]],
        "pids": [123],
    }
    fresh_tasks.append(1)
    jobs.print_one_job(1, outfile=sys.stdout)
    captured = capsys.readouterr()
    assert "running" in captured.out


def test_print_one_job_unknown_id_writes_nothing(thread_local_jobs, capsys):
    jobs.print_one_job(99, outfile=sys.stdout)
    assert capsys.readouterr().out == ""


# --- get_task --------------------------------------------------------------


def test_get_task_returns_dict(thread_local_jobs):
    fresh_jobs, _ = thread_local_jobs
    fresh_jobs[1] = {"a": 1}
    assert jobs.get_task(1) == {"a": 1}


# --- update_job_attr -------------------------------------------------------


def test_update_job_attr_sets_attribute_for_matching_pid(thread_local_jobs):
    fresh_jobs, _ = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["a"]],
        "pids": [99],
    }
    jobs.update_job_attr(99, "status", "stopped")
    assert fresh_jobs[1]["status"] == "stopped"


def test_update_job_attr_no_match_is_noop(thread_local_jobs):
    fresh_jobs, _ = thread_local_jobs
    fresh_jobs[1] = {
        "obj": _FakeProc(),
        "bg": False,
        "status": "running",
        "cmds": [["a"]],
        "pids": [99],
    }
    jobs.update_job_attr(12345, "status", "stopped")
    # the unrelated pid is unchanged
    assert fresh_jobs[1]["status"] == "running"


# --- proc_untraced_waitpid -------------------------------------------------


def test_proc_untraced_waitpid_proc_with_none_pid_returns_info():
    """When the proc has ``pid=None``, the function short-circuits and
    returns the empty info dict instead of crashing."""

    class NoPid:
        pid = None

    info = jobs.proc_untraced_waitpid(NoPid(), hang=False)
    assert info["backgrounded"] is False
    assert info["signal"] is None


def test_proc_untraced_waitpid_raises_when_requested():
    """With ``raise_child_process_error=True`` and a None pid, raises."""

    class NoPid:
        pid = None

    with pytest.raises(ChildProcessError):
        jobs.proc_untraced_waitpid(NoPid(), hang=False, raise_child_process_error=True)
