"""The main xonsh script."""

import argparse
import builtins
import contextlib
import enum
import os
import signal
import sys
import traceback

import xonsh.procs.pipelines as xpp
from xonsh import __version__
from xonsh.built_ins import XSH
from xonsh.codecache import run_code_with_cache, run_script_with_cache
from xonsh.environ import get_home_xonshrc_path, make_args_env, xonshrc_context
from xonsh.events import events
from xonsh.execer import Execer
from xonsh.imphooks import install_import_hooks
from xonsh.lib.lazyasd import lazyobject
from xonsh.lib.lazyimps import pyghooks, pygments
from xonsh.lib.pretty import pretty
from xonsh.platform import HAS_PYGMENTS, ON_WINDOWS
from xonsh.procs.jobs import ignore_sigtstp
from xonsh.shell import Shell
from xonsh.timings import setup_timings
from xonsh.tools import (
    display_error_message,
    print_color,
    print_exception,
    to_bool_or_int,
    unquote,
)
from xonsh.xonfig import print_welcome_screen
from xonsh.xontribs import auto_load_xontribs_from_entrypoints, xontribs_load

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
on_exit(exit_code : int) -> None

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

events.transmogrify("on_xontribs_loaded", "LoadEvent")
events.doc(
    "on_xontribs_loaded",
    """
on_xontribs_loaded() -> None

Fired after external xontribs with ``entrypoints defined`` are loaded.
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
    """Return a path only if the path is actually legal (file or directory)

    This is very similar to argparse.FileType, except that it doesn't return
    an open file handle, but rather simply validates the path."""

    s = os.path.abspath(os.path.expanduser(s))
    if not os.path.exists(s):
        msg = f"{s!r} must be a valid path to a file or directory"
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
        help="Show help and exit.",
    )
    p.add_argument(
        "-V",
        "--version",
        action="version",
        help="Show version information and exit.",
        version=f"xonsh/{__version__}",
    )
    p.add_argument(
        "-c",
        help="Run a single command and exit.",
        dest="command",
        required=False,
        default=None,
    )
    p.add_argument(
        "-i",
        "--interactive",
        help="Force running in interactive mode.",
        dest="force_interactive",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "-l",
        "--login",
        help="Run as a login shell.",
        dest="login",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "--rc",
        help="The xonshrc files to load, these may be either xonsh "
        "files or directories containing xonsh files",
        dest="rc",
        nargs="+",
        type=path_argument,
        default=None,
    )
    p.add_argument(
        "--no-rc",
        help="Do not load any xonsh RC files. Argument --rc will "
        "be ignored if --no-rc is set.",
        dest="norc",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "--no-env",
        help="Do not inherit parent environment variables.",
        dest="inherit_env",
        action="store_false",
        default=True,
    )
    p.add_argument(
        "--no-script-cache",
        help="Do not cache scripts as they are run.",
        dest="scriptcache",
        action="store_false",
        default=True,
    )
    p.add_argument(
        "--cache-everything",
        help="Use a cache, even for interactive commands.",
        dest="cacheall",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "-D",
        dest="defines",
        help="Define an environment variable, in the form of "
        "-DNAME=VAL. May be used many times.",
        metavar="ITEM",
        action="append",
        default=None,
    )
    p.add_argument(
        "-st",
        "--shell-type",
        help="What kind of shell should be used. "
        "Possible options: "
        + ", ".join(Shell.shell_type_aliases.keys())
        + ". Warning! If set this overrides $SHELL_TYPE variable.",
        metavar="SHELL_TYPE",
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
        help="If present, execute the script in script-file and exit.",
        nargs="?",
        default=None,
    )
    p.add_argument(
        "args",
        metavar="args",
        help="Additional arguments to the script specified by script-file.",
        nargs=argparse.REMAINDER,
        default=[],
    )
    return p


def _pprint_displayhook(value):
    if value is None:
        return
    builtins._ = None  # Set '_' to None to avoid recursion
    if isinstance(value, xpp.HiddenCommandPipeline):
        builtins._ = value
        return
    env = XSH.env
    printed_val = None
    if env.get("PRETTY_PRINT_RESULTS"):
        printed_val = pretty(value)
    if not isinstance(printed_val, str):
        # pretty may fail (i.e for unittest.mock.Mock)
        printed_val = repr(value)
    if HAS_PYGMENTS and env.get("COLOR_RESULTS"):
        tokens = list(pygments.lex(printed_val, lexer=pyghooks.XonshLexer()))
        end = "" if env.get("SHELL_TYPE") == "prompt_toolkit" else "\n"
        print_color(tokens, end=end)
    else:
        print(printed_val)  # black & white case
    builtins._ = value


class XonshMode(enum.Enum):
    single_command = 0
    script_from_file = 1
    script_from_stdin = 2
    interactive = 3


def _get_rc_files(shell_kwargs: dict, args, env):
    if shell_kwargs.get("norc"):
        # if --no-rc was passed, then disable loading RC files and dirs
        return (), ()

    # determine which RC files to load, including whether any RC directories
    # should be scanned for such files
    rc_cli = shell_kwargs.get("rc")
    if rc_cli:
        # if an explicit --rc was passed, then we should load only that RC
        # file, and nothing else (ignore both XONSHRC and XONSHRC_DIR)
        rc = tuple(r for r in rc_cli if os.path.isfile(r))
        rcd = tuple(r for r in rc_cli if os.path.isdir(r))
        return rc, rcd

    # otherwise, get the RC files from XONSHRC, and RC dirs from XONSHRC_DIR
    rc = env.get("XONSHRC")
    rcd = env.get("XONSHRC_DIR")

    if not env.get("XONSH_INTERACTIVE", False):
        """
        Home based ``~/.xonshrc`` file has special meaning and history. The ecosystem around shells treats this kind of files
        as the place where interactive tools can add configs. To avoid unintended and unexpected affection
        of this file to non-interactive behavior we remove this file in non-interactive mode e.g. script with shebang.
        """
        home_xonshrc = get_home_xonshrc_path()
        rc = tuple(c for c in rc if c != home_xonshrc)

    return rc, rcd


def _load_rc_files(shell_kwargs: dict, args, env, execer, ctx):
    events.on_pre_rc.fire()
    # load rc files
    login = shell_kwargs.get("login", True)
    rc, rcd = _get_rc_files(shell_kwargs, args, env)
    XSH.rc_files = xonshrc_context(
        rcfiles=rc, rcdirs=rcd, execer=execer, ctx=ctx, env=env, login=login
    )
    events.on_post_rc.fire()


def _autoload_xontribs(env):
    events.on_timingprobe.fire(name="pre_xontribs_autoload")
    disabled = env.get("XONTRIBS_AUTOLOAD_DISABLED", False)
    if disabled is True:
        return
    blocked_xontribs = disabled or ()
    auto_load_xontribs_from_entrypoints(
        blocked_xontribs, verbose=bool(env.get("XONSH_DEBUG", False))
    )
    events.on_xontribs_loaded.fire()
    events.on_timingprobe.fire(name="post_xontribs_autoload")


def start_services(shell_kwargs, args, pre_env=None):
    """Starts up the essential services in the proper order.
    This returns the environment instance as a convenience.
    """
    if pre_env is None:
        pre_env = {}
    # create execer, which loads builtins
    ctx = shell_kwargs.get("ctx", {})
    debug = to_bool_or_int(os.getenv("XONSH_DEBUG", "0"))
    events.on_timingprobe.fire(name="pre_execer_init")
    execer = Execer(
        filename="<stdin>",
        debug_level=debug,
        scriptcache=shell_kwargs.get("scriptcache", True),
        cacheall=shell_kwargs.get("cacheall", False),
    )
    events.on_timingprobe.fire(name="post_execer_init")
    events.on_timingprobe.fire(name="pre_xonsh_session_load")
    XSH.load(ctx=ctx, execer=execer, inherit_env=shell_kwargs.get("inherit_env", True))
    events.on_timingprobe.fire(name="post_xonsh_session_load")

    install_import_hooks(execer)

    env = XSH.env
    for k, v in pre_env.items():
        env[k] = v

    if not shell_kwargs.get("norc"):
        _autoload_xontribs(env)
    _load_rc_files(shell_kwargs, args, env, execer, ctx)
    # create shell
    XSH.shell = Shell(execer=execer, **shell_kwargs)
    ctx["__name__"] = "__main__"
    return env


def premain(argv=None):
    """Setup for main xonsh entry point. Returns parsed arguments."""
    if argv is None:
        argv = sys.argv[1:]
    setup_timings(argv)
    setproctitle = get_setproctitle()
    if setproctitle is not None:
        setproctitle(" ".join(["xonsh"] + argv))
    args = parser.parse_args(argv)
    if args.help:
        parser.print_help()
        parser.exit()
    shell_kwargs = {
        "shell_type": args.shell_type,
        "completer": False,
        "login": False,
        "scriptcache": args.scriptcache,
        "cacheall": args.cacheall,
        "ctx": XSH.ctx,
    }
    if args.login or sys.argv[0].startswith("-"):
        args.login = True
        shell_kwargs["login"] = True
    if args.norc:
        shell_kwargs["norc"] = True
    elif args.rc:
        shell_kwargs["rc"] = args.rc
    shell_kwargs["inherit_env"] = args.inherit_env
    sys.displayhook = _pprint_displayhook
    if args.command is not None:
        args.mode = XonshMode.single_command
        shell_kwargs["shell_type"] = "none"
        xonsh_mode = "single_command"
    elif args.file is not None:
        args.mode = XonshMode.script_from_file
        shell_kwargs["shell_type"] = "none"
        xonsh_mode = "script_from_file"
    elif not sys.stdin.isatty() and not args.force_interactive:
        args.mode = XonshMode.script_from_stdin
        shell_kwargs["shell_type"] = "none"
        xonsh_mode = "script_from_stdin"
    else:
        args.mode = XonshMode.interactive
        shell_kwargs["completer"] = True
        shell_kwargs["login"] = True
        xonsh_mode = "interactive"

    pre_env = {
        "XONSH_LOGIN": shell_kwargs["login"],
        "XONSH_INTERACTIVE": args.force_interactive
        or (args.mode == XonshMode.interactive),
        "XONSH_MODE": xonsh_mode,
    }
    pre_env["COLOR_RESULTS"] = os.getenv("COLOR_RESULTS", pre_env["XONSH_INTERACTIVE"])

    # Load -DVAR=VAL arguments.
    if args.defines is not None:
        for x in args.defines:
            try:
                var, val = x.split("=", 1)
                pre_env[var] = unquote(val)
            except Exception:
                print(
                    f"Wrong format for -D{x} argument. Use -DVAR=VAL form.",
                    file=sys.stderr,
                )
                sys.exit(1)

    start_services(shell_kwargs, args, pre_env=pre_env)
    return args


def _failback_to_other_shells(args, err):
    # only failback for interactive shell; if we cannot tell, treat it
    # as an interactive one for safe.
    if hasattr(args, "mode") and args.mode != XonshMode.interactive:
        raise err

    foreign_shell = None

    # look first in users login shell $SHELL.
    # use real os.environ, in case Xonsh hasn't initialized yet
    # but don't fail back to same shell that just failed.

    try:
        env_shell = os.getenv("SHELL")
        if env_shell and os.path.exists(env_shell) and env_shell != sys.argv[0]:
            foreign_shell = env_shell
    except Exception:
        pass

    # otherwise, find acceptable shell from (unix) list of installed shells.

    if not foreign_shell:
        excluded_list = ["xonsh", "screen"]
        shells_file = "/etc/shells"
        if not os.path.exists(shells_file):
            # right now, it will always break here on Windows
            raise err
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
        print("Xonsh encountered an issue during launch.", file=sys.stderr)
        print("Please report to https://github.com/xonsh/xonsh/issues", file=sys.stderr)
        print(f"Failback to {foreign_shell}", file=sys.stderr)
        os.execlp(foreign_shell, foreign_shell)
    else:
        raise err


def main(argv=None):
    args = None
    try:
        args = premain(argv)
        sys.exit(main_xonsh(args))
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

    env = XSH.env
    shell = XSH.shell
    history = XSH.history
    exit_code = 0

    if shell and not env["XONSH_INTERACTIVE"]:
        shell.ctx.update({"exit": sys.exit})

    # store a sys.exc_info() tuple to record any exception that might occur in the user code that we are about to execute
    # if this does not change, no exceptions were thrown. Otherwise, print a traceback that does not expose xonsh internals
    exc_info = None, None, None

    try:
        if args.mode == XonshMode.interactive:
            # enter the shell

            # Setted again here because it is possible to call main_xonsh() without calling premain(), namely in the tests.
            env["XONSH_INTERACTIVE"] = True

            ignore_sigtstp()
            if (
                env["XONSH_INTERACTIVE"]
                and not env["XONSH_SUPPRESS_WELCOME"]
                and sys.stdin.isatty()  # In case the interactive mode is forced but no tty (input from pipe).
                and not any(os.path.isfile(i) for i in env["XONSHRC"])
                and not any(os.path.isdir(i) for i in env["XONSHRC_DIR"])
            ):
                print_welcome_screen()
            events.on_pre_cmdloop.fire()
            try:
                shell.shell.cmdloop()
            finally:
                events.on_post_cmdloop.fire()
        elif args.mode == XonshMode.single_command:
            # run a single command and exit
            exc_info = run_code_with_cache(
                args.command.lstrip(),
                "<string>",
                shell.execer,
                glb=shell.ctx,
                mode="single",
            )
            if history is not None and history.last_cmd_rtn is not None:
                exit_code = history.last_cmd_rtn
        elif args.mode == XonshMode.script_from_file:
            # run a script contained in a file
            path = os.path.abspath(os.path.expanduser(args.file))
            if os.path.isfile(path):
                sys.argv = [args.file] + args.args
                env.update(make_args_env())  # $ARGS is not sys.argv
                env["XONSH_SOURCE"] = path
                shell.ctx.update({"__file__": args.file, "__name__": "__main__"})
                exc_info = run_script_with_cache(
                    args.file, shell.execer, glb=shell.ctx, loc=None, mode="exec"
                )
            else:
                print(f"xonsh: {args.file}: No such file or directory.")
                exit_code = 1
        elif args.mode == XonshMode.script_from_stdin:
            # run a script given on stdin
            code = sys.stdin.read()
            exc_info = run_code_with_cache(
                code, "<stdin>", shell.execer, glb=shell.ctx, loc=None, mode="exec"
            )
    except SyntaxError:
        exit_code = 1
        debug_level = env.get("XONSH_DEBUG", 0)
        if debug_level == 0:
            # print error without tracktrace
            display_error_message(sys.exc_info())
        else:
            # pass error to finally clause
            exc_info = sys.exc_info()
    except SystemExit:
        exc_info = sys.exc_info()
    finally:
        if exc_info != (None, None, None):
            err_type, err, _ = exc_info
            if err_type is SystemExit:
                code = getattr(exc_info[1], "code", 0)
                if code is None:
                    exit_code = 0
                else:
                    exit_code = code
                    try:
                        exit_code = int(code)
                    except ValueError:
                        pass
                XSH.exit = exit_code
            else:
                exit_code = 1
                print_exception(None, exc_info)

        if isinstance(XSH.exit, int):
            exit_code = XSH.exit
        events.on_exit.fire(exit_code=exit_code)
        postmain(args)
    return exit_code


def postmain(args=None):
    """Teardown for main xonsh entry point, accepts parsed arguments."""
    XSH.unload()
    XSH.shell = None


@contextlib.contextmanager
def main_context(argv=None):
    """Generator that runs pre- and post-main() functions. This has two iterations.
    The first yields the shell. The second returns None but cleans
    up the shell.
    """
    args = premain(argv)
    yield XSH.shell
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
    packages ``__init__.py`` will allow xonsh to be fully used in the
    package in headless or headed mode. This function is primarily indended to
    make starting up xonsh for 3rd party packages easier.

    Here is example of using this at the top of an ``__init__.py``::

        from xonsh.main import setup
        setup()
        del setup

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
        execer = Execer(filename="<stdin>")
        XSH.load(ctx=ctx, execer=execer)
        XSH.shell = Shell(execer, ctx=ctx, shell_type=shell_type)
    XSH.env.update(env)
    install_import_hooks(XSH.execer)
    XSH.aliases.update(aliases)
    if xontribs:
        xontribs_load(xontribs)

    if threadable_predictors:
        XSH.commands_cache.threadable_predictors.update(threadable_predictors)
