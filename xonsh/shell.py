"""The xonsh shell"""
import os
import traceback
from cmd import Cmd
import builtins
from argparse import Namespace
import sys

from xonsh.execer import Execer
from xonsh.completer import Completer
from xonsh.environ import xonshrc_context, multiline_prompt

RL_COMPLETION_SUPPRESS_APPEND = None

def setup_readline():
    """Sets up the readline module and completion supression, if available."""
    global RL_COMPLETION_SUPPRESS_APPEND
    if RL_COMPLETION_SUPPRESS_APPEND is not None:
        return
    try:
        import readline
    except ImportError:
        return
    import ctypes
    import ctypes.util
    readline.set_completer_delims(' \t\n')
    lib = ctypes.cdll.LoadLibrary(readline.__file__)
    try:
        RL_COMPLETION_SUPPRESS_APPEND = ctypes.c_int.in_dll(lib, 
                                            'rl_completion_suppress_append')
    except ValueError:
        # not all versions of readline have this symbol, ie Macs sometimes
        RL_COMPLETION_SUPPRESS_APPEND = None
    # reads in history
    env = builtins.__xonsh_env__
    hf = env.get('XONSH_HISTORY_FILE', os.path.expanduser('~/.xonsh_history'))
    if os.path.isfile(hf):
        readline.read_history_file(hf)
    hs = env.get('XONSH_HISTORY_SIZE', 8128)
    readline.set_history_length(hs)
    # sets up IPython-like history matching with up and down
    readline.parse_and_bind('"\e[B": history-search-forward')
    readline.parse_and_bind('"\e[A": history-search-backward')
    # Setup Shift-Tab to indent
    readline.parse_and_bind('"\e[Z": "{0}"'.format(env.get('INDENT', '')))

def teardown_readline():
    """Tears down up the readline module, if available."""
    try:
        import readline
    except ImportError:
        return
    env = builtins.__xonsh_env__
    hs = env.get('XONSH_HISTORY_SIZE', 8128)
    readline.set_history_length(hs)
    hf = env.get('XONSH_HISTORY_FILE', os.path.expanduser('~/.xonsh_history'))
    readline.write_history_file(hf)

def rl_completion_suppress_append(val=1):
    """Sets the rl_completion_suppress_append varaiable, if possible.
    A value of 1 (default) means to suppress, a value of 0 means to enable.
    """
    if RL_COMPLETION_SUPPRESS_APPEND is None:
        return
    RL_COMPLETION_SUPPRESS_APPEND.value = val

class Shell(Cmd):
    """The xonsh shell."""

    def __init__(self, completekey='tab', stdin=None, stdout=None, ctx=None):
        super(Shell, self).__init__(completekey=completekey, stdin=stdin, 
                                    stdout=stdout)
        self.execer = Execer()
        env = builtins.__xonsh_env__
        self.ctx = ctx or xonshrc_context(rcfile=env.get('XONSHRC', None), 
                                          execer=self.execer)
        self.completer = Completer()
        self.buffer = []
        self.need_more_lines = False
        self.mlprompt = None
        setup_readline()

    def __del__(self):
        teardown_readline()

    def emptyline(self):
        """Called when an empty line has been entered."""
        self.need_more_lines = False
        self.default('')

    def parseline(self, line):
        """Overridden to no-op."""
        return '', line, line

    def default(self, line):
        """Implements code execution."""
        line = line if line.endswith('\n') else line + '\n'
        code = self.push(line)
        if code is None:
            return
        try:
            self.execer.exec(code, mode='single', glbs=None, locs=self.ctx)
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
            code = self.execer.compile(src, mode='single', glbs=None, 
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

    def completedefault(self, text, line, begidx, endidx):
        """Implements tab-completion for text."""
        rl_completion_suppress_append()  # this needs to be called each time
        return self.completer.complete(text, line, begidx, endidx, ctx=self.ctx)

    # tab complete on first index too
    completenames = completedefault

    def cmdloop(self, intro=None):
        try:
            super(Shell, self).cmdloop(intro=intro)
        except KeyboardInterrupt:
            print()  # gimme a newline
            self.reset_buffer()
            self.cmdloop(intro=None)

    def settitle(self):
        env = builtins.__xonsh_env__
        if 'XONSH_TITLE' in env:
            t = env['XONSH_TITLE']
            if callable(t):
                t = t()
        else:
            t = '{0} | xonsh'.format(env['PWD'].replace(env['HOME'], '~'))
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
            if callable(p):
                p = p()
        else:
            p = "set '$PROMPT = ...' $ "
        if env.get('TERM', 'linux') != 'linux':
            self.settitle()
        return p
