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

        if shell_type is not None:
            env['SHELL_TYPE'] = shell_type
        if env['SHELL_TYPE'] == 'prompt_toolkit':
            if not is_prompt_toolkit_available():
                warn('prompt_toolkit is not available, using readline instead.')
                env['SHELL_TYPE'] = 'readline'

        if env['SHELL_TYPE'] == 'prompt_toolkit':
            from xonsh.prompt_toolkit_shell import PromptToolkitShell
            self.shell = PromptToolkitShell(execer=self.execer,
                                            ctx=self.ctx, **kwargs)
        elif env['SHELL_TYPE'] == 'readline':
            from xonsh.readline_shell import ReadlineShell
            self.shell = ReadlineShell(execer=self.execer,
                                       ctx=self.ctx, **kwargs)
        else:
            raise XonshError('{} is not recognized as a shell type'.format(
                env['SHELL_TYPE']))

    def __getattr__(self, attr):
        """Delegates calls to appropriate shell instance."""
        return getattr(self.shell, attr)

    def _init_environ(self, ctx):
        self.execer = Execer()
        env = builtins.__xonsh_env__
        if ctx is not None:
            self.ctx = ctx
        else:
            rc = env.get('XONSHRC', None)
            self.ctx = xonshrc_context(rcfile=rc, execer=self.execer)
        builtins.__xonsh_ctx__ = self.ctx
        self.ctx['__name__'] = '__main__'

        # xonshrc settting takes priority
        self.ctx.setdefault('__xonsh_subproc_check__', False)
