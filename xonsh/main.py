"""The main xonsh script."""

import argparse
import atexit
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
from xonsh.environ import (
    get_home_xonshrc_path,
    load_origin_env_from_file,
    make_args_env,
    os_environ,
    xonshrc_context,
)
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


def get_current_xonsh():
    """Return the path used to invoke the current xonsh session.

    This is a thin wrapper around ``sys.argv[0]`` so that callers can share
    a single source of truth for "how was this xonsh started".

    Examples
    --------
    - Entry point: ``/usr/bin/xonsh``.
    - Source via ``python -m xonsh``: ``/path/to/xonsh/__main__.py``
    """
    return sys.argv[0]


def path_argument(s):
    """Return a path only if the path is actually legal (file or directory)

    This is very similar to argparse.FileType, except that it doesn't return
    an open file handle, but rather simply validates the path."""

    s = os.path.abspath(os.path.expanduser(s))
    if not os.path.exists(s):
        msg = f"{s!r} must be a valid path to a file or directory"
        raise argparse.ArgumentTypeError(msg)
    return s


#: Module-level state written by :func:`_acquire_controlling_terminal` and
#: consumed by :func:`_release_controlling_terminal`. Kept as a dict so that
#: the atexit restorer is a thin closure without extra globals.
_fg_tty_state: dict = {"acquired": False, "tty_fd": -1, "old_fg": -1}

#: Idempotency flag for :func:`_setup_controlling_terminal`. Flipped to
#: ``True`` once the TTY signal handlers have been installed in a given
#: process — a second call becomes a cheap no-op. Exposed on the module
#: so tests can reset it between runs.
_tty_setup_done: bool = False


def _acquire_controlling_terminal():
    """Put xonsh into the foreground process group of its controlling TTY.

    Background
    ----------
    On POSIX systems every terminal has a single *foreground process group*.
    Only processes belonging to that group may read from or perform control
    operations on the terminal without being suspended by ``SIGTTIN`` /
    ``SIGTTOU``. Interactive shells (bash, zsh, …) perform a small startup
    handshake to make sure they are that foreground group: they put
    themselves into their own process group and call ``tcsetpgrp`` on the
    TTY. xonsh historically did not do this — it relied on the launching
    shell to have arranged things correctly. That assumption breaks in a
    number of environments:

    * Flatpak / Bubblewrap and similar sandboxes that spawn children
      without adjusting the TTY's foreground group.
    * Build systems, CI runners, IDE integrated terminals and service
      managers (e.g. ``systemd --user``) that don't wire xonsh up as the
      foreground process of the PTY they attach.
    * Nested containers that reuse the outer PTY.

    In those cases xonsh is technically a background process. Every TTY
    touch — ``tcgetattr`` during prompt_toolkit init, ``tcsetpgrp`` when
    launching a pipeline, plain writes when stdout is line-buffered —
    raises ``SIGTTIN`` or ``SIGTTOU``. The signals are delivered to
    Python's asyncio wakeup pipe faster than it can be drained, overflow
    it, and crash startup with ``BlockingIOError: Resource temporarily
    unavailable``. Other signals interrupt ``termios`` calls mid-flight
    and surface as ``termios.error: Interrupted system call``.

    The fix
    -------
    Perform the same handshake bash does, very early in xonsh's lifetime:

    1. Find a TTY file descriptor (stderr, same choice xonsh already uses
       for :func:`xonsh.procs.jobs.give_terminal_to`).
    2. Compare its current foreground group to our process group. If we
       are already foreground, record that and exit fast.
    3. Block ``SIGTTOU``, ``SIGTTIN``, ``SIGTSTP`` and ``SIGCHLD`` in the
       calling thread so that the handshake cannot suspend us or be
       reentered by a child's death.
    4. Call ``setpgid(0, 0)`` to make us a process group of our own.
    5. Call ``tcsetpgrp(tty_fd, getpgrp())`` to install that group as
       the foreground group of the TTY.
    6. Remember the previous foreground group so :func:`_release_controlling_terminal`
       (registered via ``atexit``) can hand it back on shutdown.

    Every failure mode returns ``False`` cleanly — this is a best-effort
    upgrade, never a hard requirement. Windows has no concept of
    controlling terminals in the POSIX sense; the function immediately
    returns ``False`` there.

    Environment
    -----------
    Set ``XONSH_NO_FG_TAKEOVER=1`` in the parent environment to disable
    the handshake entirely. This is an escape hatch for rare cases where
    the takeover conflicts with a parent process that expects xonsh to
    stay in its original process group.

    Returns
    -------
    bool
        ``True`` if xonsh is now (or already was) the foreground process
        group of its controlling terminal. ``False`` on any failure or
        when the handshake is not applicable (non-TTY, Windows, session
        leader, disabled by env var, …).
    """
    if ON_WINDOWS:
        return False
    if os.environ.get("XONSH_NO_FG_TAKEOVER"):
        return False
    # pthread_sigmask is POSIX-only and may be absent on exotic builds.
    if not hasattr(signal, "pthread_sigmask"):
        return False
    # Use stderr as the TTY handle. xonsh already uses FD 2 for
    # give_terminal_to in pipeline management (xonsh/procs/jobs.py), so
    # this keeps the choice consistent across subsystems.
    try:
        tty_fd = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        return False
    try:
        if not os.isatty(tty_fd):
            return False
    except OSError:
        return False
    # A session leader cannot change its own process group id, so the
    # setpgid(0, 0) call below would fail with EPERM. Detect this up
    # front and skip cleanly — if we are session leader we almost
    # certainly already own the TTY anyway.
    try:
        if os.getsid(0) == os.getpid():
            return False
    except OSError:
        return False
    # Block the signals that can disrupt the handshake. SIGTTOU is the
    # critical one — without this mask, the tcsetpgrp() call below
    # would send SIGTTOU to our own process group (we are in a
    # background group at this point) and suspend us. SIGTTIN is
    # blocked for symmetry; SIGTSTP so that a stray Ctrl+Z cannot
    # desynchronise state; SIGCHLD so a child reaping does not
    # interrupt us mid-handshake. The block is thread-local — it
    # does not affect signal disposition for the rest of the process.
    block = {signal.SIGTTOU, signal.SIGTTIN, signal.SIGTSTP, signal.SIGCHLD}
    try:
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, block)
    except (AttributeError, OSError):
        return False
    try:
        try:
            current_fg = os.tcgetpgrp(tty_fd)
        except OSError:
            return False
        my_pgid = os.getpgrp()
        if current_fg == my_pgid:
            # We are already the foreground group. Nothing to acquire
            # and nothing to release on shutdown — return success but
            # do *not* mark state as acquired, so the atexit restorer
            # stays a no-op and we don't risk racing with the parent
            # shell's own tcsetpgrp() on exit.
            return True
        # Become our own process group leader. If we are already a
        # leader this is a no-op; if the kernel refuses (EPERM), we
        # bail out. After this succeeds our pgid == pid.
        try:
            os.setpgid(0, 0)
        except (PermissionError, OSError):
            return False
        my_pgid = os.getpgrp()
        # Install our pgid as the TTY's foreground group. SIGTTOU is
        # blocked, so this cannot suspend us; it may still fail with
        # EPERM if the TTY belongs to a different session, or ENOTTY
        # if the fd lost its TTY-ness between isatty() and now — both
        # degrade to a clean False return.
        try:
            os.tcsetpgrp(tty_fd, my_pgid)
        except OSError:
            return False
        _fg_tty_state["acquired"] = True
        _fg_tty_state["tty_fd"] = tty_fd
        _fg_tty_state["old_fg"] = current_fg
        return True
    finally:
        # Always restore the signal mask, even on error paths. We only
        # changed the mask for this thread, so this call is cheap and
        # cannot fail in any practical scenario — but guard it anyway.
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except (AttributeError, OSError):
            pass


def _release_controlling_terminal():
    """Give the controlling TTY's foreground group back to its previous
    owner on shutdown.

    Registered via :mod:`atexit` when :func:`_acquire_controlling_terminal`
    actually took over the TTY. A no-op in every other case: if xonsh was
    already foreground, if the handshake failed, or if there is no TTY.

    Restoring the previous foreground group matters because the parent
    shell (bash, zsh, another xonsh, …) usually calls ``wait`` on us and
    then expects to read from the terminal. If xonsh leaves its own pgid
    installed as foreground, the parent will immediately receive
    ``SIGTTIN`` on the next read. Robust shells recover from this, but it
    is much cleaner to hand the TTY back explicitly.
    """
    if not _fg_tty_state.get("acquired"):
        return
    tty_fd = _fg_tty_state.get("tty_fd", -1)
    old_fg = _fg_tty_state.get("old_fg", -1)
    if tty_fd < 0 or old_fg < 0:
        return
    if not hasattr(signal, "pthread_sigmask"):
        return
    try:
        old_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK, {signal.SIGTTOU, signal.SIGTTIN}
        )
    except (AttributeError, OSError):
        return
    try:
        try:
            os.tcsetpgrp(tty_fd, old_fg)
        except OSError:
            # Parent may already have reclaimed the TTY, or the fd may
            # have been closed by shutdown — either way nothing
            # actionable remains. Swallow silently: this runs inside
            # atexit and raising here would just make shutdown noisy.
            pass
    finally:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except (AttributeError, OSError):
            pass
        # Clear state so a second call (e.g. atexit + explicit shutdown)
        # is a no-op.
        _fg_tty_state["acquired"] = False
        _fg_tty_state["tty_fd"] = -1
        _fg_tty_state["old_fg"] = -1


def _setup_controlling_terminal():
    """Run the TTY startup handshake and install matching signal handlers.

    This is the *orchestration* layer around
    :func:`_acquire_controlling_terminal`: it installs the baseline
    signal policy, optionally calls the handshake, and registers the
    ``atexit`` restorer when appropriate. It is idempotent — a second
    call in the same process is a cheap no-op.

    It is called from the top of :func:`main` so that the handshake
    happens *before* :func:`premain`. ``premain`` loads xontribs and
    runs user ``xonshrc`` files, and rc files are arbitrary xonsh code
    — they routinely contain ``$(...)`` / ``!(...)`` captures and can
    invoke interactive programs like ``fzf`` that will themselves want
    to take over the TTY via ``tcsetattr``. When xonsh is foreground
    *before* rc runs, every downstream TTY operation simply works; when
    it is not, and the handshake cannot fix that (sandboxed nested
    containers, cross-session TTYs, …), the ``SIG_IGN`` fallback
    installed here prevents the asyncio wakeup pipe from overflowing
    during rc execution. It is also called from :func:`main_xonsh` as a
    backup for callers that enter the shell loop without going through
    :func:`main` (tests, programmatic invocation).

    Signal policy
    -------------
    Step 1: **always** install a Python-level no-op handler for
    ``SIGTTIN`` and ``SIGTTOU``, on any POSIX invocation. This matches
    the historical xonsh behavior (before this function existed,
    ``main_xonsh`` installed the same no-op handler unconditionally)
    and protects script-mode xonsh from being suspended by
    ``SIG_DFL`` when something indirectly touches the TTY. A Python
    handler is preferred over ``SIG_IGN`` here because the latter is
    inherited across ``exec`` and would subtly break job control in
    subprocess children.

    Step 2: if stderr is a real TTY, attempt the foreground handshake.
    If it succeeds, the no-op handlers installed in step 1 already
    cover the ``success`` case and no further action is needed. If
    the handshake fails (typical in sandboxes that cannot be made
    foreground), **replace** the no-op handlers with ``SIG_IGN`` —
    the kernel will then discard ``SIGTTIN`` / ``SIGTTOU`` outright
    and they will never reach Python's asyncio wakeup pipe, which
    would otherwise overflow with ``BlockingIOError`` under a signal
    storm.

    Step 3: register ``atexit`` to restore the previous foreground
    group on shutdown, but only when the handshake *actually*
    transferred foreground ownership (``_fg_tty_state["acquired"]``
    is True). Fast-path success — where we were already foreground —
    leaves state unacquired so the restorer does nothing and we don't
    race with the parent shell's own ``tcsetpgrp`` on exit.

    Non-TTY callers (script mode, piped input, test runners under
    pytest) stop after step 1 and keep the historical Python handlers.
    """
    global _tty_setup_done
    if _tty_setup_done:
        return
    if ON_WINDOWS:
        return
    _tty_setup_done = True

    # Step 1: unconditional Python no-op handlers for SIGTTIN/SIGTTOU.
    # This matches the pre-handshake xonsh behavior and is what
    # script-mode / non-TTY callers rely on. The only reason to
    # deviate from it is the sandbox-failure case below, which
    # overrides with SIG_IGN to avoid the asyncio wakeup pipe storm.
    def func_sig_ttin_ttou(n, f):
        pass

    signal.signal(signal.SIGTTIN, func_sig_ttin_ttou)
    signal.signal(signal.SIGTTOU, func_sig_ttin_ttou)

    # Step 2: only attempt the handshake when stderr is a real TTY.
    # Script mode, piped stdin/stdout, and test runners (pytest
    # captures stderr via a pipe) all bail out here and keep the
    # Python handlers from step 1.
    try:
        if not os.isatty(sys.stderr.fileno()):
            return
    except (AttributeError, OSError, ValueError):
        return

    fg_acquired = _acquire_controlling_terminal()
    if fg_acquired:
        # Step 3: register the shutdown restorer only if the handshake
        # actually changed the foreground group. The fast-path case
        # (we were already foreground) deliberately leaves
        # ``_fg_tty_state`` unacquired so the restorer does nothing
        # and we never race with the parent shell's own tcsetpgrp
        # on exit.
        if _fg_tty_state.get("acquired"):
            atexit.register(_release_controlling_terminal)
        # Python handlers from step 1 remain in place as a safety net.
    else:
        # Sandbox failure path: the kernel *will* keep sending
        # SIGTTIN/SIGTTOU every time xonsh touches the TTY, and a
        # Python-level handler would overflow asyncio's signal wakeup
        # pipe with ``BlockingIOError`` during a signal storm. Replace
        # the step-1 handlers with SIG_IGN so the kernel discards the
        # signals outright and never routes them through Python.
        # SIG_IGN is inherited across ``exec``, but in a sandbox
        # children have the same TTY ownership problem anyway, so
        # this is the right default.
        signal.signal(signal.SIGTTIN, signal.SIG_IGN)
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)


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
        "-DVAR=VAL or inherit existing variable with -DVAR. May be used many times.",
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
    p.add_argument(
        "--save-origin-env",
        help="Save origin environment variables before running xonsh. Use --load-origin-env to run xonsh with saved origin environment.",
        dest="save_origin_env",
        action="store_true",
        default=False,
    )
    p.add_argument(
        "--load-origin-env",
        help="Load origin environment variables that were saved before running xonsh by using --save-origin-env",
        dest="load_origin_env",
        action="store_true",
        default=False,
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
    XSH.load(
        ctx=ctx,
        execer=execer,
        inherit_env=shell_kwargs.get("inherit_env", True),
        save_origin_env=args.save_origin_env,
    )
    events.on_timingprobe.fire(name="post_xonsh_session_load")

    install_import_hooks(execer)

    env = XSH.env
    for k, v in pre_env.items():
        env[k] = v

    _load_rc_files(shell_kwargs, args, env, execer, ctx)
    if not shell_kwargs.get("norc"):
        _autoload_xontribs(env)
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

    # Load -DVAR=VAL arguments.
    if args.defines is not None:
        for x in args.defines:
            var = x.split("=", 1)
            if len(var) == 2:
                var, val = var
                pre_env[var] = unquote(val)
            elif len(var) == 1:
                var = var[0]
                if var in os_environ:
                    pre_env[var] = os_environ[var]
                elif os_environ.get("XONSH_DEBUG", "0") != "0":
                    print(
                        f"Variable {var!r} is not defined in origin environment.",
                        file=sys.stderr,
                    )

    if args.load_origin_env:
        origin_env = load_origin_env_from_file()
        os.environ.clear()
        os.environ.update(origin_env)

    pre_env["COLOR_RESULTS"] = os.getenv(
        "COLOR_RESULTS", str(pre_env["XONSH_INTERACTIVE"])
    )

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
    # Run the TTY startup handshake *before* premain so that xontrib
    # loading and xonshrc execution happen with xonsh already as the
    # foreground process group. rc files are arbitrary user code and
    # can contain subprocess captures ``$(...)``/``!(...)`` — including
    # interactive tools like ``fzf`` that take over the TTY via
    # ``tcsetattr``. Having the handshake done before rc runs means
    # those child processes inherit a "foreground shell" context and
    # the race between their own TTY manipulation and xonsh's
    # :func:`xonsh.procs.jobs.give_terminal_to` never has to open.
    # See :func:`_setup_controlling_terminal` for the full rationale.
    _setup_controlling_terminal()
    args = None
    try:
        args = premain(argv)
        sys.exit(main_xonsh(args))
    except Exception as err:
        _failback_to_other_shells(args, err)


def main_xonsh(args):
    """Main entry point for xonsh cli."""
    # Normally :func:`main` has already run the handshake before
    # premain — this call is a cheap idempotent no-op in that case
    # (the module-level ``_tty_setup_done`` flag short-circuits).
    # It exists so that callers which enter the shell loop without
    # going through ``main`` (tests, programmatic launches) still
    # get the same TTY signal setup.
    _setup_controlling_terminal()

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
            if os.path.isdir(path):
                print(f"xonsh: {args.file}: Is a directory.")
                exit_code = 1
            elif os.path.exists(path):
                sys.argv = [args.file] + args.args
                env.update(make_args_env())  # $ARGS is not sys.argv
                env["XONSH_SOURCE"] = path
                shell.ctx.update({"__file__": args.file, "__name__": "__main__"})
                # Add script directory to sys.path[0], matching CPython behavior.
                # See https://docs.python.org/3/library/sys_path_init.html
                script_dir = os.path.dirname(path)
                old_sys_path = sys.path.copy()
                sys.path.insert(0, script_dir)
                try:
                    exc_info = run_script_with_cache(
                        args.file, shell.execer, glb=shell.ctx, loc=None, mode="exec"
                    )
                finally:
                    sys.path[:] = old_sys_path
            else:
                print(f"xonsh: {args.file}: No such file.")
                exit_code = 1
        elif args.mode == XonshMode.script_from_stdin:
            # run a script given on stdin
            code = sys.stdin.read()
            # Reopen stdin from /dev/tty so that child processes
            # (e.g. fzf, vim) can interact with the terminal instead
            # of inheriting the exhausted pipe.
            try:
                tty_fd = os.open("/dev/tty", os.O_RDONLY)
                os.dup2(tty_fd, 0)
                os.close(tty_fd)
                sys.stdin = open(0, closefd=False)
            except OSError:
                pass  # no controlling terminal (cron, CI, etc.)
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
    env=(("XONSH_SUBPROC_CMD_RAISE_ERROR", True),),
    aliases=(),
    xontribs=(),
    threadable_predictors=(),
    history_backend=None,
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
        XSH.shell = Shell(
            execer, ctx=ctx, shell_type=shell_type, history_backend=history_backend
        )
    XSH.env.update(env)
    install_import_hooks(XSH.execer)
    XSH.aliases.update(aliases)
    if xontribs:
        xontribs_load(xontribs)

    if threadable_predictors:
        XSH.commands_cache.threadable_predictors.update(threadable_predictors)
