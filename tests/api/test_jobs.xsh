from xonsh.api.jobs import get_last_job, get_last_pid
import pytest


$RAISE_SUBPROC_ERROR = True
$XONSH_SHOW_TRACEBACK = True

def test_get_last_job():
  sleep 100 &
  job = get_last_job()
  assert job["cmds"][0] == ["sleep", "100"]
  kill @(job["pids"][0])

def test_get_last_pid():
  sleep 100 &
  pid = get_last_pid()
  kill @(pid)

