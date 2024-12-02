"""Helpers for the Xonsh jobs API"""

from xonsh.procs.jobs import get_jobs


def get_last_job():
    """Get the last job that was started, or None if there are no running jobs."""
    jobs = list(get_jobs().values())
    if not jobs:
        return None
    last_job = max(jobs, key=lambda x: x["started"])
    return last_job


def get_last_pid():
    """Get the PID from the last job that was started. Returns an int or None if there are no running jobs.
    This is equivalent to $! in bash."""
    last_job = get_last_job()
    return None if last_job is None else last_job["pids"][0]
