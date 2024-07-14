"""The xonsh built-ins.

Note that this module is named 'built_ins' so as not to be confused with the
special Python builtins module.
"""

import atexit
import builtins
import collections.abc as cabc
import contextlib
import inspect
import itertools
import os
import pathlib
import re
import signal
import sys
import types
import warnings
from ast import AST

from xonsh.lib.inspectors import Inspector
from xonsh.lib.lazyasd import lazyobject
from xonsh.platform import ON_POSIX
from xonsh.tools import (
    XonshCalledProcessError,
    XonshError,
    expand_path,
    globpath,
    print_color,
)

INSPECTOR = Inspector()

warnings.filterwarnings("once", category=DeprecationWarning)


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
    prev_signal_handler = signal.getsignal(sig)

    def new_signal_handler(s=None, frame=None):
        f(s, frame)
        signal.signal(sig, prev_signal_handler)
        if sig != 0:
            """
            There is no immediate exiting here.
            The ``sys.exit()`` function raises a ``SystemExit`` exception.
            This exception must be caught and processed in the upstream code.
            """
            sys.exit(sig)

    signal.signal(sig, new_signal_handler)


def helper(x, name=""):
    """Prints help about, and then returns that variable."""
    name = name or getattr(x, "__name__", "")
    INSPECTOR.pinfo(x, oname=name, detail_level=0)
    return x


def superhelper(x, name=""):
    """Prints help about, and then returns that variable."""
    name = name or getattr(x, "__name__", "")
    INSPECTOR.pinfo(x, oname=name, detail_level=1)
    return x


def reglob(path, parts=None, i=None):
    """Regular expression-based globbing."""
    if parts is None:
        path = os.path.normpath(path)
        drive, tail = os.path.splitdrive(path)
        parts = tail.split(os.sep)
        d = os.sep if os.path.isabs(path) else "."
        d = os.path.join(drive, d)
        return reglob(d, parts, i=0)
    base = subdir = path
    if i == 0:
        if not os.path.isabs(base):
            base = ""
        elif len(parts) > 1:
            i += 1
    try:
        regex = re.compile(parts[i])
    except Exception as e:
        if isinstance(e, re.error) and str(e) == "nothing to repeat at position 0":
            raise XonshError(
                "Consider adding a leading '.' to your glob regex pattern."
            ) from e
        else:
            raise e

    files = os.listdir(subdir)
    files.sort()
    paths = []
    i1 = i + 1
    if i1 == len(parts):
        for f in files:
            p = os.path.join(base, f)
            if regex.fullmatch(f) is not None:
                paths.append(p)
    else:
        for f in files:
            p = os.path.join(base, f)
            if regex.fullmatch(f) is None or not os.path.isdir(p):
                continue
            paths += reglob(p, parts=parts, i=i1)
    return paths


def path_literal(s):
    s = expand_path(s)
    return pathlib.Path(s)


def regexsearch(s):
    s = expand_path(s)
    return reglob(s)


def globsearch(s):
    csc = XSH.env.get("CASE_SENSITIVE_COMPLETIONS")
    glob_sorted = XSH.env.get("GLOB_SORTED")
    dotglob = XSH.env.get("DOTGLOB")
    return globpath(
        s,
        ignore_case=(not csc),
        return_empty=True,
        sort_result=glob_sorted,
        include_dotfiles=dotglob,
    )


def pathsearch(func, s, pymode=False, pathobj=False):
    """
    Takes a string and returns a list of file paths that match (regex, glob,
    or arbitrary search function). If pathobj=True, the return is a list of
    pathlib.Path objects instead of strings.
    """
    if not callable(func) or len(inspect.signature(func).parameters) != 1:
        error = "%r is not a known path search function"
        raise XonshError(error % func)
    o = func(s)
    if pathobj and pymode:
        o = list(map(pathlib.Path, o))
    no_match = [] if pymode else [s]
    return o if len(o) != 0 else no_match


def subproc_captured_stdout(*cmds, envs=None):
    """Runs a subprocess, capturing the output. Returns the stdout
    that was produced as a str or list based on ``$XONSH_SUBPROC_OUTPUT_FORMAT``.
    """

    import xonsh.procs.specs

    return xonsh.procs.specs.run_subproc(cmds, captured="stdout", envs=envs)


def subproc_captured_inject(*cmds, envs=None):
    """Runs a subprocess, capturing the output. Returns a list of
    whitespace-separated strings of the stdout that was produced.
    The string is split using xonsh's lexer, rather than Python's str.split()
    or shlex.split().
    """
    import xonsh.procs.specs

    o = xonsh.procs.specs.run_subproc(cmds, captured="object", envs=envs)
    o.end()
    toks = []
    for line in o:
        line = line.rstrip(os.linesep)
        toks.extend(XSH.execer.parser.lexer.split(line))
    return toks


def subproc_captured_object(*cmds, envs=None):
    """
    Runs a subprocess, capturing the output. Returns an instance of
    CommandPipeline representing the completed command.
    """
    import xonsh.procs.specs

    return xonsh.procs.specs.run_subproc(cmds, captured="object", envs=envs)


def subproc_captured_hiddenobject(*cmds, envs=None):
    """Runs a subprocess, capturing the output. Returns an instance of
    HiddenCommandPipeline representing the completed command.
    """
    import xonsh.procs.specs

    return xonsh.procs.specs.run_subproc(cmds, captured="hiddenobject", envs=envs)


def subproc_uncaptured(*cmds, envs=None):
    """Runs a subprocess, without capturing the output. Returns the stdout
    that was produced as a str.
    """
    import xonsh.procs.specs

    return xonsh.procs.specs.run_subproc(cmds, captured=False, envs=envs)


def ensure_list_of_strs(x):
    """Ensures that x is a list of strings."""
    if isinstance(x, str):
        rtn = [x]
    elif isinstance(x, cabc.Sequence):
        rtn = [i if isinstance(i, str) else str(i) for i in x]
    else:
        rtn = [str(x)]
    return rtn


def ensure_str_or_callable(x):
    """Ensures that x is single string or function."""
    if isinstance(x, str) or callable(x):
        return x
    if isinstance(x, bytes):
        # ``os.fsdecode`` decodes using "surrogateescape" on linux and "strict" on windows.
        # This is used to decode bytes for interfacing with the os, notably for command line arguments.
        # See https://www.python.org/dev/peps/pep-0383/#specification
        return os.fsdecode(x)
    return str(x)


def list_of_strs_or_callables(x):
    """
    Ensures that x is a list of strings or functions.
    This is called when using the ``@()`` operator to expand it's content.
    """
    if isinstance(x, (str, bytes)) or callable(x):
        rtn = [ensure_str_or_callable(x)]
    elif isinstance(x, cabc.Iterable):
        rtn = list(map(ensure_str_or_callable, x))
    else:
        rtn = [ensure_str_or_callable(x)]
    return rtn


def list_of_list_of_strs_outer_product(x):
    """Takes an outer product of a list of strings"""
    lolos = map(ensure_list_of_strs, x)
    rtn = []
    for los in itertools.product(*lolos):
        s = "".join(los)
        if "*" in s:
            rtn.extend(XSH.glob(s))
        else:
            rtn.append(XSH.expand_path(s))
    return rtn


def eval_fstring_field(field):
    """Evaluates the argument in Xonsh context."""
    res = XSH.execer.eval(
        field[0].strip(), glbs=globals(), locs=XSH.ctx, filename=field[1]
    )
    return res


@lazyobject
def MACRO_FLAG_KINDS():
    return {
        "s": str,
        "str": str,
        "string": str,
        "a": AST,
        "ast": AST,
        "c": types.CodeType,
        "code": types.CodeType,
        "compile": types.CodeType,
        "v": eval,
        "eval": eval,
        "x": exec,
        "exec": exec,
        "t": type,
        "type": type,
    }


def _convert_kind_flag(x):
    """Puts a kind flag (string) a canonical form."""
    x = x.lower()
    kind = MACRO_FLAG_KINDS.get(x, None)
    if kind is None:
        raise TypeError(f"{x!r} not a recognized macro type.")
    return kind


def convert_macro_arg(raw_arg, kind, glbs, locs, *, name="<arg>", macroname="<macro>"):
    """Converts a string macro argument based on the requested kind.

    Parameters
    ----------
    raw_arg : str
        The str representation of the macro argument.
    kind : object
        A flag or type representing how to convert the argument.
    glbs : Mapping
        The globals from the call site.
    locs : Mapping or None
        The locals from the call site.
    name : str, optional
        The macro argument name.
    macroname : str, optional
        The name of the macro itself.

    Returns
    -------
    The converted argument.
    """
    # munge kind and mode to start
    mode = None
    if isinstance(kind, cabc.Sequence) and not isinstance(kind, str):
        # have (kind, mode) tuple
        kind, mode = kind
    if isinstance(kind, str):
        kind = _convert_kind_flag(kind)
    if kind is str or kind is None:
        return raw_arg  # short circuit since there is nothing else to do
    # select from kind and convert
    execer = XSH.execer
    filename = macroname + "(" + name + ")"
    if kind is AST:
        ctx = set(dir(builtins)) | set(glbs.keys())
        if locs is not None:
            ctx |= set(locs.keys())
        mode = mode or "eval"
        if mode != "eval" and not raw_arg.endswith("\n"):
            raw_arg += "\n"
        arg = execer.parse(raw_arg, ctx, mode=mode, filename=filename)
    elif kind is types.CodeType or kind is compile:  # NOQA
        mode = mode or "eval"
        arg = execer.compile(
            raw_arg, mode=mode, glbs=glbs, locs=locs, filename=filename
        )
    elif kind is eval:
        arg = execer.eval(raw_arg, glbs=glbs, locs=locs, filename=filename)
    elif kind is exec:
        mode = mode or "exec"
        if not raw_arg.endswith("\n"):
            raw_arg += "\n"
        arg = execer.exec(raw_arg, mode=mode, glbs=glbs, locs=locs, filename=filename)
    elif kind is type:
        arg = type(execer.eval(raw_arg, glbs=glbs, locs=locs, filename=filename))
    else:
        msg = "kind={0!r} and mode={1!r} was not recognized for macro " "argument {2!r}"
        raise TypeError(msg.format(kind, mode, name))
    return arg


@contextlib.contextmanager
def in_macro_call(f, glbs, locs):
    """Attaches macro globals and locals temporarily to function as a
    context manager.

    Parameters
    ----------
    f : callable object
        The function that is called as ``f(*args)``.
    glbs : Mapping
        The globals from the call site.
    locs : Mapping or None
        The locals from the call site.
    """
    prev_glbs = getattr(f, "macro_globals", None)
    prev_locs = getattr(f, "macro_locals", None)
    f.macro_globals = glbs
    f.macro_locals = locs
    yield
    if prev_glbs is None:
        del f.macro_globals
    else:
        f.macro_globals = prev_glbs
    if prev_locs is None:
        del f.macro_locals
    else:
        f.macro_locals = prev_locs


def call_macro(f, raw_args, glbs, locs):
    """Calls a function as a macro, returning its result.

    Parameters
    ----------
    f : callable object
        The function that is called as ``f(*args)``.
    raw_args : tuple of str
        The str representation of arguments of that were passed into the
        macro. These strings will be parsed, compiled, evaled, or left as
        a string depending on the annotations of f.
    glbs : Mapping
        The globals from the call site.
    locs : Mapping or None
        The locals from the call site.
    """
    sig = inspect.signature(f)
    empty = inspect.Parameter.empty
    macroname = f.__name__
    i = 0
    args = []
    for (key, param), raw_arg in zip(sig.parameters.items(), raw_args):
        i += 1
        if raw_arg == "*":
            break
        kind = param.annotation
        if kind is empty or kind is None:
            kind = str
        arg = convert_macro_arg(
            raw_arg, kind, glbs, locs, name=key, macroname=macroname
        )
        args.append(arg)
    reg_args, kwargs = _eval_regular_args(raw_args[i:], glbs, locs)
    args += reg_args
    with in_macro_call(f, glbs, locs):
        rtn = f(*args, **kwargs)
    return rtn


@lazyobject
def KWARG_RE():
    return re.compile(r"([A-Za-z_]\w*=|\*\*)")


def _starts_as_arg(s):
    """Tests if a string starts as a non-kwarg string would."""
    return KWARG_RE.match(s) is None


def _eval_regular_args(raw_args, glbs, locs):
    if not raw_args:
        return [], {}
    arglist = list(itertools.takewhile(_starts_as_arg, raw_args))
    kwarglist = raw_args[len(arglist) :]
    execer = XSH.execer
    if not arglist:
        args = arglist
        kwargstr = "dict({})".format(", ".join(kwarglist))
        kwargs = execer.eval(kwargstr, glbs=glbs, locs=locs)
    elif not kwarglist:
        argstr = "({},)".format(", ".join(arglist))
        args = execer.eval(argstr, glbs=glbs, locs=locs)
        kwargs = {}
    else:
        argstr = "({},)".format(", ".join(arglist))
        kwargstr = "dict({})".format(", ".join(kwarglist))
        both = f"({argstr}, {kwargstr})"
        args, kwargs = execer.eval(both, glbs=glbs, locs=locs)
    return args, kwargs


def enter_macro(obj, raw_block, glbs, locs):
    """Prepares to enter a context manager macro by attaching the contents
    of the macro block, globals, and locals to the object. These modifications
    are made in-place and the original object is returned.

    Parameters
    ----------
    obj : context manager
        The object that is about to be entered via a with-statement.
    raw_block : str
        The str of the block that is the context body.
        This string will be parsed, compiled, evaled, or left as
        a string depending on the return annotation of obj.__enter__.
    glbs : Mapping
        The globals from the context site.
    locs : Mapping or None
        The locals from the context site.

    Returns
    -------
    obj : context manager
        The same context manager but with the new macro information applied.
    """
    # recurse down sequences
    if isinstance(obj, cabc.Sequence):
        for x in obj:
            enter_macro(x, raw_block, glbs, locs)
        return obj
    # convert block as needed
    kind = getattr(obj, "__xonsh_block__", str)
    macroname = getattr(obj, "__name__", "<context>")
    block = convert_macro_arg(
        raw_block, kind, glbs, locs, name="<with!>", macroname=macroname
    )
    # attach attrs
    obj.macro_globals = glbs
    obj.macro_locals = locs
    obj.macro_block = block
    return obj


@contextlib.contextmanager
def xonsh_builtins(execer=None):
    """A context manager for using the xonsh builtins only in a limited
    scope. Likely useful in testing.
    """
    XSH.load(execer=execer)
    yield
    XSH.unload()


class InlineImporter:
    """Inline importer allows to import and use module attribute or function in one line."""

    def __getattr__(self, name):
        if name.startswith("__"):
            return getattr(super(), name)
        return __import__(name)


class XonshSession:
    """All components defining a xonsh session."""

    def __init__(self):
        """
        Attributes
        ----------
        exit: int or None
            Session attribute. In case of integer value it signals xonsh to exit
            with returning this value as exit code.
        """
        self.execer = None
        self.ctx = {}
        self.builtins_loaded = False
        self.history = None
        self.shell = None
        self.env = None
        self.imp = InlineImporter()
        self.rc_files = None

        # AST-invoked functions
        self.help = helper
        self.superhelp = superhelper
        self.pathsearch = pathsearch
        self.globsearch = globsearch
        self.regexsearch = regexsearch
        self.glob = globpath
        self.expand_path = expand_path

        self.subproc_captured_stdout = subproc_captured_stdout
        self.subproc_captured_inject = subproc_captured_inject
        self.subproc_captured_object = subproc_captured_object
        self.subproc_captured_hiddenobject = subproc_captured_hiddenobject
        self.subproc_uncaptured = subproc_uncaptured
        self.call_macro = call_macro
        self.enter_macro = enter_macro
        self.path_literal = path_literal

        self.list_of_strs_or_callables = list_of_strs_or_callables
        self.list_of_list_of_strs_outer_product = list_of_list_of_strs_outer_product
        self.eval_fstring_field = eval_fstring_field

        # Session attributes
        self.exit = None
        self.stdout_uncaptured = None
        self.stderr_uncaptured = None
        self._py_exit = None
        self._py_quit = None
        self.commands_cache = None
        self.modules_cache = None
        self.all_jobs = None
        self._completers = None
        self.builtins = None
        self._initial_builtin_names = None
        self.last = None  # Last executed CommandPipeline.

    @property
    def aliases(self):
        if self.commands_cache is None:
            return
        return self.commands_cache.aliases

    @property
    def completers(self):
        """Returns a list of all available completers. Init when first accessing the attribute"""
        if self._completers is None:
            from xonsh.completers.init import default_completers

            self._completers = default_completers(self.commands_cache)
        return self._completers

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

    def load(self, execer=None, ctx=None, inherit_env=True, **kwargs):
        """Loads the session with default values.

        Parameters
        ----------
        execer : Execer, optional
            Xonsh execution object, may be None to start
        ctx : Mapping, optional
            Context to start xonsh session with.
        inherit_env : bool
            If ``True``: inherit environment variables from ``os.environ``.
            If ``False``: use default values for environment variables and
            set ``$XONSH_ENV_INHERITED = False``.
        """
        from xonsh.commands_cache import CommandsCache
        from xonsh.environ import Env, default_env

        if not hasattr(builtins, "__xonsh__"):
            builtins.__xonsh__ = self
        if ctx is not None:
            self.ctx = ctx

        if "env" in kwargs:
            self.env = kwargs.pop("env")
        elif inherit_env:
            self.env = Env(default_env())
        else:
            self.env = Env({"XONSH_ENV_INHERITED": False})

        self.exit = None
        self.stdout_uncaptured = None
        self.stderr_uncaptured = None

        self._disable_python_exit()

        self.execer = execer
        self.modules_cache = {}
        self.all_jobs = {}

        self.builtins = get_default_builtins(execer)
        self._initial_builtin_names = frozenset(vars(self.builtins))

        aliases_given = kwargs.pop("aliases", None)
        for attr, value in kwargs.items():
            if hasattr(self, attr):
                setattr(self, attr, value)
        self.commands_cache = (
            kwargs.pop("commands_cache")
            if "commands_cache" in kwargs
            else CommandsCache(self.env, aliases_given)
        )
        self.link_builtins()
        self.builtins_loaded = True

        def flush_on_exit(s=None, f=None):
            if self.history is not None:
                self.history.flush(at_exit=True)

        atexit.register(flush_on_exit)

        # Add one-shot handler for exit
        for sig in AT_EXIT_SIGNALS:
            resetting_signal_handle(sig, flush_on_exit)

    def link_builtins(self):
        # public built-ins
        for refname in self._initial_builtin_names:
            objname = f"__xonsh__.builtins.{refname}"
            proxy = DynamicAccessProxy(refname, objname)
            setattr(builtins, refname, proxy)

        # sneak the path search functions into the aliases
        # Need this inline/lazy import here since we use locate_binary that
        # relies on __xonsh__.env in default aliases
        builtins.default_aliases = builtins.aliases = self.aliases

    def unlink_builtins(self):
        for name in self._initial_builtin_names:
            if hasattr(builtins, name):
                delattr(builtins, name)

    def unload(self):
        if not hasattr(builtins, "__xonsh__"):
            self.builtins_loaded = False
            return

        if hasattr(self.env, "undo_replace_env"):
            self.env.undo_replace_env()

        self._restore_python_exit()

        if not self.builtins_loaded:
            return

        if self.history is not None:
            self.history.flush(at_exit=True)

        self.unlink_builtins()
        delattr(builtins, "__xonsh__")
        self.builtins_loaded = False
        self._completers = None


def get_default_builtins(execer=None):
    from xonsh.events import events

    return types.SimpleNamespace(
        XonshError=XonshError,
        XonshCalledProcessError=XonshCalledProcessError,
        evalx=None if execer is None else execer.eval,
        execx=None if execer is None else execer.exec,
        compilex=None if execer is None else execer.compile,
        events=events,
        print_color=print_color,
        printx=print_color,
    )


class DynamicAccessProxy:
    """Proxies access dynamically."""

    def __init__(self, refname, objname):
        """
        Parameters
        ----------
        refname : str
            '.'-separated string that represents the new, reference name that
            the user will access.
        objname : str
            '.'-separated string that represents the name where the target
            object actually lives that refname points to.
        """
        super().__setattr__("refname", refname)
        super().__setattr__("objname", objname)

    @property
    def obj(self):
        """Dynamically grabs object"""
        names = self.objname.split(".")
        obj = builtins
        for name in names:
            obj = getattr(obj, name)
        return obj

    def __getattr__(self, name):
        return getattr(self.obj, name)

    def __setattr__(self, name, value):
        return super().__setattr__(self.obj, name, value)

    def __delattr__(self, name):
        return delattr(self.obj, name)

    def __getitem__(self, item):
        return self.obj.__getitem__(item)

    def __setitem__(self, item, value):
        return self.obj.__setitem__(item, value)

    def __delitem__(self, item):
        del self.obj[item]

    def __call__(self, *args, **kwargs):
        return self.obj.__call__(*args, **kwargs)

    def __dir__(self):
        return self.obj.__dir__()


# singleton
XSH = XonshSession()
