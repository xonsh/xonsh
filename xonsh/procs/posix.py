"""Interface for running subprocess-mode commands on posix systems."""

import array
import io
import os
import signal
import subprocess
import sys
import threading
import time

import xonsh.lib.lazyasd as xl
import xonsh.lib.lazyimps as xli
import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.procs.jobs import proc_untraced_waitpid
from xonsh.procs.readers import (
    BufferedFDParallelReader,
    NonBlockingFDReader,
    safe_fdclose,
)

# The following escape codes are xterm codes.
# See http://rtfm.etla.org/xterm/ctlseq.html for more.
MODE_NUMS = ("1049", "47", "1047")


@xl.lazyobject
def START_ALTERNATE_MODE():
    return frozenset(f"\x1b[?{i}h".encode() for i in MODE_NUMS)


@xl.lazyobject
def END_ALTERNATE_MODE():
    return frozenset(f"\x1b[?{i}l".encode() for i in MODE_NUMS)


@xl.lazyobject
def ALTERNATE_MODE_FLAGS():
    return tuple(START_ALTERNATE_MODE) + tuple(END_ALTERNATE_MODE)


class PopenThread(threading.Thread):
    """A thread for running and managing subprocess. This allows reading
    from the stdin, stdout, and stderr streams in a non-blocking fashion.

    This takes the same arguments and keyword arguments as regular Popen.
    This requires that the captured_stdout and captured_stderr attributes
    to be set following instantiation.
    """

    def __init__(self, *args, stdin=None, stdout=None, stderr=None, **kwargs):
        super().__init__()

        self.daemon = True

        self.lock = threading.RLock()
        env = XSH.env
        # stdin setup
        self.orig_stdin = stdin
        if stdin is None:
            self.stdin_fd = 0
        elif isinstance(stdin, int):
            self.stdin_fd = stdin
        else:
            self.stdin_fd = stdin.fileno()
        self.store_stdin = env.get("XONSH_STORE_STDIN")
        self.timeout = env.get("XONSH_PROC_FREQUENCY")
        self.in_alt_mode = False
        self.stdin_mode = None
        self._tc_cc_vsusp = b"\x1a"  # default is usually ^Z
        self._disable_suspend_keybind()
        # stdout setup
        self.orig_stdout = stdout
        self.stdout_fd = 1 if stdout is None else stdout.fileno()
        self._set_pty_size()
        # stderr setup
        self.orig_stderr = stderr
        # Set some signal handles, if we can. Must come before process
        # is started to prevent deadlock on windows
        self.proc = None  # has to be here for closure for handles
        self.old_int_handler = self.old_winch_handler = None
        self.old_tstp_handler = self.old_quit_handler = None
        if xt.on_main_thread():
            self.old_int_handler = signal.signal(signal.SIGINT, self._signal_int)
            if xp.ON_POSIX:
                self.old_tstp_handler = signal.signal(signal.SIGTSTP, self._signal_tstp)
                self.old_quit_handler = signal.signal(signal.SIGQUIT, self._signal_quit)
            if xp.CAN_RESIZE_WINDOW:
                self.old_winch_handler = signal.signal(
                    signal.SIGWINCH, self._signal_winch
                )
        # start up process
        if xp.ON_WINDOWS and stdout is not None:
            os.set_inheritable(stdout.fileno(), False)

        try:
            self.proc = proc = subprocess.Popen(
                *args, stdin=stdin, stdout=stdout, stderr=stderr, **kwargs
            )
        except Exception:
            self._clean_up()
            raise

        self.pid = proc.pid
        self.name = repr(
            {
                "cls": self.__class__.__name__,
                "name": self.name,
                "cmd": args,
                "pid": self.pid,
            }
        )
        self.universal_newlines = uninew = proc.universal_newlines
        if uninew:
            self.encoding = enc = env.get("XONSH_ENCODING")
            self.encoding_errors = err = env.get("XONSH_ENCODING_ERRORS")
            self.stdin = io.BytesIO()  # stdin is always bytes!
            self.stdout = io.TextIOWrapper(io.BytesIO(), encoding=enc, errors=err)
            self.stderr = io.TextIOWrapper(io.BytesIO(), encoding=enc, errors=err)
        else:
            self.encoding = self.encoding_errors = None
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
        self.suspended = False
        self.prevs_are_closed = False
        # This is so the thread will use the same swapped values as the origin one.
        self.original_swapped_values = XSH.env.get_swapped_values()
        self.start()

    def run(self):
        """Runs the subprocess by performing a parallel read on stdin if allowed,
        and copying bytes from captured_stdout to stdout and bytes from
        captured_stderr to stderr.
        """
        # Set the thread-local swapped values.
        XSH.env.set_swapped_values(self.original_swapped_values)
        proc = self.proc
        spec = self._wait_and_getattr("spec")
        # get stdin and apply parallel reader if needed.
        stdin = self.stdin
        if self.orig_stdin is None:
            origin = None
        elif xp.ON_POSIX and self.store_stdin:
            origin = self.orig_stdin
            origfd = origin if isinstance(origin, int) else origin.fileno()
            origin = BufferedFDParallelReader(origfd, buffer=stdin)
        else:
            origin = None
        # get non-blocking stdout
        stdout = self.stdout.buffer if self.universal_newlines else self.stdout
        capout = spec.captured_stdout
        if capout is None:
            procout = None
        else:
            procout = NonBlockingFDReader(capout.fileno(), timeout=self.timeout)
        # get non-blocking stderr
        stderr = self.stderr.buffer if self.universal_newlines else self.stderr
        caperr = spec.captured_stderr
        if caperr is None:
            procerr = None
        else:
            procerr = NonBlockingFDReader(caperr.fileno(), timeout=self.timeout)
        # initial read from buffer
        self._read_write(procout, stdout, sys.__stdout__)
        self._read_write(procerr, stderr, sys.__stderr__)
        # loop over reads while process is running.
        i = j = cnt = 1
        while proc.poll() is None:
            info = proc_untraced_waitpid(proc, hang=False)
            if getattr(proc, "suspended", False):
                self.suspended = True
                if XSH.env.get("XONSH_DEBUG", False):
                    procname = f"{getattr(proc, 'args', '')} {proc.pid}".strip()
                    print(
                        f"Process {procname} suspended with signal {info['signal_name']}.",
                        file=sys.stderr,
                    )

            # this is here for CPU performance reasons.
            if i + j == 0:
                cnt = min(cnt + 1, 1000)
                tout = self.timeout * cnt
                if procout is not None:
                    procout.timeout = tout
                if procerr is not None:
                    procerr.timeout = tout
            elif cnt == 1:
                pass
            else:
                cnt = 1
                if procout is not None:
                    procout.timeout = self.timeout
                if procerr is not None:
                    procerr.timeout = self.timeout
            # redirect some output!
            i = self._read_write(procout, stdout, sys.__stdout__)
            j = self._read_write(procerr, stderr, sys.__stderr__)
            if self.suspended:
                break
        if self.suspended:
            return
        # close files to send EOF to non-blocking reader.
        # capout & caperr seem to be needed only by Windows, while
        # orig_stdout & orig_stderr are need by posix and Windows.
        # Also, order seems to matter here,
        # with orig_* needed to be closed before cap*
        safe_fdclose(self.orig_stdout)
        safe_fdclose(self.orig_stderr)
        if xp.ON_WINDOWS:
            safe_fdclose(capout)
            safe_fdclose(caperr)
        # read in the remaining data in a blocking fashion.
        while (procout is not None and not procout.is_fully_read()) or (
            procerr is not None and not procerr.is_fully_read()
        ):
            self._read_write(procout, stdout, sys.__stdout__)
            self._read_write(procerr, stderr, sys.__stderr__)
        # kill the process if it is still alive. Happens when piping.
        if proc.poll() is None:
            proc.terminate()

    def _wait_and_getattr(self, name):
        """make sure the instance has a certain attr, and return it."""
        while not hasattr(self, name):
            time.sleep(1e-7)
        return getattr(self, name)

    def _read_write(self, reader, writer, stdbuf):
        """Reads a chunk of bytes from a buffer and write into memory or back
        down to the standard buffer, as appropriate. Returns the number of
        successful reads.
        """
        if reader is None:
            return 0
        i = -1
        for i, chunk in enumerate(iter(reader.read_queue, b"")):  # noqa
            self._alt_mode_switch(chunk, writer, stdbuf)
        if i >= 0:
            writer.flush()
            stdbuf.flush()
        return i + 1

    def _alt_mode_switch(self, chunk, membuf, stdbuf):
        """Enables recursively switching between normal capturing mode
        and 'alt' mode, which passes through values to the standard
        buffer. Pagers, text editors, curses applications, etc. use
        alternate mode.
        """
        i, flag = xt.findfirst(chunk, ALTERNATE_MODE_FLAGS)
        if flag is None:
            self._alt_mode_writer(chunk, membuf, stdbuf)
        else:
            # This code is executed when the child process switches the
            # terminal into or out of alternate mode. The line below assumes
            # that the user has opened vim, less, or similar, and writes writes
            # to stdin.
            j = i + len(flag)
            # write the first part of the chunk in the current mode.
            self._alt_mode_writer(chunk[:i], membuf, stdbuf)
            # switch modes
            # write the flag itself the current mode where alt mode is on
            # so that it is streamed to the terminal ASAP.
            # this is needed for terminal emulators to find the correct
            # positions before and after alt mode.
            alt_mode = flag in START_ALTERNATE_MODE
            if alt_mode:
                self.in_alt_mode = alt_mode
                self._alt_mode_writer(flag, membuf, stdbuf)
                self._enable_cbreak_stdin()
            else:
                self._alt_mode_writer(flag, membuf, stdbuf)
                self.in_alt_mode = alt_mode
                self._disable_cbreak_stdin()
            # recurse this function, but without the current flag.
            self._alt_mode_switch(chunk[j:], membuf, stdbuf)

    def _alt_mode_writer(self, chunk, membuf, stdbuf):
        """Write bytes to the standard buffer if in alt mode or otherwise
        to the in-memory buffer.
        """
        if not chunk:
            pass  # don't write empty values
        elif self.in_alt_mode:
            stdbuf.buffer.write(chunk)
        else:
            with self.lock:
                p = membuf.tell()
                membuf.seek(0, io.SEEK_END)
                membuf.write(chunk)
                membuf.seek(p)

    #
    # Window resize handlers
    #

    def _signal_winch(self, signum, frame):
        """Signal handler for SIGWINCH - window size has changed."""
        self.send_signal(signal.SIGWINCH)
        self._set_pty_size()

    def _set_pty_size(self):
        """Sets the window size of the child pty based on the window size of
        our own controlling terminal.
        """
        if xp.ON_WINDOWS or not os.isatty(self.stdout_fd):
            return
        # Get the terminal size of the real terminal, set it on the
        #       pseudoterminal.
        buf = array.array("h", [0, 0, 0, 0])
        # 1 = stdout here
        try:
            xli.fcntl.ioctl(1, xli.termios.TIOCGWINSZ, buf, True)
            xli.fcntl.ioctl(self.stdout_fd, xli.termios.TIOCSWINSZ, buf)
        except OSError:
            pass

    #
    # SIGINT handler
    #

    def _signal_int(self, signum, frame):
        """Signal handler for SIGINT - Ctrl+C may have been pressed."""
        self.send_signal(signal.CTRL_C_EVENT if xp.ON_WINDOWS else signum)
        if self.proc is not None and self.proc.poll() is not None:
            self._restore_sigint(frame=frame)
        if xt.on_main_thread() and not xp.ON_WINDOWS:
            signal.pthread_kill(threading.get_ident(), signal.SIGINT)

    def _restore_sigint(self, frame=None):
        old = self.old_int_handler
        if old is not None:
            if xt.on_main_thread():
                signal.signal(signal.SIGINT, old)
            self.old_int_handler = None
        if frame is not None:
            self._disable_cbreak_stdin()
            if old is not None and old is not self._signal_int:
                old(signal.SIGINT, frame)

    #
    # SIGTSTP handler
    #

    def _signal_tstp(self, signum, frame):
        """Signal handler for suspending SIGTSTP - Ctrl+Z may have been pressed."""
        self.suspended = True
        self.send_signal(signum)
        self._restore_sigtstp(frame=frame)

    def _restore_sigtstp(self, frame=None):
        old = self.old_tstp_handler
        if old is not None:
            if xt.on_main_thread():
                signal.signal(signal.SIGTSTP, old)
            self.old_tstp_handler = None
        if frame is not None:
            self._disable_cbreak_stdin()
        self._restore_suspend_keybind()

    def _disable_suspend_keybind(self):
        if xp.ON_WINDOWS:
            return
        try:
            mode = xli.termios.tcgetattr(0)  # only makes sense for stdin
            self._tc_cc_vsusp = mode[xp.CC][xli.termios.VSUSP]
            mode[xp.CC][xli.termios.VSUSP] = b"\x00"  # set ^Z (ie SIGSTOP) to undefined
            xli.termios.tcsetattr(0, xli.termios.TCSANOW, mode)
        except xli.termios.error:
            return

    def _restore_suspend_keybind(self):
        if xp.ON_WINDOWS:
            return
        try:
            mode = xli.termios.tcgetattr(0)  # only makes sense for stdin
            mode[xp.CC][xli.termios.VSUSP] = (
                self._tc_cc_vsusp
            )  # set ^Z (ie SIGSTOP) to original
            # this usually doesn't work in interactive mode,
            # but we should try it anyway.
            xli.termios.tcsetattr(0, xli.termios.TCSANOW, mode)
        except xli.termios.error:
            pass

    #
    # SIGQUIT handler
    #

    def _signal_quit(self, signum, frame):
        r"""Signal handler for quiting SIGQUIT - Ctrl+\ may have been pressed."""
        self.send_signal(signum)
        self._restore_sigquit(frame=frame)

    def _restore_sigquit(self, frame=None):
        old = self.old_quit_handler
        if old is not None:
            if xt.on_main_thread():
                signal.signal(signal.SIGQUIT, old)
            self.old_quit_handler = None
        if frame is not None:
            self._disable_cbreak_stdin()

    #
    # cbreak mode handlers
    #

    def _enable_cbreak_stdin(self):
        if not xp.ON_POSIX:
            return
        try:
            self.stdin_mode = xli.termios.tcgetattr(self.stdin_fd)[:]
        except xli.termios.error:
            # this can happen for cases where another process is controlling
            # xonsh's tty device, such as in testing.
            self.stdin_mode = None
            return
        new = self.stdin_mode[:]
        new[xp.LFLAG] &= ~(xli.termios.ECHO | xli.termios.ICANON)
        new[xp.CC][xli.termios.VMIN] = 1
        new[xp.CC][xli.termios.VTIME] = 0
        try:
            # termios.TCSAFLUSH may be less reliable than termios.TCSANOW
            xli.termios.tcsetattr(self.stdin_fd, xli.termios.TCSANOW, new)
        except xli.termios.error:
            self._disable_cbreak_stdin()

    def _disable_cbreak_stdin(self):
        if not xp.ON_POSIX or self.stdin_mode is None:
            return
        new = self.stdin_mode[:]
        new[xp.LFLAG] |= xli.termios.ECHO | xli.termios.ICANON
        new[xp.CC][xli.termios.VMIN] = 1
        new[xp.CC][xli.termios.VTIME] = 0
        try:
            xli.termios.tcsetattr(self.stdin_fd, xli.termios.TCSANOW, new)
        except xli.termios.error:
            pass

    #
    # Dispatch methods
    #

    def poll(self):
        """Dispatches to Popen.returncode."""
        return self.proc.returncode

    def wait(self, timeout=None):
        """Dispatches to Popen.wait(), but also does process cleanup such as
        joining this thread and replacing the original window size signal
        handler.
        """
        self._disable_cbreak_stdin()
        rtn = self.proc.wait(timeout=timeout)
        self.join()
        # need to replace the old signal handlers somewhere...
        if self.old_winch_handler is not None and xt.on_main_thread():
            signal.signal(signal.SIGWINCH, self.old_winch_handler)
            self.old_winch_handler = None
        self._clean_up()
        return rtn

    def _clean_up(self):
        self._restore_sigint()
        self._restore_sigtstp()
        self._restore_sigquit()

    @property
    def returncode(self):
        """Process return code."""
        return self.proc.returncode

    @returncode.setter
    def returncode(self, value):
        """Process return code."""
        self.proc.returncode = value

    @property
    def signal(self):
        """Process signal, or None."""
        s = getattr(self.proc, "signal", None)
        if s is None:
            rtn = self.returncode
            if rtn is not None and rtn != 0:
                s = (-1 * rtn, rtn < 0 if xp.ON_WINDOWS else os.WCOREDUMP(rtn))
        return s

    @signal.setter
    def signal(self, value):
        """Process signal, or None."""
        self.proc.signal = value

    def send_signal(self, signal):
        """Dispatches to Popen.send_signal()."""
        dt = 0.0
        while self.proc is None and dt < self.timeout:
            time.sleep(1e-7)
            dt += 1e-7
        if self.proc is None:
            return
        try:
            rtn = self.proc.send_signal(signal)
        except ProcessLookupError:
            # This can happen in the case of !(cmd) when the command has ended
            rtn = None
        return rtn

    def terminate(self):
        """Dispatches to Popen.terminate()."""
        return self.proc.terminate()

    def kill(self):
        """Dispatches to Popen.kill()."""
        return self.proc.kill()
