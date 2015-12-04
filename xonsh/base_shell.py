# -*- coding: utf-8 -*-
"""The base class for xonsh shell"""
import io
import os
import sys
import time
import builtins

from xonsh.tools import XonshError, escape_windows_title_string, ON_WINDOWS, \
    print_exception
from xonsh.completer import Completer, KnownCommands
from xonsh.environ import multiline_prompt, format_prompt


class _TeeOut(object):
    """Tees stdout into the original sys.stdout and another buffer."""

    def __init__(self, buf):
        self.buffer = buf
        self.stdout = sys.stdout
        self.encoding = self.stdout.encoding
        sys.stdout = self

    def __del__(self):
        sys.stdout = self.stdout

    def close(self):
        """Restores the original stdout."""
        sys.stdout = self.stdout

    def write(self, data):
        """Writes data to the original stdout and the buffer."""
        self.stdout.write(data)
        self.buffer.write(data)

    def flush(self):
        """Flushes both the original stdout and the buffer."""
        self.stdout.flush()
        self.buffer.flush()

    def fileno(self):
        """Tunnel fileno() calls."""
        _ = self
        return sys.stdout.fileno()


class _TeeErr(object):
    """Tees stderr into the original sys.stdout and another buffer."""

    def __init__(self, buf):
        self.buffer = buf
        self.stderr = sys.stderr
        self.encoding = self.stderr.encoding
        sys.stderr = self

    def __del__(self):
        sys.stderr = self.stderr

    def close(self):
        """Restores the original stderr."""
        sys.stderr = self.stderr

    def write(self, data):
        """Writes data to the original stderr and the buffer."""
        self.stderr.write(data)
        self.buffer.write(data)

    def flush(self):
        """Flushes both the original stderr and the buffer."""
        self.stderr.flush()
        self.buffer.flush()

    def fileno(self):
        """Tunnel fileno() calls."""
        _ = self
        return sys.stderr.fileno()


class Tee(io.StringIO):
    """Class that merges tee'd stdout and stderr into a single buffer.

    This represents what a user would actually see on the command line.
    """
    # pylint is a stupid about counting public methods when using inheritance.
    # pylint: disable=too-few-public-methods

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stdout = _TeeOut(self)
        self.stderr = _TeeErr(self)

    def __del__(self):
        del self.stdout, self.stderr
        super().__del__()

    def close(self):
        """Closes the buffer as well as the stdout and stderr tees."""
        self.stdout.close()
        self.stderr.close()
        super().close()


class BaseShell(object):
    """The xonsh shell."""

    def __init__(self, execer, ctx, **kwargs):
        super().__init__(**kwargs)
        self.execer = execer
        self.ctx = ctx
        self.known_commands = KnownCommands()
        self.completer = Completer(known_commands=self.known_commands)
        self.buffer = []
        self.need_more_lines = False
        self.mlprompt = None

    def emptyline(self):
        """Called when an empty line has been entered."""
        self.need_more_lines = False
        self.default('')

    def precmd(self, line):
        """Called just before execution of line."""
        return line if self.need_more_lines else line.lstrip()

    def default(self, line):
        """Implements code execution."""
        line = line if line.endswith('\n') else line + '\n'
        src, code = self.push(line)
        if code is None:
            return
        hist = builtins.__xonsh_history__  # pylint: disable=no-member
        ts1 = None
        store_stdout = builtins.__xonsh_env__.get('XONSH_STORE_STDOUT')  # pylint: disable=no-member
        tee = Tee() if store_stdout else io.StringIO()
        try:
            ts0 = time.time()
            self.execer.exec(code, mode='single', glbs=self.ctx)  # no locals
            ts1 = time.time()
            if hist.last_cmd_rtn is None:
                hist.last_cmd_rtn = 0  # returncode for success
        except XonshError as e:
            print(e.args[0], file=sys.stderr)
            if hist.last_cmd_rtn is None:
                hist.last_cmd_rtn = 1  # return code for failure
        except Exception:  # pylint: disable=broad-except
            print_exception()
            if hist.last_cmd_rtn is None:
                hist.last_cmd_rtn = 1  # return code for failure
        finally:
            ts1 = ts1 or time.time()
            self._append_history(inp=src, ts=[ts0, ts1], tee_out=tee.getvalue())
            tee.close()
        if builtins.__xonsh_exit__:  # pylint: disable=no-member
            return True

    def push(self, line):
        """Pushes a line onto the buffer and compiles the code in a way that
        enables multiline input.
        """
        code = None
        self.buffer.append(line)
        if self.need_more_lines:
            return None, code
        src = ''.join(self.buffer)
        try:
            code = self.execer.compile(src,
                                       mode='single',
                                       glbs=None,
                                       locs=self.ctx)
            self.reset_buffer()
        except SyntaxError:
            if line == '\n':
                self.reset_buffer()
                print_exception()
                return src, None
            self.need_more_lines = True
        except Exception:  # pylint: disable=broad-except
            self.reset_buffer()
            print_exception()
            return src, None
        return src, code

    def reset_buffer(self):
        """Resets the line buffer."""
        self.buffer.clear()
        self.need_more_lines = False
        self.mlprompt = None

    def settitle(self):
        """Sets terminal title."""
        _ = self
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        term = env.get('TERM', None)
        # Shells running in emacs sets TERM to "dumb" or "eterm-color".
        # Do not set title for these to avoid garbled prompt.
        if term is None or term in ['dumb', 'eterm-color', 'linux']:
            return
        t = env.get('TITLE')
        if t is None:
            return
        t = format_prompt(t)
        if ON_WINDOWS and 'ANSICON' not in env:
            t = escape_windows_title_string(t)
            os.system('title {}'.format(t))
        else:
            sys.stdout.write("\x1b]2;{0}\x07".format(t))

    @property
    def prompt(self):
        """Obtains the current prompt string."""
        if self.need_more_lines:
            if self.mlprompt is None:
                try:
                    self.mlprompt = multiline_prompt()
                except Exception:  # pylint: disable=broad-except
                    print_exception()
                    self.mlprompt = '<multiline prompt error> '
            return self.mlprompt
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        p = env.get('PROMPT')
        try:
            p = format_prompt(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        self.settitle()
        return p

    def _append_history(self, tee_out=None, **info):
        """Append information about the command to the history."""
        _ = self
        hist = builtins.__xonsh_history__  # pylint: disable=no-member
        info['rtn'] = hist.last_cmd_rtn
        tee_out = tee_out or None
        last_out = hist.last_cmd_out or None
        if last_out is None and tee_out is None:
            pass
        elif last_out is None and tee_out is not None:
            info['out'] = tee_out
        elif last_out is not None and tee_out is None:
            info['out'] = last_out
        else:
            info['out'] = tee_out + '\n' + last_out
        hist.append(info)
        hist.last_cmd_rtn = hist.last_cmd_out = None
