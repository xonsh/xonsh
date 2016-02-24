# -*- coding: utf-8 -*-
"""The xonsh shell"""
import random
import builtins
from warnings import warn

from xonsh.execer import Execer
from xonsh.environ import xonshrc_context
from xonsh.tools import XonshError, ON_WINDOWS


def is_readline_available():
    """Checks if readline is available to import."""
    try:
        import readline
        return True
    except Exception:  # pyreadline will sometimes fail in strange ways
        return False


def is_prompt_toolkit_available():
    """Checks if prompt_toolkit is available to import."""
    try:
        import prompt_toolkit
        return True
    except ImportError:
        return False


def prompt_toolkit_version():
    """Gets the prompt toolkit version."""
    import prompt_toolkit
    return getattr(prompt_toolkit, '__version__', '<0.57')


def prompt_toolkit_version_info():
    """Gets the prompt toolkit version info tuple."""
    v = prompt_toolkit_version().strip('<>+-=.')
    return tuple(map(int, v.split('.')))


def best_shell_type():
    """Gets the best shell type that is available"""
    if ON_WINDOWS or is_prompt_toolkit_available():
        shell_type = 'prompt_toolkit'
    else:
        shell_type = 'readline'
    return shell_type


class Shell(object):
    """Main xonsh shell.

    Initializes execution environment and decides if prompt_toolkit or
    readline version of shell should be used.
    """

    def __init__(self, ctx=None, shell_type=None, config=None, rc=None,
                 **kwargs):
        """
        Parameters
        ----------
        ctx : Mapping, optional
            The execution context for the shell (e.g. the globals namespace).
            If none, this is computed by loading the rc files. If not None,
            this no additional context is computed and this is used
            directly.
        shell_type : str, optional
            The shell type to start, such as 'readline', 'prompt_toolkit',
            or 'random'.
        config : str, optional
            Path to configuration file.
        rc : list of str, optional
            Sequence of paths to run control files.
        """
        self._init_environ(ctx, config, rc)
        env = builtins.__xonsh_env__
        # pick a valid shell
        if shell_type is not None:
            env['SHELL_TYPE'] = shell_type
        shell_type = env.get('SHELL_TYPE')
        if shell_type == 'best':
            shell_type = best_shell_type()
        elif shell_type == 'random':
            shell_type = random.choice(('readline', 'prompt_toolkit'))
        if shell_type == 'prompt_toolkit':
            if not is_prompt_toolkit_available():
                warn('prompt_toolkit is not available, using readline instead.')
                shell_type = env['SHELL_TYPE'] = 'readline'
        # actually make the shell
        if shell_type == 'prompt_toolkit':
            vptk = prompt_toolkit_version()
            minor = int(vptk.split('.')[1])
            if minor < 57 or vptk == '<0.57':  # TODO: remove in future
                msg = ('prompt-toolkit version < v0.57 and may not work as '
                       'expected. Please update.')
                warn(msg, RuntimeWarning)
            from xonsh.ptk.shell import PromptToolkitShell
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

    def _init_environ(self, ctx, config, rc):
        self.execer = Execer(config=config)
        env = builtins.__xonsh_env__
        if ctx is None:
            rc = env.get('XONSHRC') if rc is None else rc
            self.ctx = xonshrc_context(rcfiles=rc, execer=self.execer)
        else:
            self.ctx = ctx
        builtins.__xonsh_ctx__ = self.ctx
        self.ctx['__name__'] = '__main__'
