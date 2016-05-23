import builtins
from argparse import ArgumentParser, Action

from xonsh.platform import ON_WINDOWS
from xonsh.xoreutils import _which


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
                        version='{}'.format(_which.__version__))
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose')
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
            print('{} -> {}'.format(arg, builtins.aliases[arg]), file=stdout)
            nmatches += 1
            if not pargs.all:
                continue
        for match in _which.whichgen(arg, path=builtins.__xonsh_env__['PATH'],
                                     exts=exts, verbose=pargs.verbose):
            abs_name, from_where = match if pargs.verbose else (match, '')
            if ON_WINDOWS:
                # Use list dir to get correct case for the filename
                # i.e. windows is case insesitive but case preserving
                p, f = os.path.split(abs_name)
                f = next(s for s in os.listdir(p) if s.lower() == f.lower())
                abs_name = os.path.join(p, f)
                if builtins.__xonsh_env__.get('FORCE_POSIX_PATHS', False):
                    abs_name.replace(os.sep, os.altsep)
            if pargs.verbose:
                print('{} ({})'.format(abs_name, from_where), file=stdout)
            else:
                print(abs_name, file=stdout)
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
