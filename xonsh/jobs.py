"""
Job control for the xonsh shell.
"""
import os
import sys
import time
import signal
import builtins
from collections import namedtuple

ProcProxy = namedtuple('ProcProxy', ['stdout', 'stderr'])
"""
A class representing a Python function to be run as a subprocess command.
"""

try:
    _shell_tty = sys.stderr.fileno()
except OSError:
    _shell_tty = None

_shell_pgrp = os.getpgrp()


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


_block_when_giving = (signal.SIGTTOU, signal.SIGTTIN, signal.SIGTSTP)


def _give_terminal_to(pgid):
    # over-simplified version of:
    #    give_terminal_to from bash 4.3 source, jobs.c, line 4030
    # this will give the terminal to the process group pgid
    if _shell_tty is not None:
        oldmask = signal.pthread_sigmask(signal.SIG_BLOCK, _block_when_giving)
        os.tcsetpgrp(_shell_tty, pgid)
        signal.pthread_sigmask(signal.SIG_SETMASK, oldmask)


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
    pgrp = job['pgrp']
    obj.done = False

    _give_terminal_to(pgrp)  # give the terminal over to the fg process
    p, s = os.waitpid(obj.pid, os.WUNTRACED)
    if os.WIFSTOPPED(s):
        obj.done = True
        job['bg'] = True
        job['status'] = 'stopped'
        print()  # get a newline because ^Z will have been printed
        print_one_job(act)
    elif os.WIFSIGNALED(s):
        print()  # get a newline because ^C will have been printed
    if obj.poll() is not None:
        builtins.__xonsh_active_job__ = None
    _give_terminal_to(_shell_pgrp)  # give terminal back to the shell


def kill_all_jobs():
    """
    Send SIGKILL to all child processes (called when exiting xonsh).
    """
    _clear_dead_jobs()
    for job in builtins.__xonsh_all_jobs__.values():
        os.kill(job['obj'].pid, signal.SIGKILL)


def jobs(args, stdin=None):
    """
    xonsh command: jobs

    Display a list of all current jobs.
    """
    _clear_dead_jobs()
    for j in sorted(builtins.__xonsh_all_jobs__):
        print_one_job(j)
    return None, None


def fg(args, stdin=None):
    """
    xonsh command: fg

    Bring the currently active job to the foreground, or, if a single number is
    given as an argument, bring that job to the foreground.
    """
    _clear_dead_jobs()
    if len(args) == 0:
        # start active job in foreground
        act = builtins.__xonsh_active_job__
        if act is None:
            return '', 'Cannot bring nonexistent job to foreground.\n'
    elif len(args) == 1:
        try:
            act = int(args[0])
        except:
            return '', 'Invalid job: {}\n'.format(args[0])
        if act not in builtins.__xonsh_all_jobs__:
            return '', 'Invalid job: {}\n'.format(args[0])
    else:
        return '', 'fg expects 0 or 1 arguments, not {}\n'.format(len(args))
    builtins.__xonsh_active_job__ = act
    job = builtins.__xonsh_all_jobs__[act]
    job['bg'] = False
    job['status'] = 'running'
    print_one_job(act)
    os.kill(job['obj'].pid, signal.SIGCONT)


def bg(args, stdin=None):
    """
    xonsh command: bg

    Resume execution of the currently active job in the background, or, if a
    single number is given as an argument, resume that job in the background.
    """
    _clear_dead_jobs()
    if len(args) == 0:
        # start active job in foreground
        act = builtins.__xonsh_active_job__
        if act is None:
            return '', 'Cannot send nonexistent job to background.\n'
    elif len(args) == 1:
        try:
            act = int(args[0])
        except:
            return '', 'Invalid job: {}\n'.format(args[0])
        if act not in builtins.__xonsh_all_jobs__:
            return '', 'Invalid job: {}\n'.format(args[0])
    else:
        return '', 'bg expects 0 or 1 arguments, not {}\n'.format(len(args))
    builtins.__xonsh_active_job__ = act
    job = builtins.__xonsh_all_jobs__[act]
    job['bg'] = True
    job['status'] = 'running'
    print_one_job(act)
    os.kill(job['obj'].pid, signal.SIGCONT)
