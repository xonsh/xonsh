import atexit
import builtins
import signal
from xonsh.platform import ON_POSIX, ON_WINDOWS
from xonsh.lazyasd import lazyobject
import xonsh.built_ins
import sys

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


def _lastflush(s=None, f=None):
    if XSH.history is not None:
        XSH.history.flush(at_exit=True)


class XonshSession:
    """All components defining a xonsh session."""

    def __init__(self):
        self.execer = None
        self.ctx = {}
        self.builtins_loaded = False
        self.history = None
        self.shell = None
        self.env = None
        self.rc_files = None

    def load(self, execer=None, ctx=None, **kwargs):
        """Loads the session with default values.

        Parameters
        ----------
        execer : Execer, optional
            Xonsh execution object, may be None to start
        ctx : Mapping, optional
            Context to start xonsh session with.
        """
        from xonsh.environ import Env, default_env
        from xonsh.commands_cache import CommandsCache
        from xonsh.completers.init import default_completers

        if not hasattr(builtins, "__xonsh__"):
            builtins.__xonsh__ = self
        if ctx is not None:
            self.ctx = ctx

        self.env = kwargs.pop("env") if "env" in kwargs else Env(default_env())
        self.help = xonsh.built_ins.helper
        self.superhelp = xonsh.built_ins.superhelper
        self.pathsearch = xonsh.built_ins.pathsearch
        self.globsearch = xonsh.built_ins.globsearch
        self.regexsearch = xonsh.built_ins.regexsearch
        self.glob = xonsh.built_ins.globpath
        self.expand_path = xonsh.built_ins.expand_path
        self.exit = False
        self.stdout_uncaptured = None
        self.stderr_uncaptured = None

        if hasattr(builtins, "exit"):
            self.pyexit = builtins.exit
            del builtins.exit

        if hasattr(builtins, "quit"):
            self.pyquit = builtins.quit
            del builtins.quit

        self.subproc_captured_stdout = xonsh.built_ins.subproc_captured_stdout
        self.subproc_captured_inject = xonsh.built_ins.subproc_captured_inject
        self.subproc_captured_object = xonsh.built_ins.subproc_captured_object
        self.subproc_captured_hiddenobject = xonsh.built_ins.subproc_captured_hiddenobject
        self.subproc_uncaptured = xonsh.built_ins.subproc_uncaptured
        self.execer = execer
        self.commands_cache = (
            kwargs.pop("commands_cache")
            if "commands_cache" in kwargs
            else CommandsCache()
        )
        self.modules_cache = {}
        self.all_jobs = {}
        self.ensure_list_of_strs = xonsh.built_ins.ensure_list_of_strs
        self.list_of_strs_or_callables = xonsh.built_ins.list_of_strs_or_callables
        self.list_of_list_of_strs_outer_product = xonsh.built_ins.list_of_list_of_strs_outer_product
        self.eval_fstring_field = xonsh.built_ins.eval_fstring_field

        self.completers = default_completers()
        self.call_macro = xonsh.built_ins.call_macro
        self.enter_macro = xonsh.built_ins.enter_macro
        self.path_literal = xonsh.built_ins.path_literal

        self.builtins = xonsh.built_ins.create_builtins_namespace(execer)
        self._default_builtin_names = frozenset(vars(self.builtins))

        aliases_given = kwargs.pop("aliases", None)
        for attr, value in kwargs.items():
            if hasattr(self, attr):
                setattr(self, attr, value)
        self.link_builtins(aliases_given)
        self.builtins_loaded = True

    def link_builtins(self, aliases=None):
        from xonsh.aliases import Aliases, make_default_aliases

        # public built-ins
        for refname in self._default_builtin_names:
            objname = f"__xonsh__.builtins.{refname}"
            proxy = xonsh.built_ins.DynamicAccessProxy(refname, objname)
            setattr(builtins, refname, proxy)

        # sneak the path search functions into the aliases
        # Need this inline/lazy import here since we use locate_binary that
        # relies on __xonsh__.env in default aliases
        if aliases is None:
            aliases = Aliases(make_default_aliases())
        self.aliases = builtins.default_aliases = builtins.aliases = aliases
        atexit.register(_lastflush)
        for sig in AT_EXIT_SIGNALS:
            resetting_signal_handle(sig, _lastflush)

    def unlink_builtins(self):
        for name in self._default_builtin_names:
            if hasattr(builtins, name):
                delattr(builtins, name)

    def unload(self):
        if not hasattr(builtins, "__xonsh__"):
            self.builtins_loaded = False
            return
        env = getattr(self, "env", None)
        if hasattr(self.env, "undo_replace_env"):
            env.undo_replace_env()
        if hasattr(self, "pyexit"):
            builtins.exit = self.pyexit
        if hasattr(self, "pyquit"):
            builtins.quit = self.pyquit
        if not self.builtins_loaded:
            return
        self.unlink_builtins()
        delattr(builtins, "__xonsh__")
        self.builtins_loaded = False


# singleton
XSH = XonshSession()
