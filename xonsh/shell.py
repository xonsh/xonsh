"""The xonsh shell"""
import traceback
from cmd import Cmd
import builtins

from xonsh.execer import Execer
from xonsh.completer import Completer

def setup_readline():
    try:
        import readline
    except ImportError:
        return
    import ctypes
    import ctypes.util
    readline.set_completer_delims(' \t\n')
    lib = ctypes.cdll.LoadLibrary(readline.__file__)
    rawlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library('readline'))
    append_char = ctypes.c_int.in_dll(lib, 'rl_completion_append_character')
    #print(ctypes.addressof(append_char), ctypes.c_int.in_dll(lib, 'rl_completion_append_character'))
    append_char.value = 0

    """
    rappend_char = ctypes.c_int.in_dll(rawlib, 'rl_completion_append_character')
    print(ctypes.addressof(rappend_char), ctypes.c_int.in_dll(rawlib, 'rl_completion_append_character'))
    rappend_char.value = 0

    nappend_char = ctypes.c_int.in_dll(lib, 'rl_completion_append_character')
    print(ctypes.addressof(nappend_char), ctypes.c_int.in_dll(lib, 'rl_completion_append_character'))
    """

    #int_size = ctypes.sizeof(ctypes.c_int)
    #ctypes.memset(ctypes.addressof(append_char), 0, int_size)
    #print(ctypes.addressof(append_char), ctypes.c_int.in_dll(lib, 'rl_completion_append_character'))
    suppress = ctypes.c_int.in_dll(lib, 'rl_completion_suppress_append')
    #ctypes.memset(ctypes.addressof(suppress), 1, int_size)
    #readline.parse_and_bind('tab: delete-char-or-list')

setup_readline()

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
        setup_readline()
        return self.completer.complete(text, line, begidx, endidx, ctx=self.ctx)

    # tab complete on first index too
    completenames = completedefault

    def cmdloop(self, intro=None):
        try:
            super(Shell, self).cmdloop(intro=intro)
        except KeyboardInterrupt:
            print()  # gimme a newline
            self.cmdloop(intro=None)

    #def complete(self, text, state):
    #    rtn = super(Shell, self).complete(text, state)
        #if rtn is not None:
        #    readline.insert_text('\b')
    #    return rtn

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

