# -*- coding: utf-8 -*-
"""Job control for the xonsh shell."""
import os
import sys
import time
import ctypes
import signal
import builtins
import functools
import subprocess
import collections

from xonsh.lazyasd import LazyObject
from xonsh.platform import ON_DARWIN, ON_WINDOWS, ON_CYGWIN

tasks = LazyObject(collections.deque, globals(), 'tasks')
# Track time stamp of last exit command, so that two consecutive attempts to
# exit can kill all jobs and exit.
_last_exit_time = None


if ON_DARWIN:
    def _send_signal(job, signal):
        # On OS X, os.killpg() may cause PermissionError when there are
        # any zombie processes in the process group.
        # See github issue #1012 for details
        for pid in job['pids']:
            if pid is None:  # the pid of an aliased proc is None
                continue
            os.kill(pid, signal)
elif ON_WINDOWS:
    pass
elif ON_CYGWIN:
    # Similar to what happened on OSX, more issues on Cygwin
    # (see Github issue #514).
    def _send_signal(job, signal):
        try:
            os.killpg(job['pgrp'], signal)
        except Exception:
            for pid in job['pids']:
                try:
                    os.kill(pid, signal)
                except Exception:
                    pass
else:
    def _send_signal(job, signal):
        pgrp = job['pgrp']
        if pgrp is None:
            for pid in job['pids']:
                try:
                    os.kill(pid, signal)
                except Exception:
                    pass
        else:
            os.killpg(job['pgrp'], signal)


if ON_WINDOWS:
    def _continue(job):
        job['status'] = "running"

    def _kill(job):
        subprocess.check_output(['taskkill', '/F', '/T', '/PID',
                                 str(job['obj'].pid)])

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
            except subprocess.TimeoutExpired:
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
        pid = info['pids'][0]
        if pid is None:
            # occurs if first process is an alias
            info['pgrp'] = None
            return
        try:
            info['pgrp'] = os.getpgid(pid)
        except ProcessLookupError:
            info['pgrp'] = None

    _shell_pgrp = os.getpgrp()

    _block_when_giving = LazyObject(lambda: (signal.SIGTTOU, signal.SIGTTIN,
                                             signal.SIGTSTP, signal.SIGCHLD),
                                    globals(), '_block_when_giving')

    # check for shell tty
    @functools.lru_cache(1)
    def _shell_tty():
        try:
            _st = sys.stderr.fileno()
            if os.tcgetpgrp(_st) != os.getpgid(os.getpid()):
                # we don't own it
                _st = None
        except OSError:
            _st = None
        return _st

    # _give_terminal_to is a simplified version of:
    #    give_terminal_to from bash 4.3 source, jobs.c, line 4030
    # this will give the terminal to the process group pgid
    if ON_CYGWIN:
        _libc = LazyObject(lambda: ctypes.CDLL('cygwin1.dll'),
                           globals(), '_libc')

        # on cygwin, signal.pthread_sigmask does not exist in Python, even
        # though pthread_sigmask is defined in the kernel.  thus, we use
        # ctypes to mimic the calls in the "normal" version below.
        def _give_terminal_to(pgid):
            st = _shell_tty()
            if st is not None and os.isatty(st):
                omask = ctypes.c_ulong()
                mask = ctypes.c_ulong()
                _libc.sigemptyset(ctypes.byref(mask))
                for i in _block_when_giving:
                    _libc.sigaddset(ctypes.byref(mask), ctypes.c_int(i))
                _libc.sigemptyset(ctypes.byref(omask))
                _libc.sigprocmask(ctypes.c_int(signal.SIG_BLOCK),
                                  ctypes.byref(mask),
                                  ctypes.byref(omask))
                _libc.tcsetpgrp(ctypes.c_int(st), ctypes.c_int(pgid))
                _libc.sigprocmask(ctypes.c_int(signal.SIG_SETMASK),
                                  ctypes.byref(omask), None)
    else:
        def _give_terminal_to(pgid):
            st = _shell_tty()
            if st is not None and os.isatty(st):
                oldmask = signal.pthread_sigmask(signal.SIG_BLOCK,
                                                 _block_when_giving)
                os.tcsetpgrp(st, pgid)
                signal.pthread_sigmask(signal.SIG_SETMASK, oldmask)

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
        pgrp = active_task.get('pgrp', None)
        obj = active_task['obj']
        # give the terminal over to the fg process
        if pgrp is not None:
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


def print_one_job(num, outfile=sys.stdout):
    """Print a line describing job number ``num``."""
    try:
        job = builtins.__xonsh_all_jobs__[num]
    except KeyError:
        return
    pos = '+' if tasks[0] == num else '-' if tasks[1] == num else ' '
    status = job['status']
    cmd = [' '.join(i) if isinstance(i, list) else i for i in job['cmds']]
    cmd = ' '.join(cmd)
    pid = job['pids'][-1]
    bg = ' &' if job['bg'] else ''
    print('[{}]{} {}: {}{} ({})'.format(num, pos, status, cmd, bg, pid),
          file=outfile)


def get_next_job_number():
    """Get the lowest available unique job number (for the next job created).
    """
    _clear_dead_jobs()
    i = 1
    while i in builtins.__xonsh_all_jobs__:
        i += 1
    return i


def add_job(info):
    """Add a new job to the jobs dictionary."""
    num = get_next_job_number()
    info['started'] = time.time()
    info['status'] = "running"
    _set_pgrp(info)
    tasks.appendleft(num)
    builtins.__xonsh_all_jobs__[num] = info
    if info['bg']:
        print_one_job(num)


def clean_jobs():
    """Clean up jobs for exiting shell

    In non-interactive mode, kill all jobs.

    In interactive mode, check for suspended or background jobs, print a
    warning if any exist, and return False. Otherwise, return True.
    """
    jobs_clean = True
    if builtins.__xonsh_env__['XONSH_INTERACTIVE']:
        _clear_dead_jobs()

        if builtins.__xonsh_all_jobs__:
            global _last_exit_time
            hist = builtins.__xonsh_history__
            if hist is not None and hist.buffer:
                last_cmd_start = builtins.__xonsh_history__.buffer[-1]['ts'][0]
            else:
                last_cmd_start = None

            if (_last_exit_time and last_cmd_start and
                    _last_exit_time > last_cmd_start):
                # Exit occurred after last command started, so it was called as
                # part of the last command and is now being called again
                # immediately. Kill jobs and exit without reminder about
                # unfinished jobs in this case.
                kill_all_jobs()
            else:
                if len(builtins.__xonsh_all_jobs__) > 1:
                    msg = 'there are unfinished jobs'
                else:
                    msg = 'there is an unfinished job'

                if builtins.__xonsh_env__['SHELL_TYPE'] != 'prompt_toolkit':
                    # The Ctrl+D binding for prompt_toolkit already inserts a
                    # newline
                    print()
                print('xonsh: {}'.format(msg), file=sys.stderr)
                print('-'*5, file=sys.stderr)
                jobs([], stdout=sys.stderr)
                print('-'*5, file=sys.stderr)
                print('Type "exit" or press "ctrl-d" again to force quit.',
                      file=sys.stderr)
                jobs_clean = False
                _last_exit_time = time.time()
    else:
        kill_all_jobs()

    return jobs_clean


def kill_all_jobs():
    """
    Send SIGKILL to all child processes (called when exiting xonsh).
    """
    _clear_dead_jobs()
    for job in builtins.__xonsh_all_jobs__.values():
        _kill(job)


def jobs(args, stdin=None, stdout=sys.stdout, stderr=None):
    """
    xonsh command: jobs

    Display a list of all current jobs.
    """
    _clear_dead_jobs()
    for j in tasks:
        print_one_job(j, outfile=stdout)
    return None, None


def fg(args, stdin=None):
    """
    xonsh command: fg

    Bring the currently active job to the foreground, or, if a single number is
    given as an argument, bring that job to the foreground. Additionally,
    specify "+" for the most recent job and "-" for the second most recent job.
    """

    _clear_dead_jobs()
    if len(tasks) == 0:
        return '', 'Cannot bring nonexistent job to foreground.\n'

    if len(args) == 0:
        act = tasks[0]  # take the last manipulated task by default
    elif len(args) == 1:
        try:
            if args[0] == '+':  # take the last manipulated task
                act = tasks[0]
            elif args[0] == '-':  # take the second to last manipulated task
                act = tasks[1]
            else:
                act = int(args[0])
        except (ValueError, IndexError):
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
    """xonsh command: bg

    Resume execution of the currently active job in the background, or, if a
    single number is given as an argument, resume that job in the background.
    """
    res = fg(args, stdin)
    if res is None:
        curtask = get_task(tasks[0])
        curtask['bg'] = True
        _continue(curtask)
    else:
        return res
