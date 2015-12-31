"""The xonsh configuration (xonfig) utility."""
import os
import json
import functools
from argparse import ArgumentParser

from xonsh import __version__ as XONSH_VERSION
from xonsh import tools
from xonsh.shell import is_readline_available, is_prompt_toolkit_available


def _format_human(data):
    wcol1 = wcol2 = 0
    for key, val in data:
        wcol1 = max(wcol1, len(key))
        wcol2 = max(wcol2, len(str(val)))
    hr = '+' + ('-'*(wcol1+2)) + '+' + ('-'*(wcol2+2)) + '+\n'
    row = '| {key!s:<{wcol1}} | {val!s:<{wcol2}} |\n'
    s = hr
    for key, val in data:
        s += row.format(key=key, wcol1=wcol1, val=val, wcol2=wcol2)
    s += hr
    return s


def _format_json(data):
    data = {k.replace(' ', '_'): v for k, v in data}
    s = json.dumps(data, sort_keys=True, indent=1) + '\n'
    return s
    

def _info(ns):
    data = [
        ('xonsh', XONSH_VERSION), 
        ('Python', '.'.join(map(str, tools.VER_FULL))), 
        ('have readline', is_readline_available()),
        ('have prompt toolkit', is_prompt_toolkit_available()),
        ('on posix', tools.ON_POSIX),
        ('on linux', tools.ON_LINUX),
        ('on arch', tools.ON_ARCH),
        ('on windows', tools.ON_WINDOWS),
        ('on mac', tools.ON_MAC),
        ('are root', tools.IS_ROOT),
        ('default encoding', tools.DEFAULT_ENCODING),
        ]
    formatter = _format_json if ns.json else _format_human
    s = formatter(data)
    return s


@functools.lru_cache()
def _create_parser():
    p = ArgumentParser(prog='xonfig', 
                       description='Manages xonsh configuration.')
    subp = p.add_subparsers(title='action', dest='action')
    info = subp.add_parser('info', help=('displays configuration information, '
                                         'default action'))
    info.add_argument('--json', action='store_true', default=False, 
                      help='reports results as json')
    return p

_MAIN_ACTIONS = {
    'info': _info,
    }

def main(args=None):
    """Main xonfig entry point."""
    if not args or (args[0] not in _MAIN_ACTIONS and args[0] not in {'-h', '--help'}):
        args.insert(0, 'info')
    parser = _create_parser()
    ns = parser.parse_args(args)
    if ns.action is None:  # apply default action
        ns = parser.parse_args(['info'] + args)
    return _MAIN_ACTIONS[ns.action](ns)

if __name__ == '__main__':
    main()
