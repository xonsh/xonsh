"""The xonsh shell"""
import traceback
from cmd import Cmd
import builtins

from xonsh.execer import Execer

class Shell(Cmd):
    """The xonsh shell."""

    def __init__(self, completekey='tab', stdin=None, stdout=None, ctx=None):
        super(Shell, self).__init__(completekey='tab', stdin=stdin, 
                                    stdout=stdout)
        self.execer = Execer()
        self.ctx = ctx or {}

    def parseline(self, line):
        """Overridden to no-op."""
        return '', None, line

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
        x = [s for s in self.ctx if s.startswith(text)]
        x += [s for s in dir(builtins) if s.startswith(text)]
        return x

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

