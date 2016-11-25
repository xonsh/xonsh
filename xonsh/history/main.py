# -*- coding: utf-8 -*-
"""Implements the xonsh history object."""
import argparse
import builtins
import datetime
import functools
import os
import sys

from xonsh.history.dummy import DummyHistory
from xonsh.history.json import JsonHistory
from xonsh.history.sqlite import SqliteHistory
import xonsh.diff_history as xdh
import xonsh.lazyasd as xla
import xonsh.tools as xt

HISTORY_BACKENDS = {
    'dummy': DummyHistory,
    'json': JsonHistory,
    'sqlite': SqliteHistory,
}


def construct_history(env, ts, locked, gc=True, filename=None):
    env = builtins.__xonsh_env__
    backend = env.get('XONSH_HISTORY_BACKEND', 'json')
    if backend not in HISTORY_BACKENDS:
        print('Unknown history backend: {}. Using JSON version'.format(
            backend), file=sys.stderr)
        kls_history = JsonHistory
    else:
        kls_history = HISTORY_BACKENDS[backend]
    return kls_history(
        env=env.detype(),
        ts=ts,
        locked=locked,
        gc=gc,
        filename=filename,
    )


def _xh_session_parser(hist=None, **kwargs):
    """Returns history items of current session.
        format: (cmd, start_time, index)
    """
    if hist is None:
        hist = builtins.__xonsh_history__
    return hist.session_items()


def _xh_all_parser(hist=None, **kwargs):
    """Returns all history items."""
    if hist is None:
        hist = builtins.__xonsh_history__
    return hist.all_items()


def _xh_find_histfile_var(file_list, default=None):
    """Return the path of the history file
    from the value of the envvar HISTFILE.
    """
    for f in file_list:
        f = xt.expanduser_abs_path(f)
        if not os.path.isfile(f):
            continue
        with open(f, 'r') as rc_file:
            for line in rc_file:
                if line.startswith('HISTFILE='):
                    hist_file = line.split('=', 1)[1].strip('\'"\n')
                    hist_file = xt.expanduser_abs_path(hist_file)
                    if os.path.isfile(hist_file):
                        return hist_file
    else:
        if default:
            default = xt.expanduser_abs_path(default)
            if os.path.isfile(default):
                return default


def _xh_bash_hist_parser(location=None, **kwargs):
    """Yield commands from bash history file"""
    if location is None:
        location = _xh_find_histfile_var([os.path.join('~', '.bashrc'),
                                         os.path.join('~', '.bash_profile')],
                                         os.path.join('~', '.bash_history'))
    if location:
        with open(location, 'r', errors='backslashreplace') as bash_hist:
            for ind, line in enumerate(bash_hist):
                yield (line.rstrip(), 0.0, ind)
    else:
        print("No bash history file", file=sys.stderr)


def _xh_zsh_hist_parser(location=None, **kwargs):
    """Yield commands from zsh history file"""
    if location is None:
        location = _xh_find_histfile_var([os.path.join('~', '.zshrc'),
                                         os.path.join('~', '.zprofile')],
                                         os.path.join('~', '.zsh_history'))
    if location:
        with open(location, 'r', errors='backslashreplace') as zsh_hist:
            for ind, line in enumerate(zsh_hist):
                if line.startswith(':'):
                    try:
                        start_time, command = line.split(';', 1)
                    except ValueError:
                        # Invalid history entry
                        continue
                    try:
                        start_time = float(start_time.split(':')[1])
                    except ValueError:
                        start_time = 0.0
                    yield (command.rstrip(), start_time, ind)
                else:
                    yield (line.rstrip(), 0.0, ind)

    else:
        print("No zsh history file found", file=sys.stderr)


def _hist_gc(ns, hist, stdout=None, stderr=None):
    """Start and monitor garbage collection of the shell history."""
    gc = hist.do_gc(wait_for_shell=False, size=ns.size)
    if ns.blocking:
        while gc.is_alive():
            continue


def _hist_filter_ts(commands, start_time, end_time):
    """Yield only the commands between start and end time."""
    for cmd in commands:
        if start_time <= cmd[1] < end_time:
            yield cmd


def _hist_get(session='session', *, slices=None, datetime_format=None,
              start_time=None, end_time=None, location=None):
    """Get the requested portion of shell history.

    Parameters
    ----------
    session: {'session', 'all', 'xonsh', 'bash', 'zsh'}
        The history session to get.
    slices : list of slice-like objects, optional
        Get only portions of history.
    start_time, end_time: float, optional
        Filter commands by timestamp.
    location: string, optional
        The history file location (bash or zsh)

    Returns
    -------
    generator
       A filtered list of commands
    """
    cmds = _HIST_SESSIONS[session](location=location)
    if slices:
        # transform/check all slices
        slices = [xt.ensure_slice(s) for s in slices]
        cmds = xt.get_portions(cmds, slices)
    if start_time or end_time:
        if start_time is None:
            start_time = 0.0
        else:
            start_time = xt.ensure_timestamp(start_time, datetime_format)
        if end_time is None:
            end_time = float('inf')
        else:
            end_time = xt.ensure_timestamp(end_time, datetime_format)
        cmds = _hist_filter_ts(cmds, start_time, end_time)
    return cmds


def _hist_show(ns, hist=None, stdout=None, stderr=None):
    """Show the requested portion of shell history.
    Accepts same parameters with `_hist_get`.
    """
    try:
        commands = _hist_get(ns.session,
                             slices=ns.slices,
                             start_time=ns.start_time,
                             end_time=ns.end_time,
                             datetime_format=ns.datetime_format)
    except ValueError as err:
        print("history: error: {}".format(err), file=stderr)
        return
    if ns.reverse:
        commands = reversed(list(commands))
    if not ns.numerate and not ns.timestamp:
        for c, _, _ in commands:
            print(c, file=stdout)
    elif not ns.timestamp:
        for c, _, i in commands:
            print('{}: {}'.format(i, c), file=stdout)
    elif not ns.numerate:
        for c, ts, _ in commands:
            dt = datetime.datetime.fromtimestamp(ts).ctime()
            print('({}) {}'.format(dt, c), file=stdout)
    else:
        for c, ts, i in commands:
            dt = datetime.datetime.fromtimestamp(ts).ctime()
            print('{}:({}) {}'.format(i, dt, c), file=stdout)


def _hist_info(ns, hist, stdout=None, stderr=None):
    """Display information about the shell history."""
    hist.show_info(ns)


@xla.lazyobject
def _HIST_SESSIONS():
    return {'session': _xh_session_parser,
            'xonsh': _xh_all_parser,
            'all': _xh_all_parser,
            'zsh': _xh_zsh_hist_parser,
            'bash': _xh_bash_hist_parser}


@xla.lazyobject
def _HIST_MAIN_ACTIONS():
    return {
        'show': _hist_show,
        'id': lambda ns, hist, stdout, stderr: print(hist.sessionid, file=stdout),
        'file': lambda ns, hist, stdout, stderr: print(hist.filename, file=stdout),
        'info': _hist_info,
        'diff': xdh._dh_main_action,
        'gc': _hist_gc,
    }


@functools.lru_cache()
def _xh_create_parser():
    """Create a parser for the "history" command."""
    p = argparse.ArgumentParser(prog='history',
                                description="try 'history <command> --help' "
                                            'for more info')
    subp = p.add_subparsers(title='commands', dest='action')
    # session action
    show = subp.add_parser('show', prefix_chars='-+',
                           help='display history of a session, default command')
    show.add_argument('-r', dest='reverse', default=False,
                      action='store_true', help='reverses the direction')
    show.add_argument('-n', dest='numerate', default=False,
                      action='store_true', help='numerate each command')
    show.add_argument('-t', dest='timestamp', default=False,
                      action='store_true', help='show command timestamps')
    show.add_argument('-T', dest='end_time', default=None,
                      help='show only commands before timestamp')
    show.add_argument('+T', dest='start_time', default=None,
                      help='show only commands after timestamp')
    show.add_argument('-f', dest='datetime_format', default=None,
                      help='the datetime format to be used for'
                           'filtering and printing')
    show.add_argument('session', nargs='?', choices=_HIST_SESSIONS.keys(),
                      default='session',
                      metavar='session',
                      help='{} (default: current session, all is an alias for xonsh)'
                           ''.format(', '.join(map(repr, _HIST_SESSIONS.keys()))))
    show.add_argument('slices', nargs='*', default=None, metavar='slice',
                      help='integer or slice notation')
    # 'id' subcommand
    subp.add_parser('id', help='display the current session id')
    # 'file' subcommand
    subp.add_parser('file', help='display the current history filename')
    # 'info' subcommand
    info = subp.add_parser('info', help=('display information about the '
                                         'current history'))
    info.add_argument('--json', dest='json', default=False,
                      action='store_true', help='print in JSON format')
    # diff
    diff = subp.add_parser('diff', help='diff two xonsh history files')
    xdh._dh_create_parser(p=diff)
    # replay, dynamically
    from xonsh import replay
    rp = subp.add_parser('replay', help='replay a xonsh history file')
    replay._rp_create_parser(p=rp)
    _HIST_MAIN_ACTIONS['replay'] = replay._rp_main_action
    # gc
    gcp = subp.add_parser(
        'gc', help='launches a new history garbage collector')
    gcp.add_argument('--size', nargs=2, dest='size', default=None,
                     help=('next two arguments represent the history size and '
                           'units; e.g. "--size 8128 commands"'))
    bgcp = gcp.add_mutually_exclusive_group()
    bgcp.add_argument('--blocking', dest='blocking', default=True,
                      action='store_true',
                      help=('ensures that the gc blocks the main thread, '
                            'default True'))
    bgcp.add_argument('--non-blocking', dest='blocking', action='store_false',
                      help='makes the gc non-blocking, and thus return sooner')
    return p


def _xh_parse_args(args):
    """Prepare and parse arguments for the history command.

    Add default action for ``history`` and
    default session for ``history show``.
    """
    parser = _xh_create_parser()
    if not args:
        args = ['show', 'session']
    elif args[0] not in _HIST_MAIN_ACTIONS and args[0] not in ('-h', '--help'):
        args = ['show', 'session'] + args
    if args[0] == 'show':
        if not any(a in _HIST_SESSIONS for a in args):
            args.insert(1, 'session')
        ns, slices = parser.parse_known_args(args)
        if slices:
            if not ns.slices:
                ns.slices = slices
            else:
                ns.slices.extend(slices)
    else:
        ns = parser.parse_args(args)
    return ns


def history_main(args=None, stdin=None, stdout=None, stderr=None):
    """This is the history command entry point."""
    hist = builtins.__xonsh_history__
    ns = _xh_parse_args(args)
    if ns:
        _HIST_MAIN_ACTIONS[ns.action](ns, hist, stdout, stderr)
