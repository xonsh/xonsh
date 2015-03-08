"""The xonsh shell"""
import os
import traceback
from cmd import Cmd
import builtins
from argparse import Namespace

from xonsh.execer import Execer
from xonsh.completer import Completer
from xonsh.environ import xonshrc_context, multiline_prompt

RL_POINT = Namespace(value=0)  # mirrors ctypes
RL_COMPLETION_SUPPRESS_APPEND = None

def setup_readline():
    """Sets up the readline module and completion supression, if available."""
    global RL_COMPLETION_SUPPRESS_APPEND, RL_ERASE_EMPTY_LINE, RL_POINT
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
    RL_POINT = ctypes.c_int.in_dll(lib, 'rl_point')
    RL_COMPLETION_SUPPRESS_APPEND = ctypes.c_int.in_dll(lib, 
                                            'rl_completion_suppress_append')
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
        super(Shell, self).__init__(completekey='tab', stdin=stdin, 
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

    def parseline(self, line):
        """Overridden to no-op."""
        return '', line, line

    def default(self, line):
        """Implements code execution."""
        line = line if line.endswith('\n') else line + '\n'
        code = self.push(line)
        if self.need_more_lines:
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
        buf = self.buffer
        buf.append(line)
        col = RL_POINT.value  # current location in line
        code = None
        self.need_more_lines = True
        if len(buf) > 1:
            # col (RL_POINT.value) == 0 is a terrifying way to detect that 
            # a newline has been pressed, but there doesn't seem to be a 
            # way around it.
            if col == 0:
                # this has to be here a newline press does clear the readline
                # buffer.  Thanks GNU, thanks Python.
                buf.pop()
            else:
                return code
        src = ''.join(buf)
        try:
            code = self.execer.compile(src, mode='single', glbs=None, 
                                       locs=self.ctx)
            self.reset_buffer()
        except SyntaxError:
            pass
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
        return p

