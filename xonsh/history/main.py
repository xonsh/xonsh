# -*- coding: utf-8 -*-
"""Main entry points of the xonsh history."""
import argparse
import builtins
import datetime
import functools
import json
import os
import sys

from xonsh.history.base import History
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


def construct_history(**kwargs):
    """Construct the history backend object."""
    env = builtins.__xonsh_env__
    backend = env.get('XONSH_HISTORY_BACKEND')
    if isinstance(backend, str) and backend in HISTORY_BACKENDS:
        kls_history = HISTORY_BACKENDS[backend]
    elif xt.is_class(backend):
        kls_history = backend
    elif isinstance(backend, History):
        return backend
    else:
        print('Unknown history backend: {}. Using JSON version'.format(
            backend), file=sys.stderr)
        kls_history = JsonHistory
    return kls_history(**kwargs)


def _xh_session_parser(hist=None, **kwargs):
    """Returns history items of current session."""
    if hist is None:
        hist = builtins.__xonsh_history__
    return hist.items()


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
                yield {'inp': line.rstrip(), 'ts': 0.0, 'ind': ind}
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
                    yield {'inp': command.rstrip(), 'ts': start_time, 'ind': ind}
                else:
                    yield {'inp': line.rstrip(), 'ts': 0.0, 'ind': ind}

    else:
        print("No zsh history file found", file=sys.stderr)


def _xh_filter_ts(commands, start_time, end_time):
    """Yield only the commands between start and end time."""
    for cmd in commands:
        if start_time <= cmd['ts'] < end_time:
            yield cmd


def _xh_get_history(session='session', *, slices=None, datetime_format=None,
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
    cmds = []
    for i, item in enumerate(_XH_HISTORY_SESSIONS[session](location=location)):
        item['ind'] = i
        cmds.append(item)
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
        cmds = _xh_filter_ts(cmds, start_time, end_time)
    return cmds


def _xh_show_history(hist, ns, stdout=None, stderr=None):
    """Show the requested portion of shell history.
    Accepts same parameters with `_xh_get_history`.
    """
    try:
        commands = _xh_get_history(ns.session,
                                   slices=ns.slices,
                                   start_time=ns.start_time,
                                   end_time=ns.end_time,
                                   datetime_format=ns.datetime_format)
    except ValueError as err:
        print("history: error: {}".format(err), file=stderr)
        return
    if ns.reverse:
        commands = reversed(list(commands))
    if ns.numerate and ns.timestamp:
        for c in commands:
            dt = datetime.datetime.fromtimestamp(c['ts'])
            print('{}:({}) {}'.format(c['ind'], xt.format_datetime(dt), c['inp']),
                  file=stdout, end='\n' if not ns.null_byte else '\0')
    elif ns.numerate:
        for c in commands:
            print('{}: {}'.format(c['ind'], c['inp']), file=stdout,
                  end='\n' if not ns.null_byte else '\0')
    elif ns.timestamp:
        for c in commands:
            dt = datetime.datetime.fromtimestamp(c['ts'])
            print('({}) {}'.format(xt.format_datetime(dt), c['inp']),
                  file=stdout, end='\n' if not ns.null_byte else '\0')
    else:
        for c in commands:
            print(c['inp'], file=stdout, end='\n' if not ns.null_byte else '\0')


@xla.lazyobject
def _XH_HISTORY_SESSIONS():
    return {'session': _xh_session_parser,
            'xonsh': _xh_all_parser,
            'all': _xh_all_parser,
            'zsh': _xh_zsh_hist_parser,
            'bash': _xh_bash_hist_parser}


_XH_MAIN_ACTIONS = {'show', 'id', 'file', 'info', 'diff', 'gc'}


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
    show.add_argument('-0', dest='null_byte', default=False,
                      action='store_true',
                      help='separate commands by the null character for piping '
                           'history to external filters')
    show.add_argument('session', nargs='?', choices=_XH_HISTORY_SESSIONS.keys(),
                      default='session',
                      metavar='session',
                      help='{} (default: current session, all is an alias for xonsh)'
                           ''.format(', '.join(map(repr, _XH_HISTORY_SESSIONS.keys()))))
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

    hist = builtins.__xonsh_history__
    if isinstance(hist, JsonHistory):
        # add actions belong only to JsonHistory
        diff = subp.add_parser('diff', help='diff two xonsh history files')
        xdh.dh_create_parser(p=diff)

        import xonsh.replay as xrp
        replay = subp.add_parser('replay', help='replay a xonsh history file')
        xrp.replay_create_parser(p=replay)
        _XH_MAIN_ACTIONS.add('replay')

    return p


def _xh_parse_args(args):
    """Prepare and parse arguments for the history command.

    Add default action for ``history`` and
    default session for ``history show``.
    """
    parser = _xh_create_parser()
    if not args:
        args = ['show', 'session']
    elif args[0] not in _XH_MAIN_ACTIONS and args[0] not in ('-h', '--help'):
        args = ['show', 'session'] + args
    if args[0] == 'show':
        if not any(a in _XH_HISTORY_SESSIONS for a in args):
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
    if not ns or not ns.action:
        return
    if ns.action == 'show':
        _xh_show_history(hist, ns, stdout=stdout, stderr=stderr)
    elif ns.action == 'info':
        data = hist.info()
        if ns.json:
            s = json.dumps(data)
            print(s, file=stdout)
        else:
            lines = ['{0}: {1}'.format(k, v) for k, v in data.items()]
            print('\n'.join(lines), file=stdout)
    elif ns.action == 'id':
        if not hist.sessionid:
            return
        print(str(hist.sessionid), file=stdout)
    elif ns.action == 'file':
        if not hist.filename:
            return
        print(str(hist.filename), file=stdout)
    elif ns.action == 'gc':
        hist.run_gc(size=ns.size, blocking=ns.blocking)
    elif ns.action == 'diff':
        if isinstance(hist, JsonHistory):
            xdh.dh_main_action(ns)
    elif ns.action == 'replay':
        if isinstance(hist, JsonHistory):
            import xonsh.replay as xrp
            xrp.replay_main_action(hist, ns, stdout=stdout, stderr=stderr)
    else:
        print('Unknown history action {}'.format(ns.action), file=sys.stderr)
