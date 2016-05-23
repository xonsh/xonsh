# -*- coding: utf-8 -*-
"""Aliases for the xonsh shell."""

from argparse import ArgumentParser, Action
import builtins
from collections.abc import MutableMapping, Iterable, Sequence
import os
import shlex

from xonsh.dirstack import cd, pushd, popd, dirs, _get_cwd
from xonsh.environ import locate_binary
from xonsh.foreign_shells import foreign_shell_data
from xonsh.jobs import jobs, fg, bg, kill_all_jobs
from xonsh.history import main as history_alias
from xonsh.platform import ON_ANACONDA, ON_DARWIN, ON_WINDOWS
from xonsh.proc import foreground
from xonsh.replay import main as replay_main
from xonsh.timings import timeit_alias
from xonsh.tools import (XonshError, argvquote, escape_windows_cmd_string,
                         to_bool)
from xonsh.vox import Vox
from xonsh.xontribs import main as xontribs_main
from xonsh.xoreutils import _which


class Aliases(MutableMapping):
    """Represents a location to hold and look up aliases."""

    def __init__(self, *args, **kwargs):
        self._raw = {}
        self.update(*args, **kwargs)

    def get(self, key, default=None):
        """Returns the (possibly modified) value. If the key is not present,
        then `default` is returned.
        If the value is callable, it is returned without modification. If it
        is an iterable of strings it will be evaluated recursively to expand
        other aliases, resulting in a new list or a "partially applied"
        callable.
        """
        val = self._raw.get(key)
        if val is None:
            return default
        elif isinstance(val, Iterable) or callable(val):
            return self.eval_alias(val, seen_tokens={key})
        else:
            msg = 'alias of {!r} has an inappropriate type: {!r}'
            raise TypeError(msg.format(key, val))

    def eval_alias(self, value, seen_tokens=frozenset(), acc_args=()):
        """
        "Evaluates" the alias `value`, by recursively looking up the leftmost
        token and "expanding" if it's also an alias.

        A value like ["cmd", "arg"] might transform like this:
        > ["cmd", "arg"] -> ["ls", "-al", "arg"] -> callable()
        where `cmd=ls -al` and `ls` is an alias with its value being a
        callable.  The resulting callable will be "partially applied" with
        ["-al", "arg"].
        """
        # Beware of mutability: default values for keyword args are evaluated
        # only once.
        if callable(value):
            if acc_args:  # Partial application
                def _alias(args, stdin=None):
                    args = list(acc_args) + args
                    return value(args, stdin=stdin)
                return _alias
            else:
                return value
        else:
            expand_path = builtins.__xonsh_expand_path__
            token, *rest = map(expand_path, value)
            if token in seen_tokens or token not in self._raw:
                # ^ Making sure things like `egrep=egrep --color=auto` works,
                # and that `l` evals to `ls --color=auto -CF` if `l=ls -CF`
                # and `ls=ls --color=auto`
                rtn = [token]
                rtn.extend(rest)
                rtn.extend(acc_args)
                return rtn
            else:
                seen_tokens = seen_tokens | {token}
                acc_args = rest + list(acc_args)
                return self.eval_alias(self._raw[token], seen_tokens, acc_args)

    def expand_alias(self, line):
        """Expands any aliases present in line if alias does not point to a
        builtin function and if alias is only a single command.
        """
        word = line.split(' ', 1)[0]
        if word in builtins.aliases and isinstance(self.get(word), Sequence):
            word_idx = line.find(word)
            expansion = ' '.join(self.get(word))
            line = line[:word_idx] + expansion + line[word_idx+len(word):]
        return line

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self._raw[key]

    def __setitem__(self, key, val):
        if isinstance(val, str):
            self._raw[key] = shlex.split(val)
        else:
            self._raw[key] = val

    def __delitem__(self, key):
        del self._raw[key]

    def update(self, *args, **kwargs):
        for key, val in dict(*args, **kwargs).items():
            self[key] = val

    def __iter__(self):
        yield from self._raw

    def __len__(self):
        return len(self._raw)

    def __str__(self):
        return str(self._raw)

    def __repr__(self):
        return '{0}.{1}({2})'.format(self.__class__.__module__,
                                     self.__class__.__name__, self._raw)

    def _repr_pretty_(self, p, cycle):
        name = '{0}.{1}'.format(self.__class__.__module__,
                                self.__class__.__name__)
        with p.group(0, name + '(', ')'):
            if cycle:
                p.text('...')
            elif len(self):
                p.break_()
                p.pretty(dict(self))



def exit(args, stdin=None):  # pylint:disable=redefined-builtin,W0622
    """Sends signal to exit shell."""
    builtins.__xonsh_exit__ = True
    kill_all_jobs()
    print()  # gimme a newline
    return None, None


_SOURCE_FOREIGN_PARSER = None


def _ensure_source_foreign_parser():
    global _SOURCE_FOREIGN_PARSER
    if _SOURCE_FOREIGN_PARSER is not None:
        return _SOURCE_FOREIGN_PARSER
    desc = "Sources a file written in a foreign shell language."
    parser = ArgumentParser('source-foreign', description=desc)
    parser.add_argument('shell', help='Name or path to the foreign shell')
    parser.add_argument('files_or_code', nargs='+',
                        help='file paths to source or code in the target '
                             'language.')
    parser.add_argument('-i', '--interactive', type=to_bool, default=True,
                        help='whether the sourced shell should be interactive',
                        dest='interactive')
    parser.add_argument('-l', '--login', type=to_bool, default=False,
                        help='whether the sourced shell should be login',
                        dest='login')
    parser.add_argument('--envcmd', default=None, dest='envcmd',
                        help='command to print environment')
    parser.add_argument('--aliascmd', default=None, dest='aliascmd',
                        help='command to print aliases')
    parser.add_argument('--extra-args', default=(), dest='extra_args',
                        type=(lambda s: tuple(s.split())),
                        help='extra arguments needed to run the shell')
    parser.add_argument('-s', '--safe', type=to_bool, default=True,
                        help='whether the source shell should be run safely, '
                             'and not raise any errors, even if they occur.',
                        dest='safe')
    parser.add_argument('-p', '--prevcmd', default=None, dest='prevcmd',
                        help='command(s) to run before any other commands, '
                             'replaces traditional source.')
    parser.add_argument('--postcmd', default='', dest='postcmd',
                        help='command(s) to run after all other commands')
    parser.add_argument('--funcscmd', default=None, dest='funcscmd',
                        help='code to find locations of all native functions '
                             'in the shell language.')
    parser.add_argument('--sourcer', default=None, dest='sourcer',
                        help='the source command in the target shell '
                        'language, default: source.')
    parser.add_argument('--use-tmpfile', type=to_bool, default=False,
                        help='whether the commands for source shell should be '
                             'written to a temporary file.',
                        dest='use_tmpfile')
    parser.add_argument('--seterrprevcmd', default=None, dest='seterrprevcmd',
                        help='command(s) to set exit-on-error before any'
                             'other commands.')
    parser.add_argument('--seterrpostcmd', default=None, dest='seterrpostcmd',
                        help='command(s) to set exit-on-error after all'
                             'other commands.')
    _SOURCE_FOREIGN_PARSER = parser
    return parser


def source_foreign(args, stdin=None):
    """Sources a file written in a foreign shell language."""
    parser = _ensure_source_foreign_parser()
    ns = parser.parse_args(args)
    if ns.prevcmd is not None:
        pass  # don't change prevcmd if given explicitly
    elif os.path.isfile(ns.files_or_code[0]):
        # we have filename to source
        ns.prevcmd = '{} "{}"'.format(ns.sourcer, '" "'.join(ns.files_or_code))
    elif ns.prevcmd is None:
        ns.prevcmd = ' '.join(ns.files_or_code)  # code to run, no files
    foreign_shell_data.cache_clear()  # make sure that we don't get prev src
    fsenv, fsaliases = foreign_shell_data(shell=ns.shell, login=ns.login,
                                          interactive=ns.interactive,
                                          envcmd=ns.envcmd,
                                          aliascmd=ns.aliascmd,
                                          extra_args=ns.extra_args,
                                          safe=ns.safe, prevcmd=ns.prevcmd,
                                          postcmd=ns.postcmd,
                                          funcscmd=ns.funcscmd,
                                          sourcer=ns.sourcer,
                                          use_tmpfile=ns.use_tmpfile,
                                          seterrprevcmd=ns.seterrprevcmd,
                                          seterrpostcmd=ns.seterrpostcmd)
    if fsenv is None:
        return (None, 'xonsh: error: Source failed: '
                      '{}\n'.format(ns.prevcmd), 1)
    # apply results
    env = builtins.__xonsh_env__
    denv = env.detype()
    for k, v in fsenv.items():
        if k in denv and v == denv[k]:
            continue  # no change from original
        env[k] = v
    # Remove any env-vars that were unset by the script.
    for k in denv:
        if k not in fsenv:
            env.pop(k, None)
    # Update aliases
    baliases = builtins.aliases
    for k, v in fsaliases.items():
        if k in baliases and v == baliases[k]:
            continue  # no change from original
        baliases[k] = v


def source_alias(args, stdin=None):
    """Executes the contents of the provided files in the current context.
    If sourced file isn't found in cwd, search for file along $PATH to source
    instead"""
    for fname in args:
        if not os.path.isfile(fname):
            fname = locate_binary(fname)
        with open(fname, 'r') as fp:
            builtins.execx(fp.read(), 'exec', builtins.__xonsh_ctx__)


def source_cmd(args, stdin=None):
    """Simple cmd.exe-specific wrapper around source-foreign."""
    args = list(args)
    fpath = locate_binary(args[0])
    args[0] = fpath if fpath else args[0]
    if not os.path.isfile(args[0]):
        return (None, 'xonsh: error: File not found: {}\n'.format(args[0]), 1)
    prevcmd = 'call '
    prevcmd += ' '.join([argvquote(arg, force=True) for arg in args])
    prevcmd = escape_windows_cmd_string(prevcmd)
    args.append('--prevcmd={}'.format(prevcmd))
    args.insert(0, 'cmd')
    args.append('--interactive=0')
    args.append('--sourcer=call')
    args.append('--envcmd=set')
    args.append('--seterrpostcmd=if errorlevel 1 exit 1')
    args.append('--use-tmpfile=1')
    return source_foreign(args, stdin=stdin)


def xexec(args, stdin=None):
    """Replaces current process with command specified and passes in the
    current xonsh environment.
    """
    env = builtins.__xonsh_env__
    denv = env.detype()
    if len(args) > 0:
        try:
            os.execvpe(args[0], args, denv)
        except FileNotFoundError as e:
            return (None, 'xonsh: exec: file not found: {}: {}'
                          '\n'.format(e.args[1], args[0]), 1)
    else:
        return (None, 'xonsh: exec: no args specified\n', 1)


_BANG_N_PARSER = None


def bang_n(args, stdin=None):
    """Re-runs the nth command as specified in the argument."""
    global _BANG_N_PARSER
    if _BANG_N_PARSER is None:
        parser = _BANG_N_PARSER = ArgumentParser('!n', usage='!n <n>',
                    description="Re-runs the nth command as specified in the argument.")
        parser.add_argument('n', type=int, help='the command to rerun, may be negative')
    else:
        parser = _BANG_N_PARSER
    ns = parser.parse_args(args)
    hist = builtins.__xonsh_history__
    nhist = len(hist)
    n = nhist + ns.n if ns.n < 0 else ns.n
    if n < 0 or n >= nhist:
        raise IndexError('n out of range, {0} for history len {1}'.format(ns.n, nhist))
    cmd = hist.inps[n]
    if cmd.startswith('!'):
        raise XonshError('xonsh: error: recursive call to !n')
    builtins.execx(cmd)


def bang_bang(args, stdin=None):
    """Re-runs the last command. Just a wrapper around bang_n."""
    return bang_n(['-1'])


class AWitchAWitch(Action):
    SUPPRESS = '==SUPPRESS=='
    def __init__(self, option_strings, version=None, dest=SUPPRESS,
                 default=SUPPRESS, **kwargs):
        super().__init__(option_strings=option_strings, dest=dest,
                         default=default, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        import webbrowser
        webbrowser.open('https://github.com/scopatz/xonsh/commit/f49b400')
        parser.exit()


def which(args, stdin=None, stdout=None, stderr=None):
    """
    Checks if each arguments is a xonsh aliases, then if it's an executable,
    then finally return an error code equal to the number of misses.
    If '-a' flag is passed, run both to return both `xonsh` match and
    `which` match.
    """
    desc = "Parses arguments to which wrapper"
    parser = ArgumentParser('which', description=desc)
    parser.add_argument('args', type=str, nargs='+',
                        help='The executables or aliases to search for')
    parser.add_argument('-a', action='store_true', dest='all',
                        help='Show all matches in $PATH and xonsh.aliases')
    parser.add_argument('-s', '--skip-alias', action='store_true',
                        help='Do not search in xonsh.aliases', dest='skip')
    parser.add_argument('-V', '--version', action='version',
                        version='{}'.format(_which.__version__),
                        help='Display the version of the python which module '
                        'used by xonsh')
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                        help='Print out how matches were located and show '
                        'near misses on stderr')
    parser.add_argument('-p', '--plain', action='store_true', dest='plain',
                        help='Do not display alias expansions or location of '
                             'where binaries are found. This is the '
                             'default behavior, but the option can be used to '
                             'override the --verbose option')
    parser.add_argument('--very-small-rocks', action=AWitchAWitch)
    if ON_WINDOWS:
        parser.add_argument('-e', '--exts', nargs='*', type=str,
                            help='Specify a list of extensions to use instead '
                            'of the standard list for this system. This can '
                            'effectively be used as an optimization to, for '
                            'example, avoid stat\'s of "foo.vbs" when '
                            'searching for "foo" and you know it is not a '
                            'VisualBasic script but ".vbs" is on PATHEXT. '
                            'This option is only supported on Windows',
                            dest='exts')
    if len(args) == 0:
        parser.print_usage(file=stderr)
        return -1
    pargs = parser.parse_args(args)

    if pargs.all:
        pargs.verbose = True

    if ON_WINDOWS:
        if pargs.exts:
            exts = pargs.exts
        else:
            exts = builtins.__xonsh_env__.get('PATHEXT', ['.COM', '.EXE', '.BAT'])
    else:
        exts = None

    failures = []
    for arg in pargs.args:
        nmatches = 0
        # skip alias check if user asks to skip
        if (arg in builtins.aliases and not pargs.skip):
            if pargs.plain or not pargs.verbose:
                if isinstance(builtins.aliases[arg], list):
                    print(' '.join(builtins.aliases[arg]), file=stdout)
                else:
                    print(arg, file=stdout)
            else:
                print("aliases['{}'] = {}".format(arg, builtins.aliases[arg]), file=stdout)
            nmatches += 1
            if not pargs.all:
                continue
        matches = _which.whichgen(arg, exts=exts, verbose=pargs.verbose,
                                  path=builtins.__xonsh_env__['PATH'])
        for abs_name, from_where in matches:
            if ON_WINDOWS:
                # Use list dir to get correct case for the filename
                # i.e. windows is case insesitive but case preserving
                p, f = os.path.split(abs_name)
                f = next(s for s in os.listdir(p) if s.lower() == f.lower())
                abs_name = os.path.join(p, f)
                if builtins.__xonsh_env__.get('FORCE_POSIX_PATHS', False):
                    abs_name.replace(os.sep, os.altsep)
            if pargs.plain or not pargs.verbose:
                print(abs_name, file=stdout)
            else:
                if 'given path element' in from_where:
                    from_where = from_where.replace('given path', '$PATH')
                print('{} ({})'.format(abs_name, from_where), file=stdout)
            nmatches += 1
            if not pargs.all:
                break
        if not nmatches:
            failures.append(arg)
    if len(failures) == 0:
        return 0
    else:
        print('{} not in $PATH'.format(', '.join(failures)), file=stderr, end='')
        if not pargs.skip:
            print(' or xonsh.builtins.aliases', file=stderr, end='')
        print('', end='\n')
        return len(failures)


def xonfig(args, stdin=None):
    """Runs the xonsh configuration utility."""
    from xonsh.xonfig import main  # lazy import
    return main(args)


@foreground
def trace(args, stdin=None):
    """Runs the xonsh tracer utility."""
    from xonsh.tracer import main  # lazy import
    return main(args)


def vox(args, stdin=None):
    """Runs Vox environment manager."""
    vox = Vox()
    return vox(args, stdin=stdin)


def make_default_aliases():
    """Creates a new default aliases dictionary."""
    default_aliases = {
        'cd': cd,
        'pushd': pushd,
        'popd': popd,
        'dirs': dirs,
        'jobs': jobs,
        'fg': fg,
        'bg': bg,
        'EOF': exit,
        'exit': exit,
        'quit': exit,
        'xexec': xexec,
        'source': source_alias,
        'source-zsh': ['source-foreign', 'zsh', '--sourcer=source'],
        'source-bash':  ['source-foreign', 'bash', '--sourcer=source'],
        'source-cmd': source_cmd,
        'source-foreign': source_foreign,
        'history': history_alias,
        'replay': replay_main,
        '!!': bang_bang,
        '!n': bang_n,
        'trace': trace,
        'timeit': timeit_alias,
        'xonfig': xonfig,
        'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
        'ipynb': ['jupyter', 'notebook', '--no-browser'],
        'vox': vox,
        'which': which,
        'xontrib': xontribs_main,
    }
    if ON_WINDOWS:
        # Borrow builtin commands from cmd.exe.
        windows_cmd_aliases = {
            'cls',
            'copy',
            'del',
            'dir',
            'erase',
            'md',
            'mkdir',
            'mklink',
            'move',
            'rd',
            'ren',
            'rename',
            'rmdir',
            'time',
            'type',
            'vol'
        }
        for alias in windows_cmd_aliases:
            default_aliases[alias] = ['cmd', '/c', alias]
        default_aliases['call'] = ['source-cmd']
        default_aliases['source-bat'] = ['source-cmd']
        # Add aliases specific to the Anaconda python distribution.
        if ON_ANACONDA:
            def source_cmd_keep_prompt(args, stdin=None):
                p = builtins.__xonsh_env__.get('PROMPT')
                source_cmd(args, stdin=stdin)
                builtins.__xonsh_env__['PROMPT'] = p
            default_aliases['source-cmd-keep-promt'] = source_cmd_keep_prompt
            default_aliases['activate'] = ['source-cmd-keep-promt',
                                           'activate.bat']
            default_aliases['deactivate'] = ['source-cmd-keep-promt',
                                             'deactivate.bat']
        if not locate_binary('sudo'):
            import xonsh.winutils as winutils

            def sudo(args, sdin=None):
                if len(args) < 1:
                    print('You need to provide an executable to run as '
                          'Administrator.')
                    return
                cmd = args[0]
                if locate_binary(cmd):
                    return winutils.sudo(cmd, args[1:])
                elif cmd.lower() in windows_cmd_aliases:
                    args = ['/D', '/C', 'CD', _get_cwd(), '&&'] + args
                    return winutils.sudo('cmd', args)
                else:
                    msg = 'Cannot find the path for executable "{0}".'
                    print(msg.format(cmd))

            default_aliases['sudo'] = sudo
    elif ON_DARWIN:
        default_aliases['ls'] = ['ls', '-G']
    else:
        default_aliases['grep'] = ['grep', '--color=auto']
        default_aliases['ls'] = ['ls', '--color=auto', '-v']
    return default_aliases
