# -*- coding: utf-8 -*-
"""The xonsh shell"""
import os
import sys
import random
import time
import difflib
import builtins
import warnings

from xonsh.xontribs import update_context, prompt_xontrib_install
from xonsh.environ import xonshrc_context
from xonsh.execer import Execer
from xonsh.platform import (best_shell_type, has_prompt_toolkit,
                            ptk_version_is_supported)
from xonsh.tools import XonshError, to_bool_or_int, print_exception
from xonsh.events import events
import xonsh.history.main as xhm


events.doc('on_precommand', """
on_precommand(cmd: str) -> str

Fires just before a command is executed.
""")

events.doc('on_postcommand', """
on_postcommand(cmd: str, rtn: int, out: str or None, ts: list) -> None

Fires just after a command is executed.
""")


def fire_precommand(src, show_diff=True):
    """Returns the results of firing the precommand handles."""
    i = 0
    limit = sys.getrecursionlimit()
    lst = ''
    raw = src
    while src != lst:
        lst = src
        srcs = events.on_precommand.fire(src)
        for s in srcs:
            if s != lst:
                src = s
                break
        i += 1
        if i == limit:
            print_exception('Modifcations to source input took more than '
                            'the recursion limit number of interations to '
                            'converge.')
    debug_level = builtins.__xonsh_env__.get('XONSH_DEBUG')
    if show_diff and debug_level > 1 and src != raw:
        sys.stderr.writelines(difflib.unified_diff(
            raw.splitlines(keepends=True),
            src.splitlines(keepends=True),
            fromfile='before precommand event',
            tofile='after precommand event',
        ))
    return src


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
        # build history backend before creating shell
        builtins.__xonsh_history__ = hist = xhm.construct_history(
            env=env.detype(), ts=[time.time(), None], locked=True)

        # pick a valid shell -- if no shell is specified by the user,
        # shell type is pulled from env
        if shell_type is None:
            shell_type = env.get('SHELL_TYPE')
            if shell_type == 'none':
                # This bricks interactive xonsh
                # Can happen from the use of .xinitrc, .xsession, etc
                shell_type = 'best'
        if shell_type == 'best' or shell_type is None:
            shell_type = best_shell_type()
        elif shell_type == 'random':
            shell_type = random.choice(('readline', 'prompt_toolkit'))
        if shell_type == 'prompt_toolkit':
            if not has_prompt_toolkit():
                warnings.warn('prompt_toolkit is not available, using '
                              'readline instead.')
                shell_type = 'readline'
            elif not ptk_version_is_supported():
                warnings.warn('prompt-toolkit version < v1.0.0 is not '
                              'supported. Please update prompt-toolkit. Using '
                              'readline instead.')
                shell_type = 'readline'
        env['SHELL_TYPE'] = shell_type
        # actually make the shell
        if shell_type == 'none':
            from xonsh.base_shell import BaseShell as shell_class
        elif shell_type == 'prompt_toolkit':
            from xonsh.ptk.shell import PromptToolkitShell as shell_class
        elif shell_type == 'readline':
            from xonsh.readline_shell import ReadlineShell as shell_class
        else:
            raise XonshError('{} is not recognized as a shell type'.format(
                             shell_type))
        self.shell = shell_class(execer=self.execer,
                                 ctx=self.ctx, **kwargs)
        # allows history garbage colector to start running
        if hist.gc is not None:
            hist.gc.wait_for_shell = False

    def __getattr__(self, attr):
        """Delegates calls to appropriate shell instance."""
        return getattr(self.shell, attr)

    def _init_environ(self, ctx, config, rc, scriptcache, cacheall):
        self.ctx = {} if ctx is None else ctx
        debug = to_bool_or_int(os.getenv('XONSH_DEBUG', '0'))
        self.execer = Execer(config=config, login=self.login, xonsh_ctx=self.ctx,
                             debug_level=debug)
        self.execer.scriptcache = scriptcache
        self.execer.cacheall = cacheall
        if self.stype != 'none' or self.login:
            # load xontribs from config file
            names = builtins.__xonsh_config__.get('xontribs', ())
            for name in names:
                update_context(name, ctx=self.ctx)
            if getattr(update_context, 'bad_imports', None):
                prompt_xontrib_install(update_context.bad_imports)
                del update_context.bad_imports
            # load run control files
            env = builtins.__xonsh_env__
            rc = env.get('XONSHRC') if rc is None else rc
            events.on_pre_rc.fire()
            self.ctx.update(xonshrc_context(rcfiles=rc, execer=self.execer, initial=self.ctx))
            events.on_post_rc.fire()
        self.ctx['__name__'] = '__main__'
