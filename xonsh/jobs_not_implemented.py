
from collections import namedtuple
from subprocess import TimeoutExpired
import builtins
import os


ProcProxy = namedtuple('ProcProxy', ['stdout', 'stderr'])
"""
A class representing a Python function to be run as a subprocess command.
"""

_active_job = None


def add_job(info):
    global _active_job
    _active_job = info


def wait_for_active_job():
    global _active_job
    if _active_job is None:
        return
    obj = _active_job['obj']
    if isinstance(obj, ProcProxy):
        return
    if _active_job['bg']:
        return
    while obj.returncode is None:
        try:
            obj.wait(0.01)
        except TimeoutExpired:
            pass
        except KeyboardInterrupt:
            obj.kill()
    obj.done = True


def kill_all_jobs():
    if _active_job is not None:
        try:
            _active_jobs['obj'].kill()
        except:
            pass


msg = 'Job control not implemented on this platform.\n'


def jobs(args, stdin=None):
    return '', msg


def fg(args, stdin=None):
    return '', msg


def bg(args, stdin=None):
    return '', msg


def ignore_SIGTSTP():
    pass