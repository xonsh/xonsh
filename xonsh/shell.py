"""The xonsh shell"""
import traceback
from cmd import Cmd
import builtins

from xonsh.execer import Execer
from xonsh.completer import Completer

RL_COMPLETION_SUPPRESS_APPEND = None

def setup_readline():
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
        setup_readline()

    def parseline(self, line):
        """Overridden to no-op."""
        return '', line, line

    def default(self, line):
        """Implements parser."""
        line = line if line.endswith('\n') else line + '\n'
        try:
            self.execer.exec(line, mode='single', glbs=None, locs=self.ctx)
        except:
            traceback.print_exc()
        if builtins.__xonsh_exit__:
            return True

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
            self.cmdloop(intro=None)

    @property
    def prompt(self):
        """Obtains the current prompt string."""
        env = builtins.__xonsh_env__
        if 'PROMPT' in env:
            p = env['PROMPT']
            if callable(p):
                p = p()
        else:
            p = "set '$PROMPT = ...' $ "
        return p

