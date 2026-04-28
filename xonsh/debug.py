"""Debug utilities for a running xonsh session.

Provides :class:`XonshDebug`, which is attached to the session as
``__xonsh__.debug`` and exposed to user code through the ``@.`` interface
as ``@.debug``. The main entry point is :meth:`XonshDebug.breakpoint`.
"""

import builtins
import importlib
import importlib.util
import sys
import threading
import traceback
import warnings

CANONIC_BREAKPOINT_ENGINES = frozenset(
    {"auto", "pdbp", "ipdb", "pdb", "execer", "eval"}
)


class XonshDebugQuit(Exception):
    """Raised from the ``eval`` REPL when the user types ``exit``/``quit``/``q``.

    Propagates out of :meth:`XonshDebug.breakpoint` so that execution at
    the breakpoint site is aborted rather than resumed. Catch it
    explicitly if you want to handle user-initiated aborts.
    """


def is_breakpoint_engine(x):
    """Enumerated values of $XONSH_DEBUG_BREAKPOINT_ENGINE."""
    return isinstance(x, str) and x in CANONIC_BREAKPOINT_ENGINES


def to_breakpoint_engine(x):
    """Convert user input to value of $XONSH_DEBUG_BREAKPOINT_ENGINE."""
    y = str(x).casefold()
    if y not in CANONIC_BREAKPOINT_ENGINES:
        warnings.warn(
            f"'{x}' is not valid for $XONSH_DEBUG_BREAKPOINT_ENGINE, "
            f"must be one of {sorted(CANONIC_BREAKPOINT_ENGINES)}. Using 'auto'.",
            RuntimeWarning,
            stacklevel=2,
        )
        y = "auto"
    return y


class XonshDebug:
    """Debug helpers for a running xonsh session.

    Accessible from xonsh code as ``@.debug``.

    Examples
    --------
    Drop into the default debugger at the call site::

        @.debug.breakpoint()

    Force a specific engine::

        @.debug.breakpoint(engine='ipdb')
    """

    AUTO_ENGINES = ("pdbp", "ipdb", "pdb")

    def breakpoint(self, engine: str = "auto", *, frame=None) -> None:
        """Drop into a debugger at the caller's frame.

        Parameters
        ----------
        engine : str, optional
            Which debugger to use. One of ``"auto"``, ``"pdbp"``,
            ``"ipdb"``, ``"pdb"``, ``"execer"``, or ``"eval"``. When
            ``"auto"`` (the default), ``$XONSH_DEBUG_BREAKPOINT_ENGINE``
            is consulted first; if it is also ``"auto"``, the first
            available engine is chosen in priority order: ``pdbp`` ->
            ``ipdb`` -> ``pdb`` -> ``execer`` (if a xonsh session is
            loaded) -> ``eval`` (always).

            The ``"execer"`` engine starts a REPL at the caller's
            frame, backed by the session's :class:`~xonsh.execer.Execer`
            (prompt ``"execer> "``) — xonsh syntax such as
            subprocesses, env lookups, and aliases is available.
            Raises :class:`RuntimeError` if no execer is attached.

            The ``"eval"`` engine starts a REPL at the caller's frame
            using plain Python ``eval``/``exec`` (prompt
            ``"(xdebug) "``) — it has no dependency on a xonsh session.

            In both REPLs, type ``c``/``cont``/``continue`` (or hit
            EOF/Ctrl-C) to resume execution, or ``exit``/``quit``/``q``
            to abort — the latter raises :class:`XonshDebugQuit`.
        frame : types.FrameType, optional
            Frame at which the debugger should stop. Mirrors
            ``pdbp.set_trace(frame=...)``. When ``None`` (the default),
            the immediate caller's frame is used. Pass an explicit
            frame from a wrapper helper to relocate the stop site to
            the helper's caller (or any other frame on the stack)::

                def my_dev_helper():
                    @.debug.breakpoint(frame=sys._getframe().f_back)
        """
        __tracebackhide__: bool = True  # hidden from pdbp/pytest frame walks
        if frame is None:
            frame = sys._getframe(1)
        try:
            self._break_at(frame, engine)
        finally:
            # Break the reference to the frame so locals are not
            # pinned any longer than necessary.
            del frame

    _HINTS = {
        "pdb": "[xonsh-debug] pdb: 'c' continue | 'q' quit",
        "ipdb": "[xonsh-debug] ipdb: 'c' continue | 'q' quit",
        "pdbp": "[xonsh-debug] pdbp: 'c' continue | 'q' quit",
        "execer": (
            "[xonsh-debug] execer REPL: 'c'/'continue' resume | 'q'/'quit'/'exit' abort"
        ),
        "eval": (
            "[xonsh-debug] eval REPL: 'c'/'continue' resume | 'q'/'quit'/'exit' abort"
        ),
    }

    def _break_at(self, frame, engine: str) -> None:
        __tracebackhide__: bool = True
        resolved = self._resolve_engine(engine)
        print(f"BREAKPOINT WITH {resolved!r}")
        print(self._HINTS[resolved])
        if resolved == "execer":
            self._execer_repl(frame)
        elif resolved == "eval":
            self._eval_repl(frame)
        else:
            self._start_debugger(resolved, frame)

    def replace_builtin_breakpoint(self, engine: str = "auto") -> None:
        """Route Python's builtin ``breakpoint()`` through this debugger.

        After this call, any ``breakpoint()`` or PEP 553 breakpoint
        statement — whether in xonsh code or in plain Python modules
        loaded from xonsh — drops into the engine chosen by this
        object. Call it from ``~/.xonshrc`` to make the integration
        persistent.

        Parameters
        ----------
        engine : str, optional
            Engine to use when the builtin ``breakpoint()`` fires.
            Accepts the same values as :meth:`breakpoint`. Captured by
            the installed hook; call again with a different value to
            change it, or assign ``sys.breakpointhook =
            sys.__breakpointhook__`` to restore the default.
        """

        def hook(*_args, frame=None, **_kwargs):
            __tracebackhide__: bool = True
            # Python's breakpoint() builtin is a C function, so
            # sys._getframe(1) from inside this hook is the user's
            # Python frame that invoked breakpoint(). If the caller
            # forwarded an explicit ``frame=`` (PEP 553 forwards all
            # kwargs to sys.breakpointhook), honour it.
            if frame is None:
                frame = sys._getframe(1)
            try:
                self._break_at(frame, engine)
            finally:
                del frame

        sys.breakpointhook = hook

    READLINE_ENGINES = ("pdbp", "ipdb", "pdb")

    def _resolve_engine(self, engine: str) -> str:
        if engine not in CANONIC_BREAKPOINT_ENGINES:
            raise ValueError(
                f"Unknown breakpoint engine {engine!r}. "
                f"Must be one of {sorted(CANONIC_BREAKPOINT_ENGINES)}."
            )
        if engine == "auto":
            env_engine = self._env_default()
            if env_engine != "auto":
                engine = env_engine
        if engine != "auto":
            if engine in self.READLINE_ENGINES and not self._is_main_thread():
                warnings.warn(
                    f"Debug breakpoint (engine={engine!r}) was invoked from "
                    "a non-main thread (e.g. inside a callable alias). "
                    "External debuggers cannot tab-complete in this context "
                    "due to a CPython readline limitation. Use "
                    "engine='execer' or engine='eval' for a working REPL.",
                    UserWarning,
                    stacklevel=2,
                )
            return engine
        # Auto-walk: in worker threads readline-based engines lose tab
        # completion (CPython only wires readline into the main thread),
        # so skip straight to a session-aware REPL.
        if not self._is_main_thread():
            return "execer" if self._has_execer() else "eval"
        for name in self.AUTO_ENGINES:
            if importlib.util.find_spec(name) is not None:
                return name
        # No external debugger available — prefer execer if we have a
        # session, else fall through to the plain-Python eval REPL.
        if self._has_execer():
            return "execer"
        return "eval"

    @staticmethod
    def _is_main_thread() -> bool:
        return threading.current_thread() is threading.main_thread()

    @staticmethod
    def _has_execer() -> bool:
        xsh = getattr(builtins, "__xonsh__", None)
        return getattr(xsh, "execer", None) is not None

    @staticmethod
    def _env_default() -> str:
        xsh = getattr(builtins, "__xonsh__", None)
        env = getattr(xsh, "env", None) if xsh is not None else None
        if env is None:
            return "auto"
        value = env.get("XONSH_DEBUG_BREAKPOINT_ENGINE", "auto")
        if value not in CANONIC_BREAKPOINT_ENGINES:
            return "auto"
        return value

    @staticmethod
    def _start_debugger(name: str, frame) -> None:
        __tracebackhide__: bool = True
        module = importlib.import_module(name)
        if name == "pdb":
            module.Pdb().set_trace(frame)
        elif name == "ipdb":
            module.set_trace(frame=frame)
        elif name == "pdbp":
            module.set_trace(frame=frame)
        else:
            raise ValueError(f"Unsupported debugger engine: {name!r}")

    _CONTINUE_COMMANDS = ("c", "cont", "continue")
    _ABORT_COMMANDS = ("exit", "quit", "q")

    def _execer_repl(self, frame) -> None:
        """REPL that dispatches each line through the session's Execer."""
        xsh = getattr(builtins, "__xonsh__", None)
        execer = getattr(xsh, "execer", None) if xsh is not None else None
        if execer is None:
            raise RuntimeError(
                "The 'execer' breakpoint engine requires an active xonsh "
                "session with an Execer attached. Use engine='eval' for a "
                "plain-Python REPL, or run inside a xonsh session."
            )
        self._interactive_repl(
            frame,
            banner_backend="execer",
            prompt="execer> ",
            runner=lambda line, g, loc: execer.exec(
                line, mode="single", glbs=g, locs=loc
            ),
        )

    def _eval_repl(self, frame) -> None:
        """REPL that evaluates each line with plain Python eval/exec."""
        self._interactive_repl(
            frame,
            banner_backend="python",
            prompt="(xdebug) ",
            runner=self._python_eval,
        )

    def _interactive_repl(
        self, frame, *, banner_backend: str, prompt: str, runner
    ) -> None:
        location = f"{frame.f_code.co_filename}:{frame.f_lineno}"
        print(f"[xonsh-debug] {banner_backend} REPL at {location}")
        globs, locs = frame.f_globals, frame.f_locals
        while True:
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                # EOF / Ctrl-C behave like 'continue' — least destructive.
                print()
                return
            stripped = line.strip()
            if stripped in self._CONTINUE_COMMANDS:
                return
            if stripped in self._ABORT_COMMANDS:
                raise XonshDebugQuit(
                    f"aborted from {banner_backend} REPL at {location}"
                )
            if not stripped:
                continue
            try:
                runner(line, globs, locs)
            except (SystemExit, XonshDebugQuit):
                raise
            except BaseException:
                traceback.print_exc()

    @staticmethod
    def _python_eval(line: str, globs, locs) -> None:
        try:
            result = eval(line, globs, locs)
        except SyntaxError:
            exec(line, globs, locs)
            return
        if result is not None:
            print(repr(result))
