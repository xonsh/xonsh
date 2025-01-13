"""Job control for the xonsh shell."""

import collections
import contextlib
import ctypes
import os
import signal
import subprocess
import sys
import threading
import time
import typing as tp

from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.completers.tools import RichCompletion
from xonsh.lib.lazyasd import LazyObject
from xonsh.platform import FD_STDERR, LIBC, ON_CYGWIN, ON_DARWIN, ON_MSYS, ON_WINDOWS
from xonsh.tools import get_signal_name, on_main_thread, unthreadable

# Track time stamp of last exit command, so that two consecutive attempts to
# exit can kill all jobs and exit.
_last_exit_time: tp.Optional[float] = None

# Thread-local data for job control. Allows threadable callable aliases
# (ProcProxyThread) to maintain job control information separate from the main
# thread.
#
# _jobs_thread_local.tasks is a queue used to keep track of the tasks. On
# the main thread, it is set to _tasks_main.
#
# _jobs_thread_local.jobs is a dictionary used to keep track of the jobs.
# On the main thread, it is set to XSH.all_jobs.
_jobs_thread_local = threading.local()

# Task queue for the main thread
# The use_main_jobs context manager uses this variable to access the tasks on
# the main thread.
_tasks_main: collections.deque[int] = collections.deque()


def proc_untraced_waitpid(proc, hang, task=None, raise_child_process_error=False):
    """
    Read a stop signals from the process and update the process state.

    Return code
    ===========

    Basically ``p = subprocess.Popen()`` populates ``p.returncode`` after ``p.wait()``, ``p.poll()``
    or ``p.communicate()`` (https://docs.python.org/3/library/os.html#os.waitpid).
    But if you're using `os.waitpid()` BEFORE these functions you're capturing return code
    from a signal subsystem and ``p.returncode`` will be ``0``.
    After ``os.waitid`` call you need to set return code and process signal manually.
    See also ``xonsh.tools.describe_waitpid_status()``.

    Signals
    =======

    The command that is waiting for input can be suspended by OS in case there is no terminal attached
    because without terminal command will never end. Read more about SIGTTOU and SIGTTIN signals:
     * https://www.linusakesson.net/programming/tty/
     * http://curiousthing.org/sigttin-sigttou-deep-dive-linux
     * https://www.gnu.org/software/libc/manual/html_node/Job-Control-Signals.html
    """

    info = {"backgrounded": False, "signal": None, "signal_name": None}

    if ON_WINDOWS:
        return info

    if proc is not None and getattr(proc, "pid", None) is None:
        """
        When the process stopped before os.waitpid it has no pid.
        Note that in this case there is high probability
        that we will have return code 0 instead of real return code.
        """
        if raise_child_process_error:
            raise ChildProcessError("Process Identifier (PID) not found.")
        else:
            return info

    try:
        """
        The WUNTRACED flag indicates that the caller wishes to wait for stopped or terminated
        child processes, but doesn't want to return information about them. A stopped process is one
        that has been suspended and is waiting to be resumed or terminated.
        """
        opt = os.WUNTRACED if hang else (os.WUNTRACED | os.WNOHANG)
        wpid, wcode = os.waitpid(proc.pid, opt)
    except ChildProcessError:
        wpid, wcode = 0, 0
        if raise_child_process_error:
            raise

    if wpid == 0:
        # Process has no changes in state.
        pass

    elif os.WIFSTOPPED(wcode):
        if task is not None:
            task["status"] = "stopped"
        info["backgrounded"] = True
        proc.signal = (os.WSTOPSIG(wcode), os.WCOREDUMP(wcode))
        info["signal"] = os.WSTOPSIG(wcode)
        proc.suspended = True

    elif os.WIFSIGNALED(wcode):
        print()  # get a newline because ^C will have been printed
        proc.signal = (os.WTERMSIG(wcode), os.WCOREDUMP(wcode))
        proc.returncode = -os.WTERMSIG(wcode)  # Popen default.
        info["signal"] = os.WTERMSIG(wcode)

    else:
        proc.returncode = os.WEXITSTATUS(wcode)
        proc.signal = None
        info["signal"] = None

    info["signal_name"] = f'{info["signal"]} {get_signal_name(info["signal"])}'.strip()
    return info


@contextlib.contextmanager
def use_main_jobs():
    """Context manager that replaces a thread's task queue and job dictionary
    with those of the main thread

    This allows another thread (e.g. the commands jobs, disown, and bg) to
    handle the main thread's job control.
    """
    old_tasks = get_tasks()
    old_jobs = get_jobs()
    try:
        _jobs_thread_local.tasks = _tasks_main
        _jobs_thread_local.jobs = XSH.all_jobs
        yield
    finally:
        _jobs_thread_local.tasks = old_tasks
        _jobs_thread_local.jobs = old_jobs


def get_tasks() -> collections.deque[int]:
    try:
        return _jobs_thread_local.tasks
    except AttributeError:
        if on_main_thread():
            _jobs_thread_local.tasks = _tasks_main
        else:
            _jobs_thread_local.tasks = collections.deque()
        return _jobs_thread_local.tasks


def get_jobs() -> dict[int, dict]:
    try:
        return _jobs_thread_local.jobs
    except AttributeError:
        if on_main_thread():
            _jobs_thread_local.jobs = XSH.all_jobs
        else:
            _jobs_thread_local.jobs = {}
        return _jobs_thread_local.jobs


if ON_DARWIN:

    def _send_signal(job, signal):
        # On OS X, os.killpg() may cause PermissionError when there are
        # any zombie processes in the process group.
        # See github issue #1012 for details
        for pid in job["pids"]:
            if pid is None:  # the pid of an aliased proc is None
                continue
            try:
                os.kill(pid, signal)
            except ProcessLookupError:
                pass

elif ON_WINDOWS:
    pass
elif ON_CYGWIN or ON_MSYS:
    # Similar to what happened on OSX, more issues on Cygwin
    # (see Github issue #514).
    def _send_signal(job, signal):
        try:
            os.killpg(job["pgrp"], signal)
        except Exception:
            for pid in job["pids"]:
                try:
                    os.kill(pid, signal)
                except Exception:
                    pass

else:

    def _send_signal(job, signal):
        pgrp = job["pgrp"]
        if pgrp is None:
            for pid in job["pids"]:
                try:
                    os.kill(pid, signal)
                except Exception:
                    pass
        else:
            os.killpg(job["pgrp"], signal)


if ON_WINDOWS:

    def _continue(job):
        job["status"] = "running"

    def _kill(job):
        subprocess.check_output(
            ["taskkill", "/F", "/T", "/PID", str(job["obj"].pid)],
            stderr=subprocess.STDOUT,
        )

    _hup = _kill  # there is no equivalent of SIGHUP on Windows

    def ignore_sigtstp():
        pass

    def give_terminal_to(pgid):
        pass

    def wait_for_active_job(last_task=None, backgrounded=False, return_error=False):
        """
        Wait for the active job to finish, to be killed by SIGINT, or to be
        suspended by ctrl-z.
        """
        active_task = get_next_task()
        # Return when there are no foreground active task
        if active_task is None:
            return last_task
        proc = active_task["obj"]
        _continue(active_task)
        while proc.returncode is None:
            try:
                proc.wait(0.01)
            except subprocess.TimeoutExpired:
                pass
            except KeyboardInterrupt:
                try:
                    _kill(active_task)
                except subprocess.CalledProcessError:
                    pass  # ignore error if process closed before we got here
        return wait_for_active_job(last_task=active_task)

else:

    def _continue(job):
        _send_signal(job, signal.SIGCONT)
        job["status"] = "running"

    def _kill(job):
        _send_signal(job, signal.SIGKILL)

    def _hup(job):
        _send_signal(job, signal.SIGHUP)

    def ignore_sigtstp():
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)

    _shell_pgrp = os.getpgrp()  # type:ignore

    _block_when_giving = LazyObject(
        lambda: (
            signal.SIGTTOU,  # type:ignore
            signal.SIGTTIN,  # type:ignore
            signal.SIGTSTP,  # type:ignore
            signal.SIGCHLD,  # type:ignore
        ),
        globals(),
        "_block_when_giving",
    )

    if ON_CYGWIN or ON_MSYS:
        # on cygwin, signal.pthread_sigmask does not exist in Python, even
        # though pthread_sigmask is defined in the kernel.  thus, we use
        # ctypes to mimic the calls in the "normal" version below.
        LIBC.pthread_sigmask.restype = ctypes.c_int
        LIBC.pthread_sigmask.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
        ]

        def _pthread_sigmask(how, signals):
            mask = 0
            for sig in signals:
                mask |= 1 << sig
            oldmask = ctypes.c_ulong()
            mask = ctypes.c_ulong(mask)
            result = LIBC.pthread_sigmask(
                how, ctypes.byref(mask), ctypes.byref(oldmask)
            )
            if result:
                raise OSError(result, "Sigmask error.")

            return {
                sig
                for sig in getattr(signal, "Signals", range(0, 65))
                if (oldmask.value >> sig) & 1
            }

    else:
        _pthread_sigmask = signal.pthread_sigmask  # type:ignore

    # give_terminal_to is a simplified version of:
    #    give_terminal_to from bash 4.3 source, jobs.c, line 4030
    # this will give the terminal to the process group pgid
    def give_terminal_to(pgid):
        if pgid is None:
            return False
        oldmask = _pthread_sigmask(signal.SIG_BLOCK, _block_when_giving)
        try:
            os.tcsetpgrp(FD_STDERR, pgid)
            return True
        except ProcessLookupError:
            # when the process finished before giving terminal to it,
            # see issue #2288
            return False
        except OSError as e:
            if e.errno == 22:  # [Errno 22] Invalid argument
                # there are cases that all the processes of pgid have
                # finished, then we don't need to do anything here, see
                # issue #2220
                return False
            elif e.errno == 25:  # [Errno 25] Inappropriate ioctl for device
                # There are also cases where we are not connected to a
                # real TTY, even though we may be run in interactive
                # mode. See issue #2267 for an example with emacs
                return False
            else:
                raise
        finally:
            _pthread_sigmask(signal.SIG_SETMASK, oldmask)

    def wait_for_active_job(last_task=None, backgrounded=False, return_error=False):
        """
        Wait for the active job to finish, to be killed by SIGINT, or to be
        suspended by ctrl-z.
        """
        active_task = get_next_task()
        # Return when there are no foreground active task
        if active_task is None:
            return last_task
        proc = active_task["obj"]
        info = {"backgrounded": False}

        try:
            info = proc_untraced_waitpid(
                proc, hang=True, task=active_task, raise_child_process_error=True
            )
        except ChildProcessError as e:
            if return_error:
                return e
            else:
                return _safe_wait_for_active_job(
                    last_task=active_task, backgrounded=info["backgrounded"]
                )
        return wait_for_active_job(
            last_task=active_task, backgrounded=info["backgrounded"]
        )


def _safe_wait_for_active_job(last_task=None, backgrounded=False):
    """Safely call wait_for_active_job()"""
    have_error = True
    while have_error:
        try:
            rtn = wait_for_active_job(
                last_task=last_task, backgrounded=backgrounded, return_error=True
            )
        except ChildProcessError as e:
            rtn = e
        have_error = isinstance(rtn, ChildProcessError)
    return rtn


def get_next_task():
    """Get the next active task and put it on top of the queue"""
    tasks = get_tasks()
    _clear_dead_jobs()
    selected_task = None
    for tid in tasks:
        task = get_task(tid)
        if not task["bg"] and task["status"] == "running":
            selected_task = tid
            break
    if selected_task is None:
        return
    tasks.remove(selected_task)
    tasks.appendleft(selected_task)
    return get_task(selected_task)


def get_task(tid):
    return get_jobs()[tid]


def _clear_dead_jobs():
    to_remove = set()
    tasks = get_tasks()
    for tid in tasks:
        proc = get_task(tid)["obj"]
        if proc is None or proc.poll() is not None:
            to_remove.add(tid)
    for job in to_remove:
        tasks.remove(job)
        del get_jobs()[job]


def format_job_string(num: int, format="dict") -> str:
    try:
        job = get_jobs()[num]
    except KeyError:
        return ""
    tasks = get_tasks()
    r = {
        "num": num,
        "status": job["status"],
        "cmd": " ".join(
            [" ".join(i) if isinstance(i, list) else i for i in job["cmds"]]
        ),
        "pids": job["pids"] if "pids" in job else None,
    }

    if format == "posix":
        r["pos"] = "+" if tasks[0] == num else "-" if tasks[1] == num else " "
        r["bg"] = " &" if job["bg"] else ""
        r["pid"] = f"({','.join(str(pid) for pid in r['pids'])})" if r["pids"] else ""
        return "[{num}]{pos} {status}: {cmd}{bg} {pid}".format(**r)
    else:
        return repr(r)


def print_one_job(num, outfile=sys.stdout, format="dict"):
    """Print a line describing job number ``num``."""
    info = format_job_string(num, format)
    if info:
        print(info, file=outfile)


def get_next_job_number():
    """Get the lowest available unique job number (for the next job created)."""
    _clear_dead_jobs()
    i = 1
    while i in get_jobs():
        i += 1
    return i


def add_job(info):
    """Add a new job to the jobs dictionary."""
    num = get_next_job_number()
    info["started"] = time.time()
    info["status"] = info["status"] if "status" in info else "running"
    get_tasks().appendleft(num)
    get_jobs()[num] = info
    if (
        not info["pipeline"].spec.captured == "object"
        and info["bg"]
        and XSH.env.get("XONSH_INTERACTIVE")
    ):
        print_one_job(num)


def update_job_attr(pid, name, value):
    """Update job attribute."""
    jobs = get_jobs()
    for num, job in get_jobs().items():
        if "pids" in job and pid in job["pids"]:
            jobs[num][name] = value


def clean_jobs():
    """Clean up jobs for exiting shell

    In non-interactive mode, send SIGHUP to all jobs.

    In interactive mode, check for suspended or background jobs, print a
    warning if any exist, and return False. Otherwise, return True.
    """
    jobs_clean = True
    if XSH.env["XONSH_INTERACTIVE"]:
        _clear_dead_jobs()

        if get_jobs():
            global _last_exit_time
            hist = XSH.history
            if hist is not None and len(hist.tss) > 0:
                last_cmd_start = hist.tss[-1][0]
            else:
                last_cmd_start = None

            if _last_exit_time and last_cmd_start and _last_exit_time > last_cmd_start:
                # Exit occurred after last command started, so it was called as
                # part of the last command and is now being called again
                # immediately. Kill jobs and exit without reminder about
                # unfinished jobs in this case.
                hup_all_jobs()
            else:
                if len(get_jobs()) > 1:
                    msg = "there are unfinished jobs"
                else:
                    msg = "there is an unfinished job"

                if XSH.env["SHELL_TYPE"] != "prompt_toolkit":
                    # The Ctrl+D binding for prompt_toolkit already inserts a
                    # newline
                    print()
                print(f"xonsh: {msg}", file=sys.stderr)
                print("-" * 5, file=sys.stderr)
                jobs([], stdout=sys.stderr)
                print("-" * 5, file=sys.stderr)
                print(
                    'Type "exit" or press "ctrl-d" again to force quit.',
                    file=sys.stderr,
                )
                jobs_clean = False
                _last_exit_time = time.time()
    else:
        hup_all_jobs()

    return jobs_clean


def hup_all_jobs():
    """
    Send SIGHUP to all child processes (called when exiting xonsh).
    """
    _clear_dead_jobs()
    for job in get_jobs().values():
        _hup(job)


@use_main_jobs()
def jobs(args, stdin=None, stdout=sys.stdout, stderr=None):
    """
    xonsh command: jobs

    Display a list of all current jobs.
    """
    _clear_dead_jobs()
    format = "posix" if "--posix" in args else "dict"
    for j in get_tasks():
        print_one_job(j, outfile=stdout, format=format)
    return None, None


def resume_job(args, wording: tp.Literal["fg", "bg"]):
    """
    used by fg and bg to resume a job either in the foreground or in the background.
    """
    _clear_dead_jobs()
    tasks = get_tasks()
    if len(tasks) == 0:
        return "", "There are currently no suspended jobs"

    if len(args) == 0:
        tid = tasks[0]  # take the last manipulated task by default
    elif len(args) == 1:
        try:
            if args[0] == "+":  # take the last manipulated task
                tid = tasks[0]
            elif args[0] == "-":  # take the second to last manipulated task
                tid = tasks[1]
            else:
                tid = int(args[0])
        except (ValueError, IndexError):
            return "", f"Invalid job: {args[0]}\n"

        if tid not in get_jobs():
            return "", f"Invalid job: {args[0]}\n"
    else:
        return "", f"{wording} expects 0 or 1 arguments, not {len(args)}\n"

    # Put this one on top of the queue
    tasks.remove(tid)
    tasks.appendleft(tid)

    job = get_task(tid)
    job["bg"] = False
    job["status"] = "running"
    if XSH.env.get("XONSH_INTERACTIVE"):
        print_one_job(tid)
    pipeline = job["pipeline"]
    pipeline.resume(
        job, tee_output=(wording == "fg")
    )  # do not tee output for background jobs


@unthreadable
def fg(args, stdin=None):
    """
    xonsh command: fg

    Bring the currently active job to the foreground, or, if a single number is
    given as an argument, bring that job to the foreground. Additionally,
    specify "+" for the most recent job and "-" for the second most recent job.
    """
    return resume_job(args, wording="fg")


@use_main_jobs()
def bg(args, stdin=None):
    """xonsh command: bg

    Resume execution of the currently active job in the background, or, if a
    single number is given as an argument, resume that job in the background.
    """
    res = resume_job(args, wording="bg")
    if res is None:
        curtask = get_task(get_tasks()[0])
        curtask["bg"] = True
        _continue(curtask)
    else:
        return res


def job_id_completer(xsh, **_):
    """Return currently running jobs ids"""
    for job_id in get_jobs():
        yield RichCompletion(str(job_id), description=format_job_string(job_id))


@use_main_jobs()
def disown_fn(
    job_ids: Annotated[
        tp.Sequence[int], Arg(type=int, nargs="*", completer=job_id_completer)
    ],
    force_auto_continue=False,
):
    """Remove the specified jobs from the job table; the shell will no longer
    report their status, and will not complain if you try to exit an
    interactive shell with them running or stopped.

    If the jobs are currently stopped and the $AUTO_CONTINUE option is not set
    ($AUTO_CONTINUE = False), a warning is printed containing information about
    how to make them continue after they have been disowned.

    Parameters
    ----------
    job_ids
        Jobs to act on or none to disown the current job
    force_auto_continue : -c, --continue
        Automatically continue stopped jobs when they are disowned, equivalent to setting $AUTO_CONTINUE=True
    """

    tasks = get_tasks()
    if len(tasks) == 0:
        return "", "There are no active jobs"

    messages = []
    # if args.job_ids is empty, use the active task
    for tid in job_ids or [tasks[0]]:
        try:
            current_task = get_task(tid)
        except KeyError:
            return "", f"'{tid}' is not a valid job ID"

        auto_cont = XSH.env.get("AUTO_CONTINUE", False)
        if auto_cont or force_auto_continue:
            _continue(current_task)
        elif current_task["status"] == "stopped":
            messages.append(
                f"warning: job is suspended, use "
                f"'kill -CONT -{current_task['pids'][-1]}' "
                f"to resume\n"
            )

        # Stop tracking this task
        tasks.remove(tid)
        del get_jobs()[tid]
        messages.append(f"Removed job {tid} ({current_task['status']})")

    if messages:
        return "".join(messages)


disown = ArgParserAlias(prog="disown", func=disown_fn, has_args=True)
