"""The xonsh configuration (xonfig) utility."""
import os
import ast
import json
import textwrap
import  builtins
import functools
from pprint import pformat
from argparse import ArgumentParser

import ply

from xonsh import __version__ as XONSH_VERSION
from xonsh import tools
from xonsh.environ import is_template_string
from xonsh.shell import (is_readline_available, is_prompt_toolkit_available,
    prompt_toolkit_version)
from xonsh.wizard import (Wizard, Pass, Message, Save, Load, YesNo, Input,
    PromptVisitor, While, StoreNonEmpty, create_truefalse_cond, YN)


HR = "'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'`-.,_,.-*'"
WIZARD_HEAD = """
          {{BOLD_WHITE}}Welcome to the xonsh configuration wizard!{{NO_COLOR}}
          {{YELLOW}}------------------------------------------{{NO_COLOR}}
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

{hr}
""".format(hr=HR)

WIZARD_FS = """
{hr}

                      {{BOLD_WHITE}}Foreign Shell Setup{{NO_COLOR}}
                      {{YELLOW}}-------------------{{NO_COLOR}}
The xonsh shell has the ability to interface with foreign shells such
as Bash, zsh, or fish. 

For configuration, this means that xonsh can load the environment, 
aliases, and functions specified in the config files of these shells. 
Naturally, these shells must be available on the system to work. 
Being able to share configuration (and source) from foreign shells 
makes it easier to transition to and from xonsh.
""".format(hr=HR)

WIZARD_ENV = """
{hr}

                  {{BOLD_WHITE}}Environment Variable Setup{{NO_COLOR}}
                  {{YELLOW}}--------------------------{{NO_COLOR}}
The xonsh shell also allows you to setup environment variables from
the static configuration file. Any variables set in this way are
superceded by the definitions in the xonshrc or on the command line.
Still, setting environment variables in this way can help define
options that are global to the system or user.

The following lists the environment variable name, its documentation,
the default value, and the current value. The default and current 
values are presented as pretty repr strings of their Python types.

{{BOLD_GREEN}}Note:{{NO_COLOR}} Simply hitting enter for any environment variable 
will accept the default value for that entry.

Would you like to set env vars now, """.format(hr=HR) + YN

WIZARD_TAIL = """
Thanks for using the xonsh configuration wizard!"""


def make_fs():
    """Makes the foreign shell part of the wizard."""
    cond = create_truefalse_cond(prompt='Add a foreign shell, ' + YN)
    fs = While(cond=cond, body=[
        Input('shell name (e.g. bash): ', path='/foreign_shells/{idx}/shell'),
        StoreNonEmpty('interactive shell [bool, default=True]: ',
                      converter=tools.to_bool,
                      show_conversion=True,
                      path='/foreign_shells/{idx}/interactive'),
        StoreNonEmpty('login shell [bool, default=False]: ',
                      converter=tools.to_bool,
                      show_conversion=True,
                      path='/foreign_shells/{idx}/login'),
        StoreNonEmpty("env command [str, default='env']: ",
                      path='/foreign_shells/{idx}/envcmd'),
        StoreNonEmpty("alias command [str, default='alias']: ",
                      path='/foreign_shells/{idx}/aliascmd'),
        StoreNonEmpty(("extra command line arguments [list of str, "
                       "default=[]]: "),
                      converter=ast.literal_eval,
                      show_conversion=True,
                      path='/foreign_shells/{idx}/extra_args'),
        StoreNonEmpty('current environment [dict, default=None]: ',
                      converter=ast.literal_eval,
                      show_conversion=True,
                      path='/foreign_shells/{idx}/currenv'),
        StoreNonEmpty('safely handle exceptions [bool, default=True]: ',
                      converter=tools.to_bool,
                      show_conversion=True,
                      path='/foreign_shells/{idx}/safe'),
        StoreNonEmpty("pre-command [str, default='']: ",
                      path='/foreign_shells/{idx}/prevcmd'),
        StoreNonEmpty("post-command [str, default='']: ",
                      path='/foreign_shells/{idx}/postcmd'),
        StoreNonEmpty("foreign function command [str, default=None]: ",
                      path='/foreign_shells/{idx}/funcscmd'),
        StoreNonEmpty("source command [str, default=None]: ",
                      path='/foreign_shells/{idx}/sourcer'),
        Message(message='')  # inserts a newline
        ])
    return fs


def _wrap_paragraphs(text, width=70, **kwargs):
    """Wraps paragraphs instead."""
    pars = text.split('\n')
    pars = ['\n'.join(textwrap.wrap(p, width=width, **kwargs)) for p in pars]
    s = '\n'.join(pars)
    return s

ENVVAR_PROMPT = """
{{BOLD_CYAN}}${name}{{NO_COLOR}}
{docstr}
{{RED}}default value:{{NO_COLOR}} {default}
{{RED}}current value:{{NO_COLOR}} {current}
{{BOLD_GREEN}}>>>{{NO_COLOR}} """

def make_envvar(name):
    """Makes a StoreNonEmpty node for an environment variable."""
    env = builtins.__xonsh_env__
    vd = env.get_docs(name)
    if not vd.configurable:
        return
    default = vd.default
    if '\n' in default:
        default = '\n' + _wrap_paragraphs(default, width=69)
    curr = env.get(name)
    if tools.is_string(curr) and is_template_string(curr):
        curr = curr.replace('{', '{{').replace('}', '}}')
    curr = pformat(curr, width=69)
    if '\n' in curr:
        curr = '\n' + curr
    prompt = ENVVAR_PROMPT.format(name=name, default=default, current=curr,
                                docstr=_wrap_paragraphs(vd.docstr, width=69))
    ens = env.get_ensurer(name)
    path = '/env/' + name
    node = StoreNonEmpty(prompt, converter=ens.convert, show_conversion=True,
                         path=path)
    return node
    

def make_env():
    """Makes an environment variable wizard."""
    kids = map(make_envvar, sorted(builtins.__xonsh_env__.docs.keys()))
    kids = [k for k in kids if k is not None]
    wiz = Wizard(children=kids)
    return wiz


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
            Message(message=WIZARD_FS),
            make_fs(),
            YesNo(question=WIZARD_ENV, yes=make_env(), no=Pass()),
            Message(message='\n' + HR + '\n'),
            Save(default_file=default_file, check=True),
            Message(message=WIZARD_TAIL),
            ])
    if confirm:
        q = 'Would you like to run the xonsh configuration wizard now, ' + YN
        wiz = YesNo(question=q, yes=wiz, no=Pass())
    return wiz


def _wizard(ns):
    env = builtins.__xonsh_env__
    fname = env.get('XONSHCONFIG') if ns.file is None else ns.file
    wiz = make_wizard(default_file=fname, confirm=ns.confirm)
    tempenv = {'PROMPT': '', 'XONSH_STORE_STDOUT': False}
    pv = PromptVisitor(wiz, store_in_history=False, multiline=False)
    with env.swap(tempenv):
        try:
            pv.visit()
        except (KeyboardInterrupt, Exception):
            tools.print_exception()


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
        ('prompt toolkit', prompt_toolkit_version() if \
                           is_prompt_toolkit_available() else False),
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
