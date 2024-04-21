"""Aliases for the xonsh shell."""

import collections.abc as cabc
import inspect
import os
import re
import shutil
import sys
import types
import typing as tp

from xonsh.built_ins import XSH
from xonsh.dirstack import cd, dirs, popd, pushd
from xonsh.environ import locate_binary
from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers.ast import isexpression
from xonsh.platform import (
    IN_APPIMAGE,
    ON_ANACONDA,
    ON_DARWIN,
    ON_DRAGONFLY,
    ON_FREEBSD,
    ON_NETBSD,
    ON_OPENBSD,
    ON_WINDOWS,
)
from xonsh.procs.jobs import bg, clean_jobs, disown, fg, jobs
from xonsh.procs.specs import SpecAttrModifierAlias, SpecModifierAlias
from xonsh.timings import timeit_alias
from xonsh.tools import (
    ALIAS_KWARG_NAMES,
    XonshError,
    _get_cwd,
    strip_simple_quotes,
    to_repr_pretty_,
)
from xonsh.xontribs import xontribs_main


@lazyobject
def EXEC_ALIAS_RE():
    return re.compile(r"@\(|\$\(|!\(|\$\[|!\[|\&\&|\|\||\s+and\s+|\s+or\s+|[>|<]")


class FuncAlias:
    """Provides a callable alias for xonsh commands."""

    attributes_show = ["__xonsh_threadable__", "__xonsh_capturable__"]
    attributes_inherit = attributes_show + ["__doc__"]

    def __init__(self, name, func=None):
        self.__name__ = self.name = name
        self.func = func
        for attr in self.attributes_inherit:
            if (val := getattr(func, attr, None)) is not None:
                self.__setattr__(attr, val)

    def __repr__(self):
        r = {"name": self.name, "func": self.func.__name__}
        r |= {
            attr: val
            for attr in self.attributes_show
            if (val := getattr(self, attr, None)) is not None
        }
        return f"FuncAlias({repr(r)})"

    def __call__(
        self, args=None, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        func_args = [args, stdin, stdout, stderr, spec, stack][
            : len(inspect.signature(self.func).parameters)
        ]
        return self.func(*func_args)


class Aliases(cabc.MutableMapping):
    """Represents a location to hold and look up aliases."""

    def __init__(self, *args, **kwargs):
        self._raw = {}
        self.update(*args, **kwargs)

    @staticmethod
    def _get_func_name(func):
        name = func.__name__

        # Strip leading underscore
        if name.startswith("_"):
            name = name[1:]
        return name

    def _register(self, func, name="", dash_case=True):
        name = name or self._get_func_name(func)

        if dash_case:
            name = name.replace("_", "-")

        self[name] = func
        return func

    @tp.overload
    def register(self, func: types.FunctionType) -> types.FunctionType:
        """simple usage"""

    @tp.overload
    def register(
        self, name: str, *, dash_case: bool = True
    ) -> tp.Callable[[types.FunctionType], types.FunctionType]: ...

    def register(self, func_or_name, name=None, dash_case=True):
        """Decorator to register the given function by name."""

        if isinstance(func_or_name, types.FunctionType):
            return self._register(func_or_name, name, dash_case)

        def wrapper(func):
            return self._register(func, func_or_name, dash_case)

        return wrapper

    def get(self, key, default=None, spec_modifiers=None):
        """Returns the (possibly modified) value. If the key is not present,
        then `default` is returned.
        If the value is callable, it is returned without modification. If it
        is an iterable of strings it will be evaluated recursively to expand
        other aliases, resulting in a new list or a "partially applied"
        callable.
        """
        spec_modifiers = spec_modifiers if spec_modifiers is not None else []
        val = self._raw.get(key)
        if val is None:
            return default
        elif isinstance(val, cabc.Iterable) or callable(val):
            return self.eval_alias(
                val, seen_tokens={key}, spec_modifiers=spec_modifiers
            )
        else:
            msg = "alias of {!r} has an inappropriate type: {!r}"
            raise TypeError(msg.format(key, val))

    def eval_alias(
        self, value, seen_tokens=frozenset(), acc_args=(), spec_modifiers=None
    ):
        """
        "Evaluates" the alias ``value``, by recursively looking up the leftmost
        token and "expanding" if it's also an alias.

        A value like ``["cmd", "arg"]`` might transform like this:
        ``> ["cmd", "arg"] -> ["ls", "-al", "arg"] -> callable()``
        where ``cmd=ls -al`` and ``ls`` is an alias with its value being a
        callable.  The resulting callable will be "partially applied" with
        ``["-al", "arg"]``.
        """
        spec_modifiers = spec_modifiers if spec_modifiers is not None else []
        # Beware of mutability: default values for keyword args are evaluated
        # only once.
        if (
            isinstance(value, cabc.Iterable)
            and hasattr(value, "__len__")
            and len(value) > 1
            and (isinstance(mod := self._raw.get(str(value[0])), SpecModifierAlias))
        ):
            spec_modifiers.append(mod)
            value = value[1:]

        if callable(value):
            return partial_eval_alias(value, acc_args=acc_args)
        else:
            expand_path = XSH.expand_path
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
                return self.eval_alias(
                    self._raw[token],
                    seen_tokens,
                    acc_args,
                    spec_modifiers=spec_modifiers,
                )

    def expand_alias(self, line: str, cursor_index: int) -> str:
        """Expands any aliases present in line if alias does not point to a
        builtin function and if alias is only a single command.
        The command won't be expanded if the cursor's inside/behind it.
        """
        word = (line.split(maxsplit=1) or [""])[0]
        if word in XSH.aliases and isinstance(self.get(word), cabc.Sequence):  # type: ignore
            word_idx = line.find(word)
            word_edge = word_idx + len(word)
            if cursor_index > word_edge:
                # the cursor isn't inside/behind the word
                expansion = " ".join(self.get(word))
                line = line[:word_idx] + expansion + line[word_edge:]
        return line

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self._raw[key]

    def __setitem__(self, key, val):
        if isinstance(val, str):
            f = "<exec-alias:" + key + ">"
            if EXEC_ALIAS_RE.search(val) is not None:
                # We have a sub-command (e.g. $(cmd)) or IO redirect (e.g. >>)
                self._raw[key] = ExecAlias(val, filename=f)
            elif isexpression(val):
                # expansion substitution
                lexer = XSH.execer.parser.lexer
                self._raw[key] = list(map(strip_simple_quotes, lexer.split(val)))
            else:
                # need to exec alias
                self._raw[key] = ExecAlias(val, filename=f)
        elif isinstance(val, types.FunctionType):
            self._raw[key] = FuncAlias(key, val)
        else:
            self._raw[key] = val

    def _common_or(self, other):
        new_dict = self._raw.copy()
        for key in dict(other):
            new_dict[key] = other[key]
        return Aliases(new_dict)

    def __or__(self, other):
        return self._common_or(other)

    def __ror__(self, other):
        return self._common_or(other)

    def __ior__(self, other):
        for key in dict(other):
            self[key] = other[key]
        return self

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
        return f"{self.__class__.__module__}.{self.__class__.__name__}({self._raw})"

    _repr_pretty_ = to_repr_pretty_


class ExecAlias:
    """Provides an exec alias for xonsh source code."""

    __slots__ = ("src", "filename")

    def __init__(self, src, filename="<exec-alias>"):
        """
        Parameters
        ----------
        src : str
            Source code that will be
        """
        self.src = src
        self.filename = filename

    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        execer = XSH.execer
        frame = stack[0][0]  # execute as though we are at the call site

        alias_args = {"args": args}
        for i, a in enumerate(args):
            alias_args[f"arg{i}"] = a

        with XSH.env.swap(alias_args):
            execer.exec(
                self.src,
                glbs=frame.f_globals,
                locs=frame.f_locals,
                filename=self.filename,
            )
        if XSH.history is not None:
            return XSH.history.last_cmd_rtn

    def __repr__(self):
        return f"ExecAlias({self.src!r}, filename={self.filename!r})"


class LazyAlias:
    __slots__ = ("name", "_func")

    def __init__(self, name: str):
        """Represents a callable alias function

        Parameters
        ----------
        name
            module path and name of the alias function in the form of ``parent.module.name:func_name``
        """
        self.name = name
        self._func = None

    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        if self._func is None:
            import importlib

            path, func = self.name.rsplit(":", 1)
            module = importlib.import_module(path)
            self._func = getattr(module, func)

        from xonsh.cli_utils import _dispatch_func

        _dispatch_func(
            self._func,
            dict(
                args=args,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                spec=spec,
                stack=stack,
            ),
        )

    def __repr__(self):
        return f"LazyAlias({self.name})"


class PartialEvalAliasBase:
    """Partially evaluated alias."""

    def __init__(self, f, acc_args=()):
        """
        Parameters
        ----------
        f : callable
            A function to dispatch to.
        acc_args : sequence of strings, optional
            Additional arguments to prepent to the argument list passed in
            when the alias is called.
        """
        self.f = f
        self.acc_args = acc_args
        self.__name__ = getattr(f, "__name__", self.__class__.__name__)

    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin, stdout, stderr, spec, stack)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.f!r}, acc_args={self.acc_args!r})"


class PartialEvalAlias0(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        if args:
            msg = "callable alias {f!r} takes no arguments, but {args!f} provided. "
            msg += "Of these {acc_args!r} were partially applied."
            raise XonshError(msg.format(f=self.f, args=args, acc_args=self.acc_args))
        return self.f()


class PartialEvalAlias1(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args)


class PartialEvalAlias2(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin)


class PartialEvalAlias3(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin, stdout)


class PartialEvalAlias4(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin, stdout, stderr)


class PartialEvalAlias5(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin, stdout, stderr, spec)


class PartialEvalAlias6(PartialEvalAliasBase):
    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin, stdout, stderr, spec, stack)


PARTIAL_EVAL_ALIASES = (
    PartialEvalAlias0,
    PartialEvalAlias1,
    PartialEvalAlias2,
    PartialEvalAlias3,
    PartialEvalAlias4,
    PartialEvalAlias5,
    PartialEvalAlias6,
)


def partial_eval_alias(f, acc_args=()):
    """Dispatches the appropriate eval alias based on the number of args to the original callable alias
    and how many arguments to apply.
    """
    # no partial needed if no extra args
    if not acc_args:
        return f
    # need to dispatch
    numargs = 0
    for name, param in inspect.signature(f).parameters.items():
        if (
            param.kind == param.POSITIONAL_ONLY
            or param.kind == param.POSITIONAL_OR_KEYWORD
        ):
            numargs += 1
        elif name in ALIAS_KWARG_NAMES and param.kind == param.KEYWORD_ONLY:
            numargs += 1
    if numargs < 7:
        return PARTIAL_EVAL_ALIASES[numargs](f, acc_args=acc_args)
    else:
        e = "Expected proxy with 6 or fewer arguments for {}, not {}"
        raise XonshError(e.format(", ".join(ALIAS_KWARG_NAMES), numargs))


#
# Actual aliases below
#


def xonsh_exit(args, stdin=None):
    """Sends signal to exit shell."""
    if not clean_jobs():
        # Do not exit if jobs not cleaned up
        return None, None
    XSH.exit = True
    print()  # gimme a newline
    return None, None


def detect_xpip_alias():
    """
    Determines the correct invocation to get xonsh's pip
    """
    if not getattr(sys, "executable", None):
        return lambda args, stdin=None: (
            "",
            "Sorry, unable to run pip on your system (missing sys.executable)",
            1,
        )

    basecmd = [sys.executable, "-m", "pip"]
    try:
        if ON_WINDOWS:
            # XXX: Does windows have an installation mode that requires UAC?
            return basecmd
        elif IN_APPIMAGE:
            # In AppImage `sys.executable` is equal to path to xonsh.AppImage file and the real python executable is in $_
            return [
                XSH.env.get("_", "APPIMAGE_PYTHON_EXECUTABLE_NOT_FOUND"),
                "-m",
                "pip",
            ]
        elif not os.access(os.path.dirname(sys.executable), os.W_OK):
            return (
                sys.executable
                + " -m pip @(['install', '--user'] + $args[1:] if $args and $args[0] == 'install' else $args)"
            )
        else:
            return basecmd
    except Exception:
        # Something freaky happened, return something that'll probably work
        return basecmd


def make_default_aliases():
    """Creates a new default aliases dictionary."""
    xexec = LazyAlias("xonsh.xaliases.xsh:xexec")
    default_aliases = {
        "cd": cd,
        "pushd": pushd,
        "popd": popd,
        "dirs": dirs,
        "jobs": jobs,
        "fg": fg,
        "bg": bg,
        "disown": disown,
        "EOF": xonsh_exit,
        "exit": xonsh_exit,
        "quit": xonsh_exit,
        "exec": xexec,
        "xexec": xexec,
        "source": LazyAlias("xonsh.xaliases.source:source"),
        "source-zsh": LazyAlias("xonsh.xaliases.source_foreign:zsh"),
        "source-bash": LazyAlias("xonsh.xaliases.source_foreign:bash"),
        "source-cmd": LazyAlias("xonsh.xaliases.source_foreign:cmd"),
        "source-foreign": LazyAlias("xonsh.xaliases.source_foreign:alias"),
        "history": LazyAlias("xonsh.xaliases.history:alias"),
        "trace": LazyAlias("xonsh.tracer:tracermain"),
        "timeit": timeit_alias,
        "xonfig": LazyAlias("xonsh.xonfig:xonfig_main"),
        "scp-resume": ["rsync", "--partial", "-h", "--progress", "--rsh=ssh"],
        "showcmd": LazyAlias("xonsh.xaliases.xsh:showcmd"),
        "ipynb": ["jupyter", "notebook", "--no-browser"],
        "which": LazyAlias("xonsh.xoreutils.which:which"),
        "xontrib": xontribs_main,
        "completer": LazyAlias("xonsh.completers._aliases:completer_alias"),
        "xpip": detect_xpip_alias(),
        "xonsh-reset": LazyAlias("xonsh.xaliases.xsh:xonsh_reset"),
        "xthread": SpecAttrModifierAlias(
            {"threadable": True, "force_threadable": True},
            "Mark current command as threadable.",
        ),
        "xunthread": SpecAttrModifierAlias(
            {"threadable": False, "force_threadable": False},
            "Mark current command as unthreadable.",
        ),
    }
    if ON_WINDOWS:
        # Borrow builtin commands from cmd.exe.
        windows_cmd_aliases = {
            "cls",
            "copy",
            "del",
            "dir",
            "echo",
            "erase",
            "md",
            "mkdir",
            "mklink",
            "move",
            "rd",
            "ren",
            "rename",
            "rmdir",
            "time",
            "type",
            "vol",
        }
        for alias in windows_cmd_aliases:
            default_aliases[alias] = [os.getenv("COMSPEC"), "/c", alias]
        default_aliases["call"] = ["source-cmd"]
        default_aliases["source-bat"] = ["source-cmd"]
        default_aliases["clear"] = "cls"
        if ON_ANACONDA:
            # Add aliases specific to the Anaconda python distribution.
            default_aliases["activate"] = ["source-cmd", "activate.bat"]
            default_aliases["deactivate"] = ["source-cmd", "deactivate.bat"]
        if shutil.which("sudo", path=XSH.env.get_detyped("PATH")):
            # XSH.commands_cache is not available during setup
            import xonsh.platform.winutils as winutils

            def sudo(args):
                if len(args) < 1:
                    print(
                        "You need to provide an executable to run as " "Administrator."
                    )
                    return
                cmd = args[0]
                if locate_binary(cmd):
                    return winutils.sudo(cmd, args[1:])
                elif cmd.lower() in windows_cmd_aliases:
                    args = ["/D", "/C", "CD", _get_cwd(), "&&"] + args
                    return winutils.sudo("cmd", args)
                else:
                    msg = 'Cannot find the path for executable "{0}".'
                    print(msg.format(cmd))

            default_aliases["sudo"] = sudo
    elif ON_DARWIN:
        default_aliases["ls"] = ["ls", "-G"]
    elif ON_FREEBSD or ON_DRAGONFLY:
        default_aliases["grep"] = ["grep", "--color=auto"]
        default_aliases["egrep"] = ["egrep", "--color=auto"]
        default_aliases["fgrep"] = ["fgrep", "--color=auto"]
        default_aliases["ls"] = ["ls", "-G"]
    elif ON_NETBSD:
        default_aliases["grep"] = ["grep", "--color=auto"]
        default_aliases["egrep"] = ["egrep", "--color=auto"]
        default_aliases["fgrep"] = ["fgrep", "--color=auto"]
    elif ON_OPENBSD:
        pass
    else:
        default_aliases["grep"] = ["grep", "--color=auto"]
        default_aliases["egrep"] = ["egrep", "--color=auto"]
        default_aliases["fgrep"] = ["fgrep", "--color=auto"]
        default_aliases["ls"] = ["ls", "--color=auto", "-v"]
    return default_aliases
