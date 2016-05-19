"""Tools for helping manage xontributions."""
import os
import sys
import json
import builtins
import functools
from warnings import warn, catch_warnings, simplefilter
from argparse import ArgumentParser
from importlib import import_module
from importlib.util import find_spec

from xonsh.tools import print_color


XONTRIBS_JSON = os.path.splitext(__file__)[0] + '.json'

def find_xontrib(name):
    """Finds a xontribution from its name."""
    if name.startswith('.'):
        spec = find_spec(name, package='xontrib')
    else:
        spec = find_spec('.' + name, package='xontrib')
    return spec or find_spec(name)


def xontrib_context(name):
    """Return a context dictionary for a xontrib of a given name."""
    spec = find_xontrib(name)
    if spec is None:
        with catch_warnings():
            simplefilter('default', ImportWarning)
            warn('could not find xontrib module {0!r}'.format(name), ImportWarning)
        return {}
    m = import_module(spec.name)
    ctx = {k: getattr(m, k) for k in dir(m) if not k.startswith('_')}
    return ctx


def update_context(name, ctx=None):
    """Updates a context in place from a xontrib. If ctx is not provided,
    then __xonsh_ctx__ is updated.
    """
    if ctx is None:
        ctx = builtins.__xonsh_ctx__
    modctx = xontrib_context(name)
    return ctx.update(modctx)


@functools.lru_cache()
def xontrib_metadata():
    """Loads and returns the xontribs.json file."""
    with open(XONTRIBS_JSON, 'r') as f:
        md = json.load(f)
    return md


def _load(ns):
    """load xontribs"""
    ctx = builtins.__xonsh_ctx__
    for name in ns.names:
        if ns.verbose:
            print('loading xontrib {0!r}'.format(name))
        update_context(name, ctx=ctx)


def _list(ns):
    """Lists xontribs."""
    meta = xontrib_metadata()
    data = []
    nname = 6  # ensures some buffer space.
    names = None if len(ns.names) == 0 else set(ns.names)
    for md in meta['xontribs']:
        name = md['name']
        if names is not None and md['name'] not in names:
            continue
        nname = max(nname, len(name))
        spec = find_xontrib(name)
        if spec is None:
            installed = loaded = False
        else:
            installed = True
            loaded = spec.name in sys.modules
        d = {'name': name, 'installed': installed, 'loaded': loaded}
        data.append(d)
    if ns.json:
        jdata = {d.pop('name'): d for d in data}
        s = json.dumps(jdata)
        print(s)
    else:
        s = ""
        for d in data:
            name = d['name']
            lname = len(name)
            s += "{PURPLE}" + name + "{NO_COLOR}  " + " "*(nname - lname)
            if d['installed']:
                s += '{GREEN}installed{NO_COLOR}      '
            else:
                s += '{RED}not-installed{NO_COLOR}  '
            if d['loaded']:
                s += '{GREEN}loaded{NO_COLOR}'
            else:
                s += '{RED}not-loaded{NO_COLOR}'
            s += '\n'
        print_color(s[:-1])


@functools.lru_cache()
def _create_parser():
    # parse command line args
    parser = ArgumentParser(prog='xontrib',
                            description='Manages xonsh extensions')
    subp = parser.add_subparsers(title='action', dest='action')
    load = subp.add_parser('load', help='loads xontribs')
    load.add_argument('-v', '--verbose', action='store_true', default=False,
                        dest='verbose')
    load.add_argument('names', nargs='+', default=(),
                      help='names of xontribs')
    lyst = subp.add_parser('list', help=('list xontribs, whether they are '
                                         'installed, and loaded.'))
    lyst.add_argument('--json', action='store_true', default=False,
                      help='reports results as json')
    lyst.add_argument('names', nargs='*', default=(),
                      help='names of xontribs')
    return parser


_MAIN_ACTIONS = {
    'load': _load,
    'list': _list,
    }

def main(args=None, stdin=None):
    """Alias that loads xontribs"""
    if not args or (args[0] not in _MAIN_ACTIONS and
                    args[0] not in {'-h', '--help'}):
        args.insert(0, 'load')
    parser = _create_parser()
    ns = parser.parse_args(args)
    if ns.action is None:  # apply default action
        ns = parser.parse_args(['load'] + args)
    return _MAIN_ACTIONS[ns.action](ns)


if __name__ == '__main__':
    main()