"""The xonsh shell"""
import builtins
from warnings import warn

from xonsh.execer import Execer
from xonsh.environ import xonshrc_context
from xonsh.tools import XonshError


def is_prompt_toolkit_available():
    """Checks if prompt_toolkit is available to import."""
    try:
        import prompt_toolkit
        return True
    except ImportError:
        return False


class Shell(object):
    """Main xonsh shell.

    Initializes execution environment and decides if prompt_toolkit or
    readline version of shell should be used.
    """

    def __init__(self, ctx=None, shell_type=None, **kwargs):
        self._init_environ(ctx)
        env = builtins.__xonsh_env__
        # pick a valid shell
        if shell_type is not None:
            env['SHELL_TYPE'] = shell_type
        shell_type = env.get('SHELL_TYPE')
        if shell_type == 'prompt_toolkit':
            if not is_prompt_toolkit_available():
                warn('prompt_toolkit is not available, using readline instead.')
                shell_type = env['SHELL_TYPE'] = 'readline'
        # actually make the shell
        if shell_type == 'prompt_toolkit':
            from xonsh.prompt_toolkit_shell import PromptToolkitShell
            self.shell = PromptToolkitShell(execer=self.execer,
                                            ctx=self.ctx, **kwargs)
        elif shell_type == 'readline':
            from xonsh.readline_shell import ReadlineShell
            self.shell = ReadlineShell(execer=self.execer,
                                       ctx=self.ctx, **kwargs)
        else:
            raise XonshError('{} is not recognized as a shell type'.format(
                             shell_type))
        # allows history garbace colector to start running
        builtins.__xonsh_history__.gc.wait_for_shell = False

    def __getattr__(self, attr):
        """Delegates calls to appropriate shell instance."""
        return getattr(self.shell, attr)

    def _init_environ(self, ctx):
        self.execer = Execer()
        env = builtins.__xonsh_env__
        if ctx is not None:
            self.ctx = ctx
        else:
            rc = env.get('XONSHRC')
            self.ctx = xonshrc_context(rcfiles=rc, execer=self.execer)
        builtins.__xonsh_ctx__ = self.ctx
        self.ctx['__name__'] = '__main__'
