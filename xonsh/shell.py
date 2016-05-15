# -*- coding: utf-8 -*-
"""The xonsh shell"""
import builtins
import random
from warnings import warn

from xonsh import xontribs
from xonsh.environ import xonshrc_context
from xonsh.execer import Execer
from xonsh.platform import (BEST_SHELL_TYPE, has_prompt_toolkit, ptk_version,
                            ptk_version_info)
from xonsh.tools import XonshError


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
        self.login = kwargs.get('login', True)
        self.stype = shell_type
        self._init_environ(ctx, config, rc,
                           kwargs.get('scriptcache', True),
                           kwargs.get('cacheall', False))
        env = builtins.__xonsh_env__
        # pick a valid shell
        if shell_type is not None:
            env['SHELL_TYPE'] = shell_type
        shell_type = env.get('SHELL_TYPE')
        if shell_type == 'best':
            shell_type = BEST_SHELL_TYPE
        elif shell_type == 'random':
            shell_type = random.choice(('readline', 'prompt_toolkit'))
        if shell_type == 'prompt_toolkit':
            if not has_prompt_toolkit():
                warn('prompt_toolkit is not available, using readline instead.')
                shell_type = env['SHELL_TYPE'] = 'readline'
        # actually make the shell
        if shell_type == 'none':
            from xonsh.base_shell import BaseShell as shell_class
        elif shell_type == 'prompt_toolkit':
            if ptk_version_info()[:2] < (0, 57) or \
                    ptk_version() == '<0.57':  # TODO: remove in future
                msg = ('prompt-toolkit version < v0.57 and may not work as '
                       'expected. Please update.')
                warn(msg, RuntimeWarning)
            from xonsh.ptk.shell import PromptToolkitShell as shell_class
        elif shell_type == 'readline':
            from xonsh.readline_shell import ReadlineShell as shell_class
        else:
            raise XonshError('{} is not recognized as a shell type'.format(
                             shell_type))
        self.shell = shell_class(execer=self.execer,
                                 ctx=self.ctx, **kwargs)
        # allows history garbace colector to start running
        builtins.__xonsh_history__.gc.wait_for_shell = False

    def __getattr__(self, attr):
        """Delegates calls to appropriate shell instance."""
        return getattr(self.shell, attr)

    def _init_environ(self, ctx, config, rc, scriptcache, cacheall):
        self.ctx = {} if ctx is None else ctx
        self.execer = Execer(config=config, login=self.login, xonsh_ctx=self.ctx)
        self.execer.scriptcache = scriptcache
        self.execer.cacheall = cacheall
        if ctx is None and (self.stype != 'none' or self.login):
            # load xontribs from config file
            names = builtins.__xonsh_config__.get('xontribs', ())
            for name in names:
                xontribs.update_context(name, ctx=self.ctx)
            # load run contol files
            env = builtins.__xonsh_env__
            rc = env.get('XONSHRC') if rc is None else rc
            self.ctx.update(xonshrc_context(rcfiles=rc, execer=self.execer))
        self.ctx['__name__'] = '__main__'
