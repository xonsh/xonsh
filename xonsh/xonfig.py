"""The xonsh configuration (xonfig) utility."""
import os
import json
import  builtins
import functools
from argparse import ArgumentParser

import ply

from xonsh import __version__ as XONSH_VERSION
from xonsh import tools
from xonsh.shell import is_readline_available, is_prompt_toolkit_available
from xonsh.wizard import Wizard, Pass, Message, Save, Load, YesNo


YN = "{GREEN}yes{NO_COLOR} or {RED}no{NO_COLOR} (default)? "
HR = "'`·.,¸,.·*¯`·.,¸,.·*¯`·.,¸,.·*¯`·.,¸,.·*¯`·.,¸,.·*¯`·.,¸,.·*¯`·.,¸,.·*'"
WIZARD_HEAD = """{hr}
          Welcome to the xonsh configuration wizard!
          ------------------------------------------
This will present a guided tour through setting up the xonsh static 
config file. Xonsh will automatically ask you if you want to run this 
wizard if the configuration file does not exist. However, you can
always rerun this wizard with the xonfig command:

    $ xonfig wizard

This wizard will load an existing configuration, if it is available.
Also never fear when this wizard saves its results! It will create
a backup of any existing configuration automatically.

This wizard has two main phases: foreign shell setup and environment
variable setup. Each phase may be skipped in its entirety.

For the configuration to take effect, you will need to restart xonsh.
{hr}""".format(hr=HR)

WIZARD_DO_FS = """{hr}
                      Foreign Shell Setup
                      -------------------
The xonsh shell has the ability to interface with foreign shells such
as Bash, zsh, or fish. 

For configuration, this means that xonsh can load the environment, 
aliases, and functions specified in the config files of these shells. 
Naturally, these shells must be available on the system to work. 
Being able to share configuration (and source) from foreign shells 
makes it easier to transition to and from xonsh.

Would you like to configure any foreign shells, """.format(hr=HR) + YN 

WIZARD_DO_EV = YN

WIZARD_TAIL = """
Thanks for using the xonsh configuration wizard!
""".strip()


def make_wizard(default_file=None, confirm=False):
    """Makes a configuration wizard for xonsh config file.

    Parameters
    ----------
    default_file : str, optional
        Default filename to save and load to. User will still be prompted.
    confirm : bool, optional
        Confirm that the main part of the wizard should be run.
    """
    wiz = Wizard(children=[
            Message(message=WIZARD_HEAD),
            Load(default_file=default_file, check=True),
            YesNo(question=WIZARD_DO_FS, yes=Pass(), no=Pass()),
            YesNo(question=WIZARD_DO_EV, yes=Pass(), no=Pass()),
            Save(default_file=default_file, check=True),
            Message(message=WIZARD_TAIL),
            ])
    if confirm:
        q = ('Would you like to run the xonsh configuration wizard now?\n'
             'yes or no (default)? ')
        wiz = YesNo(question=q, yes=wiz, no=Pass())
    return wiz


def _wizard(ns):
    env = builtins.__xonsh_env__
    fname = env.get('XONSHCONFIG') if ns.file is None else ns.file
    wiz = make_wizard(default_file=fname, confirm=ns.confirm)


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
        ('PLY', ply.__version__),
        ('have readline', is_readline_available()),
        ('have prompt toolkit', is_prompt_toolkit_available()),
        ('on posix', tools.ON_POSIX),
        ('on linux', tools.ON_LINUX),
        ('on arch', tools.ON_ARCH),
        ('on windows', tools.ON_WINDOWS),
        ('on mac', tools.ON_MAC),
        ('are root user', tools.IS_ROOT),
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
    wiz = subp.add_parser('wizard', help=('displays configuration information, '
                                         'default action'))
    wiz.add_argument('--file', default=None, 
                     help='config file location, default=$XONSHCONFIG')
    wiz.add_argument('--confirm', action='store_true', default=False, 
                      help='confirm that the wizard should be run.')
    return p


_MAIN_ACTIONS = {
    'info': _info,
    'wizard': _wizard,
    }

def main(args=None):
    """Main xonfig entry point."""
    if not args or (args[0] not in _MAIN_ACTIONS and 
                    args[0] not in {'-h', '--help'}):
        args.insert(0, 'info')
    parser = _create_parser()
    ns = parser.parse_args(args)
    if ns.action is None:  # apply default action
        ns = parser.parse_args(['info'] + args)
    return _MAIN_ACTIONS[ns.action](ns)


if __name__ == '__main__':
    main()
