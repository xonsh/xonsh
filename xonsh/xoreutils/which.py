"""Implements the which xoreutil."""
import os
import argparse
import builtins
import functools

from xonsh.xoreutils import _which
import xonsh.platform as xp
import xonsh.proc as xproc


@functools.lru_cache()
def _which_create_parser():
    desc = "Parses arguments to which wrapper"
    parser = argparse.ArgumentParser("which", description=desc)
    parser.add_argument(
        "args", type=str, nargs="+", help="The executables or aliases to search for"
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        dest="all",
        help="Show all matches in globals, xonsh.aliases, $PATH",
    )
    parser.add_argument(
        "-s",
        "--skip-alias",
        action="store_true",
        help="Do not search inxonsh.aliases",
        dest="skip",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="{}".format(_which.__version__),
        help="Display the version of the python which module " "used by xonsh",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        help="Print out how matches were located and show " "near misses on stderr",
    )
    parser.add_argument(
        "-p",
        "--plain",
        action="store_true",
        dest="plain",
        help="Do not display alias expansions or location of "
        "where binaries are found. This is the "
        "default behavior, but the option can be used to "
        "override the --verbose option",
    )
    parser.add_argument("--very-small-rocks", action=AWitchAWitch)
    if xp.ON_WINDOWS:
        parser.add_argument(
            "-e",
            "--exts",
            nargs="*",
            type=str,
            help="Specify a list of extensions to use instead "
            "of the standard list for this system. This can "
            "effectively be used as an optimization to, for "
            'example, avoid stat\'s of "foo.vbs" when '
            'searching for "foo" and you know it is not a '
            'VisualBasic script but ".vbs" is on PATHEXT. '
            "This option is only supported on Windows",
            dest="exts",
        )
    return parser


def print_global_object(arg, stdout):
    """Print the object."""
    obj = builtins.__xonsh__.ctx.get(arg)
    print("global object of {}".format(type(obj)), file=stdout)


def print_path(abs_name, from_where, stdout, verbose=False, captured=False):
    """Print the name and path of the command."""
    if xp.ON_WINDOWS:
        # Use list dir to get correct case for the filename
        # i.e. windows is case insensitive but case preserving
        p, f = os.path.split(abs_name)
        f = next(s.name for s in xp.scandir(p) if s.name.lower() == f.lower())
        abs_name = os.path.join(p, f)
        if builtins.__xonsh__.env.get("FORCE_POSIX_PATHS", False):
            abs_name.replace(os.sep, os.altsep)
    if verbose:
        print("{} ({})".format(abs_name, from_where), file=stdout)
    else:
        end = "" if captured else "\n"
        print(abs_name, end=end, file=stdout)


def print_alias(arg, stdout, verbose=False):
    """Print the alias."""
    if not verbose:
        if not callable(builtins.aliases[arg]):
            print(" ".join(builtins.aliases[arg]), file=stdout)
        else:
            print(arg, file=stdout)
    else:
        print("aliases['{}'] = {}".format(arg, builtins.aliases[arg]), file=stdout)
        if callable(builtins.aliases[arg]):
            builtins.__xonsh__.superhelp(builtins.aliases[arg])


def which(args, stdin=None, stdout=None, stderr=None, spec=None):
    """
    Checks if each arguments is a xonsh aliases, then if it's an executable,
    then finally return an error code equal to the number of misses.
    If '-a' flag is passed, run both to return both `xonsh` match and
    `which` match.
    """
    parser = _which_create_parser()
    if len(args) == 0:
        parser.print_usage(file=stderr)
        return -1

    pargs = parser.parse_args(args)
    verbose = pargs.verbose or pargs.all
    if spec is not None:
        captured = spec.captured in xproc.STDOUT_CAPTURE_KINDS
    else:
        captured = False
    if pargs.plain:
        verbose = False
    if xp.ON_WINDOWS:
        if pargs.exts:
            exts = pargs.exts
        else:
            exts = builtins.__xonsh__.env["PATHEXT"]
    else:
        exts = None
    failures = []
    for arg in pargs.args:
        nmatches = 0
        if pargs.all and arg in builtins.__xonsh__.ctx:
            print_global_object(arg, stdout)
            nmatches += 1
        if arg in builtins.aliases and not pargs.skip:
            print_alias(arg, stdout, verbose)
            nmatches += 1
            if not pargs.all:
                continue
        # which.whichgen gives the nicest 'verbose' output if PATH is taken
        # from os.environ so we temporarily override it with
        # __xosnh_env__['PATH']
        original_os_path = xp.os_environ["PATH"]
        xp.os_environ["PATH"] = builtins.__xonsh__.env.detype()["PATH"]
        matches = _which.whichgen(arg, exts=exts, verbose=verbose)
        for abs_name, from_where in matches:
            print_path(abs_name, from_where, stdout, verbose, captured)
            nmatches += 1
            if not pargs.all:
                break
        xp.os_environ["PATH"] = original_os_path
        if not nmatches:
            failures.append(arg)
    if len(failures) == 0:
        return 0
    else:
        print("{} not in ".format(", ".join(failures)), file=stderr, end="")
        if pargs.all:
            print("globals or ", file=stderr, end="")
        print("$PATH", file=stderr, end="")
        if not pargs.skip:
            print(" or xonsh.builtins.aliases", file=stderr, end="")
        print("", file=stderr, end="\n")
        return len(failures)


class AWitchAWitch(argparse.Action):
    """The Ducstring, the mother of all ducs."""

    SUPPRESS = "==SUPPRESS=="

    def __init__(
        self, option_strings, version=None, dest=SUPPRESS, default=SUPPRESS, **kwargs
    ):
        super().__init__(
            option_strings=option_strings, dest=dest, default=default, nargs=0, **kwargs
        )

    def __call__(self, parser, namespace, values, option_string=None):
        import webbrowser

        webbrowser.open("https://github.com/xonsh/xonsh/commit/f49b400")
        parser.exit()
