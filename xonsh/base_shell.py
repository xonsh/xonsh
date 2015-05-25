"""The base class for xonsh shell"""
import os
import sys
import builtins
import traceback

from xonsh.execer import Execer
from xonsh.tools import XonshError, escape_windows_title_string
from xonsh.tools import ON_WINDOWS
from xonsh.completer import Completer
from xonsh.environ import multiline_prompt, format_prompt


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
        try:
            self.execer.exec(code, mode='single', glbs=self.ctx)  # no locals
        except XonshError as e:
            print(e.args[0], file=sys.stderr)
        except:
            traceback.print_exc()
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
                traceback.print_exc()
                return None
            self.need_more_lines = True
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
                self.mlprompt = multiline_prompt()
            return self.mlprompt
        env = builtins.__xonsh_env__
        if 'PROMPT' in env:
            p = env['PROMPT']
            p = format_prompt(p)
        else:
            p = "set '$PROMPT = ...' $ "
        self.settitle()
        return p
