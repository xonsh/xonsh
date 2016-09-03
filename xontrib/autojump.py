#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import builtins
import platform
import subprocess
from xonsh import dirstack
from xonsh.events import events


__all__ = ('_autojump', '_autojump_completer')

_env = builtins.__xonsh_env__


def _get_error_path():
    if platform.system() == "Darwin":
        return os.path.join(_env['HOME'], "Library/autojump/errors.log")
    elif "XDG_DATA_HOME" in _env:
        return os.path.join(_env['XDG_DATA_HOME'], "autojump/errors.log")
    else:
        return os.path.join(_env['HOME'], ".local/share/autojump/errors.log")


_env['AUTOJUMP_ERROR_PATH'] = _get_error_path()
_env['AUTOJUMP_SOURCED'] = 1


def check_output(*args, **kwargs):
    kwargs.update(dict(env=_env.detype(),
                       stderr=subprocess.DEVNULL,
                       universal_newlines=True))
    return subprocess.check_output(*args, **kwargs)


def _autojump(args, stdin=None):
    if len(args) and args[0][0] == '-' and args[0] != '--':
        return subprocess.call(['autojump'] + args, env=_env.detype())
    output = check_output(['autojump'] + args).strip()
    if os.path.isdir(output):
        print(output)
        dirstack.cd([output])
    else:
        print('autojump directory {} not found'.format(' '.join(args)))
        print(output)
        print('Try `autojump --help` for more information.')


builtins.aliases['j'] = _autojump


@events.on_chdir
def _autojump_update(olddir, newdir):
    subprocess.call(['autojump', '--add', os.path.abspath(newdir)],
                    env=_env.detype())


def _autojump_completer(prefix, line, begidx, endidx, ctx):
    '''Completes autojump'''
    if line[:2] != 'j ':
        return None
    output = check_output(['autojump', '--complete', prefix])
    return set(output.strip().split('\n'))


builtins.__xonsh_completers__['autojump'] = _autojump_completer
builtins.__xonsh_completers__.move_to_end('autojump', last=False)
