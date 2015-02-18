"""The xonsh shell"""
import traceback
from cmd import Cmd

from xonsh.execer import Execer

class Shell(Cmd):
    """The xonsh shell."""

    prompt = 'wakka? '

    def __init__(self, completekey='tab', stdin=None, stdout=None, ctx=None):
        super(Shell, self).__init__(completekey='tab', stdin=stdin, 
                                    stdout=stdout)
        self.execer = Execer()
        self.ctx = ctx or {}

    def parseline(self, line):
        """Overridden to no-op."""
        return None, None, line + '\n'

    def default(self, line):
        """Implements parser."""
        try:
            self.execer.exec(line, glbs=None, locs=self.ctx)
        except KeyboardInteruppt:
            raise
        except:
            traceback.print_exc()
