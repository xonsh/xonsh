# -*- coding: utf-8 -*-
"""Job control for the xonsh shell."""
import os
import sys
import time
import signal
import builtins
from subprocess import TimeoutExpired, check_output
from collections import deque

from xonsh.platform import ON_DARWIN, ON_WINDOWS

tasks = deque()


if ON_DARWIN:
    def _send_signal(job, signal):
        # On OS X, os.killpg() may cause PermissionError when there are
        # any zombie processes in the process group.
        # See github issue #1012 for details
        for pid in job['pids']:
            os.kill(pid, signal)

elif ON_WINDOWS:
    pass

else:
    def _send_signal(job, signal):
        os.killpg(job['pgrp'], signal)


if ON_WINDOWS:
    def _continue(job):
        job['status'] = "running"

    def _kill(job):
        check_output(['taskkill', '/F', '/T', '/PID', str(job['obj'].pid)])

    def ignore_sigtstp():
        pass

    def _set_pgrp(info):
        pass

    def wait_for_active_job(signal_to_send=None):
        """
        Wait for the active job to finish, to be killed by SIGINT, or to be
        suspended by ctrl-z.
        """
        _clear_dead_jobs()

        active_task = get_next_task()

        # Return when there are no foreground active task
        if active_task is None:
            return

        obj = active_task['obj']

        _continue(active_task)

        while obj.returncode is None:
            try:
                obj.wait(0.01)
            except TimeoutExpired:
                pass
            except KeyboardInterrupt:
                _kill(active_task)

        return wait_for_active_job()

else:
    def _continue(job):
        _send_signal(job, signal.SIGCONT)

    def _kill(job):
        _send_signal(job, signal.SIGKILL)

    def ignore_sigtstp():
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)

    def _set_pgrp(info):
        try:
            info['pgrp'] = os.getpgid(info['obj'].pid)
        except ProcessLookupError:
            pass

    _shell_pgrp = os.getpgrp()

    _block_when_giving = (signal.SIGTTOU, signal.SIGTTIN, signal.SIGTSTP)

    def _give_terminal_to(pgid):
        # over-simplified version of:
        #    give_terminal_to from bash 4.3 source, jobs.c, line 4030
        # this will give the terminal to the process group pgid
        if _shell_tty is not None and os.isatty(_shell_tty):
            oldmask = signal.pthread_sigmask(signal.SIG_BLOCK,
                                             _block_when_giving)
            os.tcsetpgrp(_shell_tty, pgid)
            signal.pthread_sigmask(signal.SIG_SETMASK, oldmask)

    # check for shell tty
    try:
        _shell_tty = sys.stderr.fileno()
        if os.tcgetpgrp(_shell_tty) != os.getpgid(os.getpid()):
            # we don't own it
            _shell_tty = None
    except OSError:
        _shell_tty = None

    def wait_for_active_job():
        """
        Wait for the active job to finish, to be killed by SIGINT, or to be
        suspended by ctrl-z.
        """
        _clear_dead_jobs()

        active_task = get_next_task()

        # Return when there are no foreground active task
        if active_task is None:
            _give_terminal_to(_shell_pgrp)  # give terminal back to the shell
            return

        pgrp = active_task['pgrp']
        obj = active_task['obj']
        # give the terminal over to the fg process
        _give_terminal_to(pgrp)

        _continue(active_task)

        _, wcode = os.waitpid(obj.pid, os.WUNTRACED)
        if os.WIFSTOPPED(wcode):
            print()  # get a newline because ^Z will have been printed
            active_task['status'] = "stopped"
        elif os.WIFSIGNALED(wcode):
            print()  # get a newline because ^C will have been printed
            obj.signal = (os.WTERMSIG(wcode), os.WCOREDUMP(wcode))
            obj.returncode = None
        else:
            obj.returncode = os.WEXITSTATUS(wcode)
            obj.signal = None

        return wait_for_active_job()


def get_next_task():
    """ Get the next active task and put it on top of the queue"""
    selected_task = None
    for tid in tasks:
        task = get_task(tid)
        if not task['bg'] and task['status'] == "running":
            selected_task = tid
            break
    if selected_task is None:
        return
    tasks.remove(selected_task)
    tasks.appendleft(selected_task)
    return get_task(selected_task)


def get_task(tid):
    return builtins.__xonsh_all_jobs__[tid]


def _clear_dead_jobs():
    to_remove = set()
    for tid in tasks:
        obj = get_task(tid)['obj']
        if obj.poll() is not None:
            to_remove.add(tid)
    for job in to_remove:
        tasks.remove(job)
        del builtins.__xonsh_all_jobs__[job]


def print_one_job(num):
    """Print a line describing job number ``num``."""
    try:
        job = builtins.__xonsh_all_jobs__[num]
    except KeyError:
        return
    status = job['status']
    cmd = [' '.join(i) if isinstance(i, list) else i for i in job['cmds']]
    cmd = ' '.join(cmd)
    pid = job['pids'][-1]
    bg = ' &' if job['bg'] else ''
    print('[{}] {}: {}{} ({})'.format(num, status, cmd, bg, pid))


def get_next_job_number():
    """Get the lowest available unique job number (for the next job created).
    """
    _clear_dead_jobs()
    i = 1
    while i in builtins.__xonsh_all_jobs__:
        i += 1
    return i


def add_job(info):
    """
    Add a new job to the jobs dictionary.
    """
    num = get_next_job_number()
    info['started'] = time.time()
    info['status'] = "running"
    _set_pgrp(info)
    tasks.appendleft(num)
    builtins.__xonsh_all_jobs__[num] = info
    if info['bg']:
        print_one_job(num)


def kill_all_jobs():
    """
    Send SIGKILL to all child processes (called when exiting xonsh).
    """
    _clear_dead_jobs()
    for job in builtins.__xonsh_all_jobs__.values():
        _kill(job)


def jobs(args, stdin=None):
    """
    xonsh command: jobs

    Display a list of all current jobs.
    """
    _clear_dead_jobs()
    for j in tasks:
        print_one_job(j)
    return None, None


def fg(args, stdin=None):
    """
    xonsh command: fg

    Bring the currently active job to the foreground, or, if a single number is
    given as an argument, bring that job to the foreground.
    """

    _clear_dead_jobs()
    if len(tasks) == 0:
        return '', 'Cannot bring nonexistent job to foreground.\n'

    if len(args) == 0:
        act = tasks[0]  # take the last manipulated task by default
    elif len(args) == 1:
        try:
            act = int(args[0])
        except ValueError:
            return '', 'Invalid job: {}\n'.format(args[0])
        if act not in builtins.__xonsh_all_jobs__:
            return '', 'Invalid job: {}\n'.format(args[0])
    else:
        return '', 'fg expects 0 or 1 arguments, not {}\n'.format(len(args))

    # Put this one on top of the queue
    tasks.remove(act)
    tasks.appendleft(act)

    job = get_task(act)
    job['bg'] = False
    job['status'] = "running"
    print_one_job(act)


def bg(args, stdin=None):
    """
    xonsh command: bg

    Resume execution of the currently active job in the background, or, if a
    single number is given as an argument, resume that job in the background.
    """
    res = fg(args, stdin)
    if res is None:
        curTask = get_task(tasks[0])
        curTask['bg'] = True
        _continue(curTask)
    else:
        return res
