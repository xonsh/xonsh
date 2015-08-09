"""The base class for xonsh shell"""
import io
import os
import sys
import time
import builtins
import traceback

from xonsh.execer import Execer
from xonsh.tools import XonshError, escape_windows_title_string
from xonsh.tools import ON_WINDOWS
from xonsh.completer import Completer
from xonsh.environ import multiline_prompt, format_prompt


class Tee(io.StringIO):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stdout = sys.stdout
        sys.stdout = self

    def __del__(self):
        sys.stdout = self.stdout

    def close(self):
        sys.stdout = self.stdout
        super().close()

    def write(self, data):
        self.stdout.write(data)
        super().write(data)

    def flush(self):
        self.stdout.flush()
        super().flush()

class BaseShell(object):
    """The xonsh shell."""

    def __init__(self, execer, ctx, **kwargs):
        super().__init__(**kwargs)
        self.execer = execer
        self.ctx = ctx
        self.completer = Completer()
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
        code = self.push(line)
        if code is None:
            return
        ts1 = None
        tee = Tee()
        try:
            ts0 = time.time()
            self.execer.exec(code, mode='single', glbs=self.ctx)  # no locals
            ts1 = time.time()
        except XonshError as e:
            print(e.args[0], file=sys.stderr)
        except:
            _print_exception()
        finally:
            ts1 = ts1 or time.time()
            hist = builtins.__xonsh_history__
            hist.append({'inp': line, 'ts': [ts0, ts1], 'out': tee.getvalue()})
            tee.close()
        if builtins.__xonsh_exit__:
            return True

    def push(self, line):
        """Pushes a line onto the buffer and compiles the code in a way that
        enables multiline input.
        """
        code = None
        self.buffer.append(line)
        if self.need_more_lines:
            return code
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
                _print_exception()
                return None
            self.need_more_lines = True
        except:
            self.reset_buffer()
            _print_exception()
            return None
        return code

    def reset_buffer(self):
        """Resets the line buffer."""
        self.buffer.clear()
        self.need_more_lines = False
        self.mlprompt = None

    def settitle(self):
        """Sets terminal title."""
        env = builtins.__xonsh_env__
        term = env.get('TERM', None)
        if term is None or term == 'linux':
            return
        if 'TITLE' in env:
            t = env['TITLE']
        else:
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
                except Exception:
                    _print_exception()
                    self.mlprompt = '<multiline prompt error> '
            return self.mlprompt
        env = builtins.__xonsh_env__
        if 'PROMPT' in env:
            p = env['PROMPT']
            try:
                p = format_prompt(p)
            except Exception:
                _print_exception()
        else:
            p = "set '$PROMPT = ...' $ "
        self.settitle()
        return p


def _print_exception():
    """Print exceptions with/without traceback."""
    if 'XONSH_SHOW_TRACEBACK' not in builtins.__xonsh_env__:
        sys.stderr.write('xonsh: For full traceback set: '
                         '$XONSH_SHOW_TRACEBACK=True\n')
    if builtins.__xonsh_env__.get('XONSH_SHOW_TRACEBACK', False):
        traceback.print_exc()
    else:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exception_only = traceback.format_exception_only(exc_type, exc_value)
        sys.stderr.write(''.join(exception_only))


