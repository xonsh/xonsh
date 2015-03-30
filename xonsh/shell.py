"""The xonsh shell"""
import os
import sys
import builtins
import traceback
from cmd import Cmd
from warnings import warn
from argparse import Namespace

from xonsh.execer import Execer
from xonsh.completer import Completer
from xonsh.environ import xonshrc_context, multiline_prompt, format_prompt

RL_COMPLETION_SUPPRESS_APPEND = RL_LIB = None
RL_CAN_RESIZE = False


def setup_readline():
    """Sets up the readline module and completion supression, if available."""
    global RL_COMPLETION_SUPPRESS_APPEND, RL_LIB, RL_CAN_RESIZE
    if RL_COMPLETION_SUPPRESS_APPEND is not None:
        return
    try:
        import readline
    except ImportError:
        return
    import ctypes
    import ctypes.util
    readline.set_completer_delims(' \t\n')
    RL_LIB = lib = ctypes.cdll.LoadLibrary(readline.__file__)
    try:
        RL_COMPLETION_SUPPRESS_APPEND = ctypes.c_int.in_dll(lib, 
                                            'rl_completion_suppress_append')
    except ValueError:
        # not all versions of readline have this symbol, ie Macs sometimes
        RL_COMPLETION_SUPPRESS_APPEND = None
    RL_CAN_RESIZE = hasattr(lib, 'rl_reset_screen_size')
    # reads in history
    env = builtins.__xonsh_env__
    hf = env.get('XONSH_HISTORY_FILE', os.path.expanduser('~/.xonsh_history'))
    if os.path.isfile(hf):
        try:
            readline.read_history_file(hf)
        except PermissionError:
            warn('do not have read permissions for ' + hf, RuntimeWarning)
    hs = env.get('XONSH_HISTORY_SIZE', 8128)
    readline.set_history_length(hs)
    # sets up IPython-like history matching with up and down
    readline.parse_and_bind('"\e[B": history-search-forward')
    readline.parse_and_bind('"\e[A": history-search-backward')
    # Setup Shift-Tab to indent
    readline.parse_and_bind('"\e[Z": "{0}"'.format(env.get('INDENT', '')))

    # handle tab completion differences found in libedit readline compatibility
    # as discussed at http://stackoverflow.com/a/7116997
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


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
    try:
        readline.write_history_file(hf)
    except PermissionError:
        warn('do not have write permissions for ' + hf, RuntimeWarning)

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
        self.ctx = ctx if ctx is not None else \
            xonshrc_context(rcfile=env.get('XONSHRC', None), execer=self.execer)
        self.ctx['__name__'] = '__main__'
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

    def precmd(self, line):
        return line if self.need_more_lines else line.lstrip()
        
    def default(self, line):
        """Implements code execution."""
        line = line if line.endswith('\n') else line + '\n'
        code = self.push(line)
        if code is None:
            return
        try:
            self.execer.exec(code, mode='single', glbs=self.ctx)  # no locals
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
        while not builtins.__xonsh_exit__:
            try:
                super(Shell, self).cmdloop(intro=intro)
            except KeyboardInterrupt:
                print()  # Gives a newline
                self.reset_buffer()
                intro = None

    def settitle(self):
        env = builtins.__xonsh_env__
        term = env.get('TERM', None)
        if term is None or term == 'linux':
            return
        if 'TITLE' in env:
            t = env['TITLE']
            if callable(t):
                t = t()
        else:
            return
        t = format_prompt(t)
        sys.stdout.write("\x1b]2;{0}\x07".format(t))

    @property
    def prompt(self):
        """Obtains the current prompt string."""
        global RL_LIB, RL_CAN_RESIZE
        if RL_CAN_RESIZE:
            # This is needed to support some system where line-wrapping doesn't
            # work. This is a bug in upstream Python, or possibly readline.
            RL_LIB.rl_reset_screen_size()
        if self.need_more_lines:
            if self.mlprompt is None:
                self.mlprompt = multiline_prompt()
            return self.mlprompt
        env = builtins.__xonsh_env__
        if 'PROMPT' in env:
            p = env['PROMPT']
            if callable(p):
                p = p()
            p = format_prompt(p)
        else:
            p = "set '$PROMPT = ...' $ "
        self.settitle()
        return p
