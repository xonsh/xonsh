"""The xonsh shell"""
import traceback
from cmd import Cmd
import builtins
from argparse import Namespace

from xonsh.execer import Execer
from xonsh.completer import Completer

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
        self.ctx = ctx or {}
        self.completer = Completer()
        self.buffer = []
        self.need_more_lines = False
        setup_readline()

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
            return ''
        env = builtins.__xonsh_env__
        if 'PROMPT' in env:
            p = env['PROMPT']
            if callable(p):
                p = p()
        else:
            p = "set '$PROMPT = ...' $ "
        return p

