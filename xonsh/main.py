# -*- coding: utf-8 -*-
"""The main xonsh script."""
import os
import sys
import enum
import argparse
import builtins
import contextlib
import signal
import traceback

from xonsh import __version__
from xonsh.timings import setup_timings
from xonsh.lazyasd import lazyobject
from xonsh.shell import Shell
from xonsh.pretty import pretty
from xonsh.execer import Execer
from xonsh.proc import HiddenCommandPipeline
from xonsh.jobs import ignore_sigtstp
from xonsh.tools import setup_win_unicode_console, print_color, to_bool_or_int
from xonsh.platform import HAS_PYGMENTS, ON_WINDOWS
from xonsh.codecache import run_script_with_cache, run_code_with_cache
from xonsh.xonfig import print_welcome_screen
from xonsh.xontribs import xontribs_load
from xonsh.lazyimps import pygments, pyghooks
from xonsh.imphooks import install_import_hooks
from xonsh.events import events
from xonsh.environ import xonshrc_context, make_args_env
from xonsh.built_ins import XonshSession, load_builtins, load_proxies


events.transmogrify("on_post_init", "LoadEvent")
events.doc(
    "on_post_init",
    """
on_post_init() -> None

Fired after all initialization is finished and we're ready to do work.

NOTE: This is fired before the wizard is automatically started.
""",
)

events.transmogrify("on_exit", "LoadEvent")
events.doc(
    "on_exit",
    """
on_exit() -> None

Fired after all commands have been executed, before tear-down occurs.

NOTE: All the caveats of the ``atexit`` module also apply to this event.
""",
)


events.transmogrify("on_pre_cmdloop", "LoadEvent")
events.doc(
    "on_pre_cmdloop",
    """
on_pre_cmdloop() -> None

Fired just before the command loop is started, if it is.
""",
)

events.transmogrify("on_post_cmdloop", "LoadEvent")
events.doc(
    "on_post_cmdloop",
    """
on_post_cmdloop() -> None

Fired just after the command loop finishes, if it is.

NOTE: All the caveats of the ``atexit`` module also apply to this event.
""",
)

events.transmogrify("on_pre_rc", "LoadEvent")
events.doc(
    "on_pre_rc",
    """
on_pre_rc() -> None

Fired just before rc files are loaded, if they are.
""",
)

events.transmogrify("on_post_rc", "LoadEvent")
events.doc(
    "on_post_rc",
    """
on_post_rc() -> None

Fired just after rc files are loaded, if they are.
""",
)


def get_setproctitle():
    """Proxy function for loading process title"""
    try:
        from setproctitle import setproctitle as spt
    except ImportError:
        return
    return spt


def path_argument(s):
    """Return a path only if the path is actually legal

    This is very similar to argparse.FileType, except that it doesn't return
    an open file handle, but rather simply validates the path."""

    s = os.path.abspath(os.path.expanduser(s))
    if not os.path.isfile(s):
        msg = "{0!r} must be a valid path to a file".format(s)
        raise argparse.ArgumentTypeError(msg)
    return s


@lazyobject
def parser():
    p = argparse.ArgumentParser(description="xonsh", add_help=False)
    p.add_argument(
        "-h",
        "--help",
        dest="help",
        action="store_true",
        default=False,
        help="show help and exit",
    )
    p.add_argument(
        "-V",
        "--version",
        dest="version",
        action="store_true",
        default=False,
        help="show version information and exit",
    )
    p.add_argument(
        "-c",
        help="Run a single command and exit",
        dest="command",
        required=False,
        default=None,
    )
    p.add_argument(
        "-i",
        "--interactive",
        help="force running in interactive mode",
        dest="force_interactive",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "-l",
        "--login",
        help="run as a login shell",
        dest="login",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "--config-path",
        help="DEPRECATED: static configuration files may now be used "
        "in the XONSHRC file list, see the --rc option.",
        dest="config_path",
        default=None,
        type=path_argument,
    )
    p.add_argument(
        "--rc",
        help="The xonshrc files to load, these may be either xonsh "
        "files or JSON-based static configuration files.",
        dest="rc",
        nargs="+",
        type=path_argument,
        default=None,
    )
    p.add_argument(
        "--no-rc",
        help="Do not load the .xonshrc files",
        dest="norc",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "--no-script-cache",
        help="Do not cache scripts as they are run",
        dest="scriptcache",
        action="store_false",
        default=True,
    )
    p.add_argument(
        "--cache-everything",
        help="Use a cache, even for interactive commands",
        dest="cacheall",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "-D",
        dest="defines",
        help="define an environment variable, in the form of "
        "-DNAME=VAL. May be used many times.",
        metavar="ITEM",
        action="append",
        default=None,
    )
    p.add_argument(
        "--shell-type",
        help="What kind of shell should be used. "
        "Possible options: readline, prompt_toolkit, random. "
        "Warning! If set this overrides $SHELL_TYPE variable.",
        dest="shell_type",
        choices=tuple(Shell.shell_type_aliases.keys()),
        default=None,
    )
    p.add_argument(
        "--timings",
        help="Prints timing information before the prompt is shown. "
        "This is useful while tracking down performance issues "
        "and investigating startup times.",
        dest="timings",
        action="store_true",
        default=None,
    )
    p.add_argument(
        "file",
        metavar="script-file",
        help="If present, execute the script in script-file" " and exit",
        nargs="?",
        default=None,
    )
    p.add_argument(
        "args",
        metavar="args",
        help="Additional arguments to the script specified " "by script-file",
        nargs=argparse.REMAINDER,
        default=[],
    )
    return p


def _pprint_displayhook(value):
    if value is None:
        return
    builtins._ = None  # Set '_' to None to avoid recursion
    if isinstance(value, HiddenCommandPipeline):
        builtins._ = value
        return
    env = builtins.__xonsh__.env
    if env.get("PRETTY_PRINT_RESULTS"):
        printed_val = pretty(value)
    else:
        printed_val = repr(value)
    if HAS_PYGMENTS and env.get("COLOR_RESULTS"):
        tokens = list(pygments.lex(printed_val, lexer=pyghooks.XonshLexer()))
        print_color(tokens)
    else:
        print(printed_val)  # black & white case
    builtins._ = value


class XonshMode(enum.Enum):
    single_command = 0
    script_from_file = 1
    script_from_stdin = 2
    interactive = 3


def start_services(shell_kwargs, args):
    """Starts up the essential services in the proper order.
    This returns the environment instance as a convenience.
    """
    install_import_hooks()
    # create execer, which loads builtins
    ctx = shell_kwargs.get("ctx", {})
    debug = to_bool_or_int(os.getenv("XONSH_DEBUG", "0"))
    events.on_timingprobe.fire(name="pre_execer_init")
    execer = Execer(
        xonsh_ctx=ctx,
        debug_level=debug,
        scriptcache=shell_kwargs.get("scriptcache", True),
        cacheall=shell_kwargs.get("cacheall", False),
    )
    events.on_timingprobe.fire(name="post_execer_init")
    # load rc files
    login = shell_kwargs.get("login", True)
    env = builtins.__xonsh__.env
    rc = shell_kwargs.get("rc", None)
    rc = env.get("XONSHRC") if rc is None else rc
    if args.mode != XonshMode.interactive and not args.force_interactive:
        #  Don't load xonshrc if not interactive shell
        rc = None
    events.on_pre_rc.fire()
    xonshrc_context(rcfiles=rc, execer=execer, ctx=ctx, env=env, login=login)
    events.on_post_rc.fire()
    # create shell
    builtins.__xonsh__.shell = Shell(execer=execer, **shell_kwargs)
    ctx["__name__"] = "__main__"
    return env


def premain(argv=None):
    """Setup for main xonsh entry point. Returns parsed arguments."""
    if argv is None:
        argv = sys.argv[1:]
    setup_timings()
    setproctitle = get_setproctitle()
    if setproctitle is not None:
        setproctitle(" ".join(["xonsh"] + argv))
    builtins.__xonsh__ = XonshSession()
    args = parser.parse_args(argv)
    if args.help:
        parser.print_help()
        parser.exit()
    if args.version:
        version = "/".join(("xonsh", __version__))
        print(version)
        parser.exit()
    shell_kwargs = {
        "shell_type": args.shell_type,
        "completer": False,
        "login": False,
        "scriptcache": args.scriptcache,
        "cacheall": args.cacheall,
        "ctx": builtins.__xonsh__.ctx,
    }
    if args.login:
        shell_kwargs["login"] = True
    if args.norc:
        shell_kwargs["rc"] = ()
    elif args.rc:
        shell_kwargs["rc"] = args.rc
    setattr(sys, "displayhook", _pprint_displayhook)
    if args.command is not None:
        args.mode = XonshMode.single_command
        shell_kwargs["shell_type"] = "none"
    elif args.file is not None:
        args.mode = XonshMode.script_from_file
        shell_kwargs["shell_type"] = "none"
    elif not sys.stdin.isatty() and not args.force_interactive:
        args.mode = XonshMode.script_from_stdin
        shell_kwargs["shell_type"] = "none"
    else:
        args.mode = XonshMode.interactive
        shell_kwargs["completer"] = True
        shell_kwargs["login"] = True
    env = start_services(shell_kwargs, args)
    env["XONSH_LOGIN"] = shell_kwargs["login"]
    if args.defines is not None:
        env.update([x.split("=", 1) for x in args.defines])
    env["XONSH_INTERACTIVE"] = args.force_interactive or (
        args.mode == XonshMode.interactive
    )
    if ON_WINDOWS:
        setup_win_unicode_console(env.get("WIN_UNICODE_CONSOLE", True))
    return args


def _failback_to_other_shells(args, err):
    # only failback for interactive shell; if we cannot tell, treat it
    # as an interactive one for safe.
    if hasattr(args, "mode") and args.mode != XonshMode.interactive:
        raise err
    foreign_shell = None
    shells_file = "/etc/shells"
    if not os.path.exists(shells_file):
        # right now, it will always break here on Windows
        raise err
    excluded_list = ["xonsh", "screen"]
    with open(shells_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "/" not in line:
                continue
            _, shell = line.rsplit("/", 1)
            if shell in excluded_list:
                continue
            if not os.path.exists(line):
                continue
            foreign_shell = line
            break
    if foreign_shell:
        traceback.print_exc()
        print("Xonsh encountered an issue during launch", file=sys.stderr)
        print("Failback to {}".format(foreign_shell), file=sys.stderr)
        os.execlp(foreign_shell, foreign_shell)
    else:
        raise err


def main(argv=None):
    args = None
    try:
        args = premain(argv)
        return main_xonsh(args)
    except Exception as err:
        _failback_to_other_shells(args, err)


def main_xonsh(args):
    """Main entry point for xonsh cli."""
    if not ON_WINDOWS:

        def func_sig_ttin_ttou(n, f):
            pass

        signal.signal(signal.SIGTTIN, func_sig_ttin_ttou)
        signal.signal(signal.SIGTTOU, func_sig_ttin_ttou)

    events.on_post_init.fire()
    env = builtins.__xonsh__.env
    shell = builtins.__xonsh__.shell
    try:
        if args.mode == XonshMode.interactive:
            # enter the shell
            env["XONSH_INTERACTIVE"] = True
            ignore_sigtstp()
            if env["XONSH_INTERACTIVE"] and not any(
                os.path.isfile(i) for i in env["XONSHRC"]
            ):
                print_welcome_screen()
            events.on_pre_cmdloop.fire()
            try:
                shell.shell.cmdloop()
            finally:
                events.on_post_cmdloop.fire()
        elif args.mode == XonshMode.single_command:
            # run a single command and exit
            run_code_with_cache(args.command.lstrip(), shell.execer, mode="single")
        elif args.mode == XonshMode.script_from_file:
            # run a script contained in a file
            path = os.path.abspath(os.path.expanduser(args.file))
            if os.path.isfile(path):
                sys.argv = [args.file] + args.args
                env.update(make_args_env())  # $ARGS is not sys.argv
                env["XONSH_SOURCE"] = path
                shell.ctx.update({"__file__": args.file, "__name__": "__main__"})
                run_script_with_cache(
                    args.file, shell.execer, glb=shell.ctx, loc=None, mode="exec"
                )
            else:
                print("xonsh: {0}: No such file or directory.".format(args.file))
        elif args.mode == XonshMode.script_from_stdin:
            # run a script given on stdin
            code = sys.stdin.read()
            run_code_with_cache(
                code, shell.execer, glb=shell.ctx, loc=None, mode="exec"
            )
    finally:
        events.on_exit.fire()
    postmain(args)


def postmain(args=None):
    """Teardown for main xonsh entry point, accepts parsed arguments."""
    if ON_WINDOWS:
        setup_win_unicode_console(enable=False)
    if hasattr(builtins.__xonsh__, "shell"):
        del builtins.__xonsh__.shell


@contextlib.contextmanager
def main_context(argv=None):
    """Generator that runs pre- and post-main() functions. This has two iterations.
    The first yields the shell. The second returns None but cleans
    up the shell.
    """
    args = premain(argv)
    yield builtins.__xonsh__.shell
    postmain(args)


def setup(
    ctx=None,
    shell_type="none",
    env=(("RAISE_SUBPROC_ERROR", True),),
    aliases=(),
    xontribs=(),
    threadable_predictors=(),
):
    """Starts up a new xonsh shell. Calling this in function in another
    packages __init__.py will allow xonsh to be fully used in the
    package in headless or headed mode. This function is primarily indended to
    make starting up xonsh for 3rd party packages easier.

    Parameters
    ----------
    ctx : dict-like or None, optional
        The xonsh context to start with. If None, an empty dictionary
        is provided.
    shell_type : str, optional
        The type of shell to start. By default this is 'none', indicating
        we should start in headless mode.
    env : dict-like, optional
        Environment to update the current environment with after the shell
        has been initialized.
    aliases : dict-like, optional
        Aliases to add after the shell has been initialized.
    xontribs : iterable of str, optional
        Xontrib names to load.
    threadable_predictors : dict-like, optional
        Threadable predictors to start up with. These overide the defaults.
    """
    ctx = {} if ctx is None else ctx
    # setup xonsh ctx and execer
    if not hasattr(builtins, "__xonsh__"):
        execer = Execer(xonsh_ctx=ctx)
        builtins.__xonsh__ = XonshSession(ctx=ctx, execer=execer)
        load_builtins(ctx=ctx, execer=execer)
        load_proxies()
        builtins.__xonsh__.shell = Shell(execer, ctx=ctx, shell_type=shell_type)
    builtins.__xonsh__.env.update(env)
    install_import_hooks()
    builtins.aliases.update(aliases)
    if xontribs:
        xontribs_load(xontribs)
    tp = builtins.__xonsh__.commands_cache.threadable_predictors
    tp.update(threadable_predictors)
