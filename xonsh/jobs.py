"""
Job control for the xonsh shell.
"""
import os
import time
import signal
import builtins
from collections import namedtuple

ProcProxy = namedtuple('ProcProxy', ['stdout', 'stderr'])
"""
A class representing a Python function to be run as a subprocess command.
"""


def _clear_dead_jobs():
    to_remove = set()
    for num, job in builtins.__xonsh_all_jobs__.items():
        obj = job['obj']
        if isinstance(obj, ProcProxy) or obj.poll() is not None:
            to_remove.add(num)
    for i in to_remove:
        del builtins.__xonsh_all_jobs__[i]
        if builtins.__xonsh_active_job__ == i:
            builtins.__xonsh_active_job__ = None
    if builtins.__xonsh_active_job__ is None:
        _reactivate_job()


def _reactivate_job():
    if len(builtins.__xonsh_all_jobs__) == 0:
        return
    builtins.__xonsh_active_job__ = max(builtins.__xonsh_all_jobs__.items(),
                                        key=lambda x: x[1]['started'])[0]


def print_one_job(num):
    """
    Print a line describing job number ``num``.
    """
    job = builtins.__xonsh_all_jobs__[num]
    act = '*' if num == builtins.__xonsh_active_job__ else ' '
    status = job['status']
    cmd = [' '.join(i) if isinstance(i, list) else i for i in job['cmds']]
    cmd = ' '.join(cmd)
    pid = job['pids'][-1]
    bg = ' &' if job['bg'] else ''
    print('{}[{}] {}: {}{} ({})'.format(act, num, status, cmd, bg, pid))


def get_next_job_number():
    """
    Get the lowest available unique job number (for the next job created)
    """
    _clear_dead_jobs()
    i = 1
    while i in builtins.__xonsh_all_jobs__:
        i += 1
    return i


def _default_sigint_handler(num, frame):
    raise KeyboardInterrupt


def wait_for_active_job():
    """
    Wait for the active job to finish, to be killed by SIGINT, or to be
    suspended by ctrl-z.
    """
    _clear_dead_jobs()
    act = builtins.__xonsh_active_job__
    if act is None:
        return
    job = builtins.__xonsh_all_jobs__[act]
    obj = job['obj']
    if isinstance(obj, ProcProxy):
        return
    if job['bg']:
        return
    obj.done = False

    def handle_sigstop(num, frame):
        obj.done = True
        job['status'] = 'stopped'
        job['bg'] = True
        print()
        print_one_job(act)
        os.kill(obj.pid, signal.SIGSTOP)

    def handle_sigint(num, frame):
        obj.done = True
        os.kill(obj.pid, signal.SIGINT)
        raise KeyboardInterrupt

    signal.signal(signal.SIGTSTP, handle_sigstop)
    signal.signal(signal.SIGINT, handle_sigint)
    while obj.poll() is None and not obj.done:
        time.sleep(0.01)
    if obj.poll() is not None:
        builtins.__xonsh_active_job__ = None
    signal.signal(signal.SIGTSTP, signal.SIG_IGN)
    signal.signal(signal.SIGINT, _default_sigint_handler)


def kill_all_jobs():
    """
    Send SIGKILL to all child processes (called when exiting xonsh).
    """
    _clear_dead_jobs()
    for job in builtins.__xonsh_all_jobs__.values():
        os.kill(job['obj'].pid, signal.SIGKILL)


def jobs(args, stdin=None):
    """
    Display a list of all current jobs.
    """
    _clear_dead_jobs()
    for j in sorted(builtins.__xonsh_all_jobs__):
        print_one_job(j)
    return None, None


def fg(args, stdin=None):
    """
    Bring the currently active job to the foreground, or, if a single number is
    given as an argument, bring that job to the foreground.
    """
    _clear_dead_jobs()
    if len(args) == 0:
        # start active job in foreground
        act = builtins.__xonsh_active_job__
        if act is None:
            return '', 'Cannot bring nonexistent job to foreground.'
    elif len(args) == 1:
        try:
            act = int(args[0])
        except:
            return '', 'Invalid job: {}'.format(args[0])
        if act not in builtins.__xonsh_all_jobs__:
            return '', 'Invalid job: {}'.format(args[0])
    else:
        return '', 'fg expects 0 or 1 arguments, not {}'.format(len(args))
    builtins.__xonsh_active_job__ = act
    job = builtins.__xonsh_all_jobs__[act]
    job['bg'] = False
    job['status'] = 'running'
    print_one_job(act)
    os.kill(job['obj'].pid, signal.SIGCONT)


def bg(args, stdin=None):
    """
    Resume execution of the currently active job in the background, or, if a
    single number is given as an argument, resume that job in the background.
    """
    _clear_dead_jobs()
    if len(args) == 0:
        # start active job in foreground
        act = builtins.__xonsh_active_job__
        if act is None:
            return '', 'Cannot send nonexistent job to background.'
    elif len(args) == 1:
        try:
            act = int(args[0])
        except:
            return '', 'Invalid job: {}'.format(args[0])
        if act not in builtins.__xonsh_all_jobs__:
            return '', 'Invalid job: {}'.format(args[0])
    else:
        return '', 'bg expects 0 or 1 arguments, not {}'.format(len(args))
    builtins.__xonsh_active_job__ = act
    job = builtins.__xonsh_all_jobs__[act]
    job['bg'] = True
    job['status'] = 'running'
    print_one_job(act)
    os.kill(job['obj'].pid, signal.SIGCONT)
