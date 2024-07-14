"""Aliases for the xonsh shell."""

import argparse
import functools
import inspect
import operator
import os
import re
import shutil
import sys
import types
import typing as tp
from collections import abc as cabc
from typing import Literal

import xonsh.completers._aliases as xca
import xonsh.history.main as xhm
import xonsh.xoreutils.which as xxw
from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.dirstack import _get_cwd, cd, dirs, popd, pushd
from xonsh.environ import locate_binary, make_args_env
from xonsh.foreign_shells import foreign_shell_data
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
from xonsh.procs.executables import locate_file
from xonsh.procs.jobs import bg, clean_jobs, disown, fg, jobs
from xonsh.procs.specs import DecoratorAlias, SpecAttrDecoratorAlias
from xonsh.timings import timeit_alias
from xonsh.tools import (
    ALIAS_KWARG_NAMES,
    XonshError,
    adjust_shlvl,
    argvquote,
    escape_windows_cmd_string,
    print_color,
    print_exception,
    strip_simple_quotes,
    swap_values,
    to_repr_pretty_,
    to_shlvl,
    unthreadable,
)
from xonsh.xontribs import xontribs_main


@lazyobject
def EXEC_ALIAS_RE():
    return re.compile(r"@\(|\$\(|!\(|\$\[|!\[|\&\&|\|\||\s+and\s+|\s+or\s+|[>|<]")


class FuncAlias:
    """Provides a callable alias for xonsh commands."""

    attributes_show = ["__xonsh_threadable__", "__xonsh_capturable__", "return_what"]
    attributes_inherit = attributes_show + ["__doc__"]
    return_what: Literal["command", "result"] = "result"

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
        self,
        args=None,
        stdin=None,
        stdout=None,
        stderr=None,
        spec=None,
        stack=None,
        decorators=None,
    ):
        return run_alias_by_params(
            self.func,
            {
                "args": args,
                "stdin": stdin,
                "stdout": stdout,
                "stderr": stderr,
                "spec": spec,
                "stack": stack,
                "decorators": decorators,
            },
        )


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

    def return_command(self, f):
        """Decorator that switches alias from returning result to return in new command for execution."""
        f.return_what = "command"
        return f

    def eval_alias(
        self,
        value,
        seen_tokens=frozenset(),
        acc_args=(),
        decorators=None,
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
        decorators = decorators if decorators is not None else []
        # Beware of mutability: default values for keyword args are evaluated
        # only once.
        if (
            isinstance(value, cabc.Iterable)
            and hasattr(value, "__len__")
            and len(value) > 1
        ):
            i = 0
            for v in value:
                if isinstance(mod := self._raw.get(str(v)), DecoratorAlias):
                    decorators.append(mod)
                    i += 1
                else:
                    break
            value = value[i:]

        if callable(value) and getattr(value, "return_what", "result") == "command":
            try:
                value = value(acc_args, decorators=decorators)
                acc_args = []
            except Exception as e:
                print_exception(f"Exception inside alias {value}: {e}")
                return None
            if not len(value):
                raise ValueError("return_command alias: zero arguments.")

        if callable(value):
            return [value] + list(acc_args)
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
                    decorators=decorators,
                )

    def get(
        self,
        key,
        default=None,
        decorators=None,
    ):
        """
        Returns list that represent command with resolved aliases.
        The ``key`` can be string with alias name or list for a command.
        In the first position will be the resolved command name or callable alias.
        If the key is not present, then `default` is returned.

        ``decorators`` is the list of `DecoratorAlias` objects that found during
        resolving aliases (#5443).

        Note! The return value is always list because during resolving
        we can find return_command alias that can completely replace
        command and add new arguments.
        """
        decorators = decorators if decorators is not None else []
        args = []
        if isinstance(key, list):
            args = key[1:]
            key = key[0]
        val = self._raw.get(key)
        if callable(val) and getattr(val, "return_what", "result") == "command":
            try:
                val = val(args, decorators=decorators)
                args = []
            except Exception as e:
                print_exception(f"Exception inside alias {key!r}: {e}")
                return None
            if not len(val):
                raise ValueError("return_command alias: zero arguments.")

        if val is None:
            return default
        elif isinstance(val, cabc.Iterable) or callable(val):
            return self.eval_alias(
                val,
                seen_tokens={key},
                decorators=decorators,
                acc_args=args,
            )
        else:
            msg = "alias of {!r} has an inappropriate type: {!r}"
            raise TypeError(msg.format(key, val))

    def expand_alias(self, line: str, cursor_index: int) -> str:
        """Expands any aliases present in line if alias does not point to a
        builtin function and if alias is only a single command.
        The command won't be expanded if the cursor's inside/behind it.
        """
        word = (line.split(maxsplit=1) or [""])[0]
        if word in self and not callable(self.get(word)[0]):  # type: ignore
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


class PartialEvalAlias7(PartialEvalAliasBase):
    def __call__(
        self,
        args,
        stdin=None,
        stdout=None,
        stderr=None,
        spec=None,
        stack=None,
        decorators=None,
    ):
        args = list(self.acc_args) + args
        return self.f(args, stdin, stdout, stderr, spec, stack, decorators)


PARTIAL_EVAL_ALIASES = (
    PartialEvalAlias0,
    PartialEvalAlias1,
    PartialEvalAlias2,
    PartialEvalAlias3,
    PartialEvalAlias4,
    PartialEvalAlias5,
    PartialEvalAlias6,
    PartialEvalAlias7,
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
    if numargs < 8:
        return PARTIAL_EVAL_ALIASES[numargs](f, acc_args=acc_args)
    else:
        e = "Expected proxy with 7 or fewer arguments for {}, not {}"
        raise XonshError(e.format(", ".join(ALIAS_KWARG_NAMES), numargs))


def run_alias_by_params(func: tp.Callable, params: dict[str, tp.Any]):
    """
    Run alias function based on signature and params.
    If function param names are in alias signature fill them.
    If function params have unknown names fill using alias signature order.
    """
    alias_params = {
        "args": None,
        "stdin": None,
        "stdout": None,
        "stderr": None,
        "spec": None,
        "stack": None,
        "decorators": None,
    }
    alias_params |= params
    sign = inspect.signature(func)
    func_params = sign.parameters.items()
    kwargs = {
        name: alias_params[name] for name, p in func_params if name in alias_params
    }

    if len(kwargs) != len(func_params):
        # There is unknown param. Switch to positional mode.
        kwargs = dict(
            zip(map(operator.itemgetter(0), func_params), alias_params.values())
        )
    return func(**kwargs)


#
# Actual aliases below
#


def xonsh_exit(args, stdin=None):
    """Sends signal to exit shell."""
    if not clean_jobs():
        # Do not exit if jobs not cleaned up
        return None, None
    if args:
        try:
            code = int(args[0])
        except ValueError:
            code = 1
    else:
        code = 0
    XSH.exit = code
    print()  # gimme a newline
    return None, None


def xonsh_reset(args, stdin=None):
    """Clears __xonsh__.ctx"""
    XSH.ctx.clear()


def source_foreign_fn(
    shell: str,
    files_or_code: Annotated[list[str], Arg(nargs="+")],
    interactive=False,
    login=False,
    envcmd=None,
    aliascmd=None,
    extra_args="",
    safe=True,
    prevcmd="",
    postcmd="",
    funcscmd="",
    sourcer=None,
    use_tmpfile=False,
    seterrprevcmd=None,
    seterrpostcmd=None,
    overwrite_aliases=False,
    suppress_skip_message=False,
    show=False,
    dryrun=False,
    _stderr=None,
):
    """Sources a file written in a foreign shell language.

    Parameters
    ----------
    shell
        Name or path to the foreign shell
    files_or_code
        file paths to source or code in the target language.
    interactive : -i, --interactive
        whether the sourced shell should be interactive
    login : -l, --login
        whether the sourced shell should be login
    envcmd : --envcmd
        command to print environment
    aliascmd : --aliascmd
        command to print aliases
    extra_args : --extra-args
        extra arguments needed to run the shell
    safe : -u, --unsafe
        whether the source shell should be run safely, and not raise any errors, even if they occur.
    prevcmd : -p, --prevcmd
        command(s) to run before any other commands, replaces traditional source.
    postcmd : --postcmd
        command(s) to run after all other commands
    funcscmd : --funcscmd
        code to find locations of all native functions in the shell language.
    sourcer : --sourcer
        the source command in the target shell language.
        If this is not set, a default value will attempt to be
        looked up based on the shell name.
    use_tmpfile : --use-tmpfile
        whether the commands for source shell should be written to a temporary file.
    seterrprevcmd : --seterrprevcmd
        command(s) to set exit-on-error before any other commands.
    seterrpostcmd : --seterrpostcmd
        command(s) to set exit-on-error after all other commands.
    overwrite_aliases : --overwrite-aliases
        flag for whether or not sourced aliases should replace the current xonsh aliases.
    suppress_skip_message : --suppress-skip-message
        flag for whether or not skip messages should be suppressed.
    show : --show
        show the script output.
    dryrun : -d, --dry-run
        Will not actually source the file.
    """
    extra_args = tuple(extra_args.split())
    env = XSH.env
    suppress_skip_message = (
        env.get("FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE")
        if not suppress_skip_message
        else suppress_skip_message
    )
    files: tuple[str, ...] = ()
    if prevcmd:
        pass  # don't change prevcmd if given explicitly
    elif os.path.isfile(files_or_code[0]):
        if not sourcer:
            return (None, "xonsh: error: `sourcer` command is not mentioned.\n", 1)
        # we have filenames to source
        prevcmd = "".join([f"{sourcer} {f}\n" for f in files_or_code])
        files = tuple(files_or_code)
    elif not prevcmd:
        prevcmd = " ".join(files_or_code)  # code to run, no files
    foreign_shell_data.cache_clear()  # make sure that we don't get prev src
    fsenv, fsaliases = foreign_shell_data(
        shell=shell,
        login=login,
        interactive=interactive,
        envcmd=envcmd,
        aliascmd=aliascmd,
        extra_args=extra_args,
        safe=safe,
        prevcmd=prevcmd,
        postcmd=postcmd,
        funcscmd=funcscmd or None,  # the default is None in the called function
        sourcer=sourcer,
        use_tmpfile=use_tmpfile,
        seterrprevcmd=seterrprevcmd,
        seterrpostcmd=seterrpostcmd,
        show=show,
        dryrun=dryrun,
        files=files,
    )
    if fsenv is None:
        if dryrun:
            return
        else:
            msg = f"xonsh: error: Source failed: {prevcmd!r}\n"
            msg += "xonsh: error: Possible reasons: File not found or syntax error\n"
            return (None, msg, 1)
    # apply results
    denv = env.detype()
    for k, v in fsenv.items():
        if k == "SHLVL":  # ignore $SHLVL as sourcing should not change $SHLVL
            continue
        if k in denv and v == denv[k]:
            continue  # no change from original
        env[k] = v
    # Remove any env-vars that were unset by the script.
    for k in denv:
        if k not in fsenv:
            env.pop(k, None)
    # Update aliases
    baliases = XSH.aliases
    for k, v in fsaliases.items():
        if k in baliases and v == baliases[k]:
            continue  # no change from original
        elif overwrite_aliases or k not in baliases:
            baliases[k] = v
        elif suppress_skip_message:
            pass
        else:
            msg = (
                "Skipping application of {0!r} alias from {1!r} "
                "since it shares a name with an existing xonsh alias. "
                'Use "--overwrite-alias" option to apply it anyway. '
                'You may prevent this message with "--suppress-skip-message" or '
                '"$FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE = True".'
            )
            print(msg.format(k, shell), file=_stderr)


class SourceForeignAlias(ArgParserAlias):
    def build(self):
        parser = self.create_parser(**self.kwargs)
        # for backwards compatibility
        parser.add_argument(
            "-n",
            "--non-interactive",
            action="store_false",
            dest="interactive",
            help="Deprecated: The default mode runs in non-interactive mode.",
        )
        return parser


source_foreign = SourceForeignAlias(
    func=source_foreign_fn, has_args=True, prog="source-foreign"
)


@unthreadable
def source_alias(args, stdin=None):
    """Executes the contents of the provided files in the current context.
    If sourced file isn't found in cwd, search for file along $PATH to source
    instead.
    """
    env = XSH.env
    encoding = env.get("XONSH_ENCODING")
    errors = env.get("XONSH_ENCODING_ERRORS")
    for i, fname in enumerate(args):
        fpath = fname
        if not os.path.isfile(fpath):
            fpath = locate_file(fname)
            if fpath is None:
                if env.get("XONSH_DEBUG"):
                    print(f"source: {fname}: No such file", file=sys.stderr)
                if i == 0:
                    raise RuntimeError(
                        "must source at least one file, " + fname + " does not exist."
                    )
                break
        _, fext = os.path.splitext(fpath)
        if fext and fext != ".xsh" and fext != ".py":
            raise RuntimeError(
                "attempting to source non-xonsh file! If you are "
                "trying to source a file in another language, "
                "then please use the appropriate source command. "
                "For example, source-bash script.sh"
            )
        with open(fpath, encoding=encoding, errors=errors) as fp:
            src = fp.read()
        if not src.endswith("\n"):
            src += "\n"
        ctx = XSH.ctx
        updates = {"__file__": fpath, "__name__": os.path.abspath(fpath)}
        with (
            env.swap(XONSH_MODE="source", **make_args_env(args[i + 1 :])),
            swap_values(ctx, updates),
        ):
            try:
                XSH.builtins.execx(src, "exec", ctx, filename=fpath)
            except Exception:
                print_color(
                    "{RED}You may be attempting to source non-xonsh file! "
                    "{RESET}If you are trying to source a file in "
                    "another language, then please use the appropriate "
                    "source command. For example, {GREEN}source-bash "
                    "script.sh{RESET}",
                    file=sys.stderr,
                )
                raise


def source_cmd_fn(
    files: Annotated[list[str], Arg(nargs="+")],
    login=False,
    aliascmd=None,
    extra_args="",
    safe=True,
    postcmd="",
    funcscmd="",
    seterrprevcmd=None,
    overwrite_aliases=False,
    suppress_skip_message=False,
    show=False,
    dryrun=False,
    _stderr=None,
):
    """
        Source cmd.exe files

    Parameters
    ----------
    files
        paths to source files.
    login : -l, --login
        whether the sourced shell should be login
    envcmd : --envcmd
        command to print environment
    aliascmd : --aliascmd
        command to print aliases
    extra_args : --extra-args
        extra arguments needed to run the shell
    safe : -s, --safe
        whether the source shell should be run safely, and not raise any errors, even if they occur.
    postcmd : --postcmd
        command(s) to run after all other commands
    funcscmd : --funcscmd
        code to find locations of all native functions in the shell language.
    seterrprevcmd : --seterrprevcmd
        command(s) to set exit-on-error before any other commands.
    overwrite_aliases : --overwrite-aliases
        flag for whether or not sourced aliases should replace the current xonsh aliases.
    suppress_skip_message : --suppress-skip-message
        flag for whether or not skip messages should be suppressed.
    show : --show
        show the script output.
    dryrun : -d, --dry-run
        Will not actually source the file.
    """
    args = list(files)
    fpath = locate_binary(args[0])
    args[0] = fpath if fpath else args[0]
    if not os.path.isfile(args[0]):
        return (None, f"xonsh: error: File not found: {args[0]}\n", 1)
    prevcmd = "call "
    prevcmd += " ".join([argvquote(arg, force=True) for arg in args])
    prevcmd = escape_windows_cmd_string(prevcmd)
    with XSH.env.swap(PROMPT="$P$G"):
        return source_foreign_fn(
            shell="cmd",
            files_or_code=args,
            interactive=True,
            sourcer="call",
            envcmd="set",
            seterrpostcmd="if errorlevel 1 exit 1",
            use_tmpfile=True,
            prevcmd=prevcmd,
            #     from this function
            login=login,
            aliascmd=aliascmd,
            extra_args=extra_args,
            safe=safe,
            postcmd=postcmd,
            funcscmd=funcscmd,
            seterrprevcmd=seterrprevcmd,
            overwrite_aliases=overwrite_aliases,
            suppress_skip_message=suppress_skip_message,
            show=show,
            dryrun=dryrun,
        )


source_cmd = ArgParserAlias(func=source_cmd_fn, has_args=True, prog="source-cmd")


def xexec_fn(
    command: Annotated[list[str], Arg(nargs=argparse.REMAINDER)],
    login=False,
    clean=False,
    name="",
    _stdin=None,
):
    """exec (also aliased as xexec) uses the os.execvpe() function to
    replace the xonsh process with the specified program.

    This provides the functionality of the bash 'exec' builtin::

        >>> exec bash -l -i
        bash $

    Parameters
    ----------
    command
        program to launch along its arguments
    login : -l, --login
        the shell places a dash at the
        beginning of the zeroth argument passed to command to simulate login
        shell.
    clean : -c, --clean
        causes command to be executed with an empty environment.
    name : -a, --name
        the shell passes name as the zeroth argument
        to the executed command.

    Notes
    -----
    This command **is not** the same as the Python builtin function
    exec(). That function is for running Python code. This command,
    which shares the same name as the sh-lang statement, is for launching
    a command directly in the same process. In the event of a name conflict,
    please use the xexec command directly or dive into subprocess mode
    explicitly with ![exec command]. For more details, please see
    http://xon.sh/faq.html#exec.
    """
    if len(command) == 0:
        return (None, "xonsh: exec: no command specified\n", 1)

    cmd = command[0]
    if name:
        command[0] = name
    if login:
        command[0] = f"-{command[0]}"

    denv = {}
    if not clean:
        denv = XSH.env.detype()

        # decrement $SHLVL to mirror bash's behaviour
        if "SHLVL" in denv:
            old_shlvl = to_shlvl(denv["SHLVL"])
            denv["SHLVL"] = str(adjust_shlvl(old_shlvl, -1))

    try:
        os.execvpe(cmd, command, denv)
    except FileNotFoundError as e:
        return (
            None,
            f"xonsh: exec: file not found: {e.args[1]}: {command[0]}" "\n",
            1,
        )


xexec = ArgParserAlias(func=xexec_fn, has_args=True, prog="xexec")


@lazyobject
def xonfig():
    """Runs the xonsh configuration utility."""
    from xonsh.xonfig import xonfig_main  # lazy import

    return xonfig_main


@unthreadable
def trace(args, stdin=None, stdout=None, stderr=None, spec=None):
    """Runs the xonsh tracer utility."""
    from xonsh.tracer import tracermain  # lazy import

    try:
        return tracermain(args, stdin=stdin, stdout=stdout, stderr=stderr, spec=spec)
    except SystemExit:
        pass


def showcmd(args, stdin=None):
    """usage: showcmd [-h|--help|cmd args]

    Displays the command and arguments as a list of strings that xonsh would
    run in subprocess mode. This is useful for determining how xonsh evaluates
    your commands and arguments prior to running these commands.

    optional arguments:
      -h, --help            show this help message and exit

    Examples
    --------
      >>> showcmd echo $USER "can't" hear "the sea"
      ['echo', 'I', "can't", 'hear', 'the sea']
    """
    if len(args) == 0 or (len(args) == 1 and args[0] in {"-h", "--help"}):
        print(showcmd.__doc__.rstrip().replace("\n    ", "\n"))
    else:
        sys.displayhook(args)


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
        "source": source_alias,
        "source-zsh": SourceForeignAlias(
            func=functools.partial(source_foreign_fn, "zsh", sourcer="source"),
            has_args=True,
            prog="source-zsh",
        ),
        "source-bash": SourceForeignAlias(
            func=functools.partial(source_foreign_fn, "bash", sourcer="source"),
            has_args=True,
            prog="source-bash",
        ),
        "source-cmd": source_cmd,
        "source-foreign": source_foreign,
        "history": xhm.history_main,
        "trace": trace,
        "timeit": timeit_alias,
        "xonfig": xonfig,
        "scp-resume": ["rsync", "--partial", "-h", "--progress", "--rsh=ssh"],
        "showcmd": showcmd,
        "ipynb": ["jupyter", "notebook", "--no-browser"],
        "which": xxw.which,
        "xontrib": xontribs_main,
        "completer": xca.completer_alias,
        "xpip": detect_xpip_alias(),
        "xonsh-reset": xonsh_reset,
        "@thread": SpecAttrDecoratorAlias(
            {"threadable": True, "force_threadable": True},
            "Mark current command as threadable.",
        ),
        "@unthread": SpecAttrDecoratorAlias(
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
            import xonsh.platforms.winutils as winutils

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
