"""The xonsh configuration (xonfig) utility."""
import ast
import json
import shutil
import textwrap
import builtins
import functools
import itertools
from pprint import pformat
from argparse import ArgumentParser
from contextlib import contextmanager

try:
    import ply
except ImportError:
    from xonsh import ply

from xonsh import __version__ as XONSH_VERSION
from xonsh.environ import is_template_string
from xonsh import platform
from xonsh.platform import is_readline_available, ptk_version
from xonsh import tools
from xonsh.wizard import (Wizard, Pass, Message, Save, Load, YesNo, Input,
    PromptVisitor, While, StoreNonEmpty, create_truefalse_cond, YN, Unstorable,
    Question)
from xonsh.xontribs import xontrib_metadata, find_xontrib


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
""".format(hr=HR)

WIZARD_ENV_QUESTION = "Would you like to set env vars now, " + YN

WIZARD_XONTRIB = """
{hr}

                           {{BOLD_WHITE}}Xontribs{{NO_COLOR}}
                           {{YELLOW}}--------{{NO_COLOR}}
No shell is complete without extensions, and xonsh is no exception. Xonsh
extensions are called {{BOLD_GREEN}}xontribs{{NO_COLOR}}, or xonsh contributions.
Xontribs are dynamically loadable, either by importing them directly or by
using the 'xontrib' command. However, you can also configure xonsh to load
xontribs automatically on startup prior to loading the run control files.
This allows the xontrib to be used immediately your xonshrc files.

The following describes all xontribs that have been registered with xonsh.
These come from users, 3rd party developers, or xonsh itself!
""".format(hr=HR)

WIZARD_XONTRIB_QUESTION = "Would you like to enable xontribs now, " + YN


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

ENVVAR_MESSAGE = """
{{BOLD_CYAN}}${name}{{NO_COLOR}}
{docstr}
{{RED}}default value:{{NO_COLOR}} {default}
{{RED}}current value:{{NO_COLOR}} {current}"""

ENVVAR_PROMPT = "{BOLD_GREEN}>>>{NO_COLOR} "

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
    msg = ENVVAR_MESSAGE.format(name=name, default=default, current=curr,
                                docstr=_wrap_paragraphs(vd.docstr, width=69))
    mnode = Message(message=msg)
    ens = env.get_ensurer(name)
    path = '/env/' + name
    pnode = StoreNonEmpty(ENVVAR_PROMPT, converter=ens.convert,
                          show_conversion=True, path=path, retry=True)
    return mnode, pnode


def _make_flat_wiz(kidfunc, *args):
    kids = map(kidfunc, *args)
    flatkids = []
    for k in kids:
        if k is None:
            continue
        flatkids.extend(k)
    wiz = Wizard(children=flatkids)
    return wiz


def make_env():
    """Makes an environment variable wizard."""
    w = _make_flat_wiz(make_envvar, sorted(builtins.__xonsh_env__.docs.keys()))
    return w


XONTRIB_PROMPT = '{BOLD_GREEN}Add this xontrib{NO_COLOR}, ' + YN

def _xontrib_path(visitor=None, node=None, val=None):
    # need this to append only based on user-selected size
    return ('xontribs', len(visitor.state.get('xontribs', ())))


def make_xontrib(xontrib, package):
    """Makes a message and StoreNonEmpty node for a xontrib."""
    name = xontrib.get('name', '<unknown-xontrib-name>')
    msg = '\n{BOLD_CYAN}' + name + '{NO_COLOR}\n'
    if 'url' in xontrib:
        msg += '{RED}url:{NO_COLOR} ' + xontrib['url'] + '\n'
    if 'package' in xontrib:
        msg += '{RED}package:{NO_COLOR} ' + xontrib['package'] + '\n'
    if 'url' in package:
        if 'url' in xontrib and package['url'] != xontrib['url']:
            msg += '{RED}package-url:{NO_COLOR} ' + package['url'] + '\n'
    if 'license' in package:
        msg += '{RED}license:{NO_COLOR} ' + package['license'] + '\n'
    msg += '{PURPLE}installed?{NO_COLOR} '
    msg += ('no' if find_xontrib(name) is None else 'yes') + '\n'
    desc = xontrib.get('description', '')
    if not isinstance(desc, str):
        desc = ''.join(desc)
    msg += _wrap_paragraphs(desc, width=69)
    if msg.endswith('\n'):
        msg = msg[:-1]
    mnode = Message(message=msg)
    convert = lambda x: name if tools.to_bool(x) else Unstorable
    pnode = StoreNonEmpty(XONTRIB_PROMPT, converter=convert,
                          path=_xontrib_path)
    return mnode, pnode


def make_xontribs():
    """Makes a xontrib wizard."""
    md = xontrib_metadata()
    pkgs = [md['packages'].get(d.get('package', None), {}) for d in md['xontribs']]
    w = _make_flat_wiz(make_xontrib, md['xontribs'], pkgs)
    return w


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
            Message(message=WIZARD_ENV),
            YesNo(question=WIZARD_ENV_QUESTION, yes=make_env(), no=Pass()),
            Message(message=WIZARD_XONTRIB),
            YesNo(question=WIZARD_XONTRIB_QUESTION, yes=make_xontribs(), no=Pass()),
            Message(message='\n' + HR + '\n'),
            Save(default_file=default_file, check=True),
            Message(message=WIZARD_TAIL),
            ])
    if confirm:
        q = ("Would you like to run the xonsh configuration wizard now?\n\n"
             "1. Yes\n2. No, but ask me later.\n3. No, and don't ask me again."
             "\n\n1, 2, or 3 [default: 2]? ")
        passer = Pass()
        saver = Save(check=False, ask_filename=False, default_file=default_file)
        wiz = Question(q, {1: wiz, 2: passer, 3: saver},
                       converter=lambda x: int(x) if x != '' else 2)
    return wiz


def _wizard(ns):
    env = builtins.__xonsh_env__
    shell = builtins.__xonsh_shell__.shell
    fname = env.get('XONSHCONFIG') if ns.file is None else ns.file
    wiz = make_wizard(default_file=fname, confirm=ns.confirm)
    tempenv = {'PROMPT': '', 'XONSH_STORE_STDOUT': False}
    pv = PromptVisitor(wiz, store_in_history=False, multiline=False)
    @contextmanager
    def force_hide():
        if env.get('XONSH_STORE_STDOUT') and hasattr(shell, '_force_hide'):
            orig, shell._force_hide = shell._force_hide, False
            yield
            shell._force_hide = orig
        else:
            yield
    with force_hide(), env.swap(tempenv):
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
        ('Python', '{}.{}.{}'.format(*platform.PYTHON_VERSION_INFO)),
        ('PLY', ply.__version__),
        ('have readline', is_readline_available()),
        ('prompt toolkit', ptk_version() or None),
        ('pygments', platform.PYGMENTS_VERSION),
        ('on posix', platform.ON_POSIX),
        ('on linux', platform.ON_LINUX)]
    if platform.ON_LINUX:
        data.append(('distro', platform.LINUX_DISTRO))
    data.extend([
        ('on darwin', platform.ON_DARWIN),
        ('on windows', platform.ON_WINDOWS),
        ('is superuser', tools.IS_SUPERUSER),
        ('default encoding', platform.DEFAULT_ENCODING),
        ])
    formatter = _format_json if ns.json else _format_human
    s = formatter(data)
    return s


def _styles(ns):
    env = builtins.__xonsh_env__
    curr = env.get('XONSH_COLOR_STYLE')
    styles = sorted(tools.color_style_names())
    if ns.json:
        s = json.dumps(styles, sort_keys=True, indent=1)
        print(s)
        return
    lines = []
    for style in styles:
        if style == curr:
            lines.append('* {GREEN}' + style + '{NO_COLOR}')
        else:
            lines.append('  ' + style)
    s = '\n'.join(lines)
    tools.print_color(s)


def _str_colors(cmap, cols):
    color_names = sorted(cmap.keys(), key=(lambda s: (len(s), s)))
    grper = lambda s: min(cols // (len(s) + 1), 8)
    lines = []
    for n, group in itertools.groupby(color_names, key=grper):
        width = cols // n
        line = ''
        for i, name in enumerate(group):
            buf = ' ' * (width - len(name))
            line += '{' + name + '}' + name + '{NO_COLOR}' + buf
            if (i+1)%n == 0:
                lines.append(line)
                line = ''
        if len(line) != 0:
            lines.append(line)
    return '\n'.join(lines)

def _tok_colors(cmap, cols):
    from xonsh.pyghooks import Color
    nc = Color.NO_COLOR
    names_toks = {}
    for t in cmap.keys():
        name = str(t)
        if name.startswith('Token.Color.'):
            _, _, name = name.rpartition('.')
        names_toks[name] = t
    color_names = sorted(names_toks.keys(), key=(lambda s: (len(s), s)))
    grper = lambda s: min(cols // (len(s) + 1), 8)
    toks = []
    for n, group in itertools.groupby(color_names, key=grper):
        width = cols // n
        for i, name in enumerate(group):
            toks.append((names_toks[name], name))
            buf = ' ' * (width - len(name))
            if (i+1)%n == 0:
                buf += '\n'
            toks.append((nc, buf))
        if not toks[-1][1].endswith('\n'):
            toks[-1] = (nc, toks[-1][1] + '\n')
    return toks

def _colors(ns):
    cols, _ = shutil.get_terminal_size()
    if tools.ON_WINDOWS:
        cols -= 1
    cmap = tools.color_style()
    akey = next(iter(cmap))
    if isinstance(akey, str):
        s = _str_colors(cmap, cols)
    else:
        s = _tok_colors(cmap, cols)
    tools.print_color(s)


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
    sty = subp.add_parser('styles', help='prints available xonsh color styles')
    sty.add_argument('--json', action='store_true', default=False,
                     help='reports results as json')
    clrs = subp.add_parser('colors', help=('displays the color palette for '
                                           'the current xonsh color style'))
    return p


_MAIN_ACTIONS = {
    'info': _info,
    'wizard': _wizard,
    'styles': _styles,
    'colors': _colors,
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
