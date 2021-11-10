import atexit
import builtins
import signal
from xonsh.platform import ON_POSIX, ON_WINDOWS
from xonsh.lazyasd import lazyobject
from xonsh.tools import print_color, XonshCalledProcessError, XonshError
import xonsh.built_ins
import sys
from pathlib import Path
import contextlib
import types


@lazyobject
def AT_EXIT_SIGNALS():
    sigs = (
        signal.SIGABRT,
        signal.SIGFPE,
        signal.SIGILL,
        signal.SIGSEGV,
        signal.SIGTERM,
    )
    if ON_POSIX:
        sigs += (signal.SIGTSTP, signal.SIGQUIT, signal.SIGHUP)
    return sigs


def resetting_signal_handle(sig, f):
    """Sets a new signal handle that will automatically restore the old value
    once the new handle is finished.
    """
    oldh = signal.getsignal(sig)

    def newh(s=None, frame=None):
        f(s, frame)
        signal.signal(sig, oldh)
        if sig != 0:
            sys.exit(sig)

    signal.signal(sig, newh)


def _create_builtins_namespace(execer, aliases):
    from xonsh.events import events

    return types.SimpleNamespace(
        # public built-ins
        XonshError=XonshError,
        XonshCalledProcessError=XonshCalledProcessError,
        evalx=None if execer is None else execer.eval,
        execx=None if execer is None else execer.exec,
        compilex=None if execer is None else execer.compile,
        events=events,
        print_color=print_color,
        printx=print_color,
        default_aliases = aliases,
        aliases = aliases
    )


class XonshSession:
    """All components defining a xonsh session."""

    def __init__(self, execer, ctx=None, env=None, aliases=None):
        from xonsh.environ import Env, default_env
        from xonsh.commands_cache import CommandsCache
        from xonsh.completers.init import default_completers
        # Need this inline/lazy import here since we use locate_binary that
        # relies on __xonsh__.env in default aliases
        from xonsh.aliases import Aliases, make_default_aliases

        # Loadable state
        self.execer = execer
        self.ctx = {} if ctx is None else ctx
        self.env = Env(default_env() if env is None else {})
        self.history = None
        self.shell = None
        self.rc_files = None
        self.exit = False
        self.stdout_uncaptured = None
        self.stderr_uncaptured = None
        self.shell = None

        cache_path = (
            (Path(env["XONSH_DATA_DIR"]).joinpath("commands-cache.pickle").resolve())
            if env is not None
            and "XONSH_DATA_DIR" in env
            and env.get("COMMANDS_CACHE_SAVE_INTERMEDIATE")
            else None
        )
        self.commands_cache = CommandsCache(cache_path)
        self.modules_cache = {}
        self.all_jobs = {}

        self.completers = default_completers()

        # Sneak the path search functions into the aliases
        self.aliases = Aliases(make_default_aliases() if aliases is None else aliases)

        self.builtins = _create_builtins_namespace(execer, self.aliases)
        self._default_builtin_names = frozenset(vars(self.builtins))

        self._py_exit = None
        self._py_quit = None

        self.help = xonsh.built_ins.helper
        self.superhelp = xonsh.built_ins.superhelper
        self.pathsearch = xonsh.built_ins.pathsearch
        self.globsearch = xonsh.built_ins.globsearch
        self.regexsearch = xonsh.built_ins.regexsearch
        self.glob = xonsh.built_ins.globpath
        self.expand_path = xonsh.built_ins.expand_path

        self.subproc_captured_stdout = xonsh.built_ins.subproc_captured_stdout
        self.subproc_captured_inject = xonsh.built_ins.subproc_captured_inject
        self.subproc_captured_object = xonsh.built_ins.subproc_captured_object
        self.subproc_captured_hiddenobject = xonsh.built_ins.subproc_captured_hiddenobject
        self.subproc_uncaptured = xonsh.built_ins.subproc_uncaptured

        self.ensure_list_of_strs = xonsh.built_ins.ensure_list_of_strs
        self.list_of_strs_or_callables = xonsh.built_ins.list_of_strs_or_callables
        self.list_of_list_of_strs_outer_product = xonsh.built_ins.list_of_list_of_strs_outer_product
        self.eval_fstring_field = xonsh.built_ins.eval_fstring_field

        self.call_macro = xonsh.built_ins.call_macro
        self.enter_macro = xonsh.built_ins.enter_macro
        self.path_literal = xonsh.built_ins.path_literal

    def _disable_python_exit(self):
        # Disable Python interactive quit/exit
        if hasattr(builtins, "exit"):
            self._py_exit = builtins.exit
            del builtins.exit

        if hasattr(builtins, "quit"):
            self._py_quit = builtins.quit
            del builtins.quit

    def _restore_python_exit(self):
        if self._py_exit is not None:
            builtins.exit = self._py_exit
        if self._py_quit is not None:
            builtins.quit = self._py_quit

    def _link_builtins(self, names):
        # public Xonsh built-ins to Python builtins
        for name in names:
            ref = f"__xonsh__.builtins.{name}"
            proxy = xonsh.built_ins.DynamicAccessProxy(name, ref)
            setattr(builtins, name, proxy)

    def _unlink_builtins(self, names):
        for name in names:
            if hasattr(builtins, name):
                delattr(builtins, name)

    def _load(self):
        """Load the session into the Python namespace"""
        self._disable_python_exit()
        self._link_builtins(self._default_builtin_names)

        # Cleanup on exit
        def _lastflush(s=None, f=None):
            if self.history is not None:
                self.history.flush(at_exit=True)
        atexit.register(_lastflush)
        for sig in AT_EXIT_SIGNALS:
            resetting_signal_handle(sig, _lastflush)

        # Make sure we have __xonsh__
        builtins.__xonsh__ = self

    def _unload(self):
        """Unload the session from the Python namespace"""
        if not hasattr(builtins, "__xonsh__"):
            return

        env = getattr(self, "env", None)
        if hasattr(self.env, "undo_replace_env"):
            env.undo_replace_env()

        self._restore_python_exit()
        self._unlink_builtins(self._default_builtin_names)
        delattr(builtins, "__xonsh__")


# Current instance
XSH = None

_XSH_STACK = []


def push_session(session):
    global XSH

    if XSH is not None:
        XSH._unload()

    XSH = session
    _XSH_STACK.append(session)

    session._load()


def pop_session():
    global XSH

    if XSH is not None:
        XSH._unload()

    session = _XSH_STACK.pop()
    XSH = session

    session._load()
    return session


@contextlib.contextmanager
def session_as(session):
    push_session(session)

    try:
        yield
    finally:
        assert pop_session() is session
