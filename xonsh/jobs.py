# -*- coding: utf-8 -*-
"""Job control for the xonsh shell."""
import os
import sys
import time
import signal
import builtins
from subprocess import TimeoutExpired
from io import BytesIO

from xonsh.tools import ON_WINDOWS


if ON_WINDOWS:
    def _continue(obj):
        return None


    def _kill(obj):
        return obj.kill()


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
        act = builtins.__xonsh_active_job__
        if act is None:
            return
        job = builtins.__xonsh_all_jobs__[act]
        obj = job['obj']
        if job['bg']:
            return
        while obj.returncode is None:
            try:
                obj.wait(0.01)
            except TimeoutExpired:
                pass
            except KeyboardInterrupt:
                obj.kill()
        if obj.poll() is not None:
            builtins.__xonsh_active_job__ = None

else:
    def _continue(obj):
        return signal.SIGCONT


    def _kill(obj):
        os.kill(obj.pid, signal.SIGKILL)


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
            oldmask = signal.pthread_sigmask(signal.SIG_BLOCK, _block_when_giving)
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


    def wait_for_active_job(signal_to_send=None):
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
        if job['bg'] and job['status'] == 'running':
            return
        pgrp = job['pgrp']

        # give the terminal over to the fg process
        _give_terminal_to(pgrp)
        # if necessary, send the specified signal to this process
        # (this hook  was added because vim, emacs, etc, seem to need to have
        # the terminal when they receive SIGCONT from the "fg" command)
        if signal_to_send is not None:
            if signal_to_send == signal.SIGCONT:
                job['status'] = 'running'

            os.kill(obj.pid, signal_to_send)

            if job['bg']:
                _give_terminal_to(_shell_pgrp)
                return

        _, wcode = os.waitpid(obj.pid, os.WUNTRACED)
        if os.WIFSTOPPED(wcode):
            job['bg'] = True
            job['status'] = 'stopped'
            print()  # get a newline because ^Z will have been printed
            print_one_job(act)
        elif os.WIFSIGNALED(wcode):
            print()  # get a newline because ^C will have been printed
            obj.signal = (os.WTERMSIG(wcode), os.WCOREDUMP(wcode))
            obj.returncode = None
        else:
            obj.returncode = os.WEXITSTATUS(wcode)
            obj.signal = None

        if obj.poll() is not None:
            builtins.__xonsh_active_job__ = None

        _give_terminal_to(_shell_pgrp)  # give terminal back to the shell


def _clear_dead_jobs():
    to_remove = set()
    for num, job in builtins.__xonsh_all_jobs__.items():
        obj = job['obj']
        if obj.poll() is not None:
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
    """Print a line describing job number ``num``."""
    try:
        job = builtins.__xonsh_all_jobs__[num]
    except KeyError:
        return
    act = '*' if num == builtins.__xonsh_active_job__ else ' '
    status = job['status']
    cmd = [' '.join(i) if isinstance(i, list) else i for i in job['cmds']]
    cmd = ' '.join(cmd)
    pid = job['pids'][-1]
    bg = ' &' if job['bg'] else ''
    print('{}[{}] {}: {}{} ({})'.format(act, num, status, cmd, bg, pid))


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
    info['started'] = time.time()
    info['status'] = 'running'
    _set_pgrp(info)
    num = get_next_job_number()
    builtins.__xonsh_all_jobs__[num] = info
    builtins.__xonsh_active_job__ = num
    if info['bg']:
        print_one_job(num)


def _default_sigint_handler(num, frame):
    raise KeyboardInterrupt


def kill_all_jobs():
    """
    Send SIGKILL to all child processes (called when exiting xonsh).
    """
    _clear_dead_jobs()
    for job in builtins.__xonsh_all_jobs__.values():
        _kill(job['obj'])


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
        except ValueError:
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
    wait_for_active_job(_continue(job['obj']))


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
        except ValueError:
            return '', 'Invalid job: {}\n'.format(args[0])
        if act not in builtins.__xonsh_all_jobs__:
            return '', 'Invalid job: {}\n'.format(args[0])
    else:
        return '', 'bg expects 0 or 1 arguments, not {}\n'.format(len(args))
    builtins.__xonsh_active_job__ = act
    job = builtins.__xonsh_all_jobs__[act]
    job['bg'] = True
    # When the SIGCONT is sent job['status'] is set to running.
    print_one_job(act)
    wait_for_active_job(_continue(job['obj']))
