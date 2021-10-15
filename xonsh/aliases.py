# -*- coding: utf-8 -*-
"""Aliases for the xonsh shell."""
import os
import re
import sys
import inspect
import argparse
import collections.abc as cabc
import typing as tp

from xonsh.built_ins import XSH
from xonsh.lazyasd import lazyobject
from xonsh.dirstack import cd, pushd, popd, dirs, _get_cwd
from xonsh.environ import locate_binary, make_args_env
from xonsh.foreign_shells import foreign_shell_data
from xonsh.jobs import jobs, fg, bg, clean_jobs, disown
from xonsh.platform import (
    ON_ANACONDA,
    ON_DARWIN,
    ON_WINDOWS,
    ON_FREEBSD,
    ON_NETBSD,
    ON_OPENBSD,
    ON_DRAGONFLY,
    ON_POSIX,
    IN_APPIMAGE,
)
from xonsh.tools import (
    XonshError,
    argvquote,
    escape_windows_cmd_string,
    to_bool,
    swap_values,
    strip_simple_quotes,
    ALIAS_KWARG_NAMES,
    unthreadable,
    print_color,
    to_repr_pretty_,
)
from xonsh.timings import timeit_alias
from xonsh.xontribs import xontribs_main
from xonsh.ast import isexpression
from xonsh.cli_utils import ArgParserAlias, Arg, Annotated

import xonsh.completers._aliases as xca
import xonsh.history.main as xhm
import xonsh.xoreutils.which as xxw
from xonsh.xoreutils.umask import umask

if ON_POSIX:
    from xonsh.xoreutils.ulimit import ulimit


@lazyobject
def EXEC_ALIAS_RE():
    return re.compile(r"@\(|\$\(|!\(|\$\[|!\[|\&\&|\|\||\s+and\s+|\s+or\s+|[>|<]")


class Aliases(cabc.MutableMapping):
    """Represents a location to hold and look up aliases."""

    def __init__(self, *args, **kwargs):
        self._raw = {}
        self.update(*args, **kwargs)

    def get(self, key, default=None):
        """Returns the (possibly modified) value. If the key is not present,
        then `default` is returned.
        If the value is callable, it is returned without modification. If it
        is an iterable of strings it will be evaluated recursively to expand
        other aliases, resulting in a new list or a "partially applied"
        callable.
        """
        val = self._raw.get(key)
        if val is None:
            return default
        elif isinstance(val, cabc.Iterable) or callable(val):
            return self.eval_alias(val, seen_tokens={key})
        else:
            msg = "alias of {!r} has an inappropriate type: {!r}"
            raise TypeError(msg.format(key, val))

    def eval_alias(self, value, seen_tokens=frozenset(), acc_args=()):
        """
        "Evaluates" the alias ``value``, by recursively looking up the leftmost
        token and "expanding" if it's also an alias.

        A value like ``["cmd", "arg"]`` might transform like this:
        ``> ["cmd", "arg"] -> ["ls", "-al", "arg"] -> callable()``
        where ``cmd=ls -al`` and ``ls`` is an alias with its value being a
        callable.  The resulting callable will be "partially applied" with
        ``["-al", "arg"]``.
        """
        # Beware of mutability: default values for keyword args are evaluated
        # only once.
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
                return self.eval_alias(self._raw[token], seen_tokens, acc_args)

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
        return "{0}.{1}({2})".format(
            self.__class__.__module__, self.__class__.__name__, self._raw
        )

    _repr_pretty_ = to_repr_pretty_


class ExecAlias:
    """Provides a callable alias for xonsh source code."""

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

    def __repr__(self):
        return "ExecAlias({0!r}, filename={1!r})".format(self.src, self.filename)


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
        return "{name}({f!r}, acc_args={acc_args!r})".format(
            name=self.__class__.__name__, f=self.f, acc_args=self.acc_args
        )


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


def xonsh_reset(args, stdin=None):
    """Clears __xonsh__.ctx"""
    XSH.ctx.clear()


@lazyobject
def _SOURCE_FOREIGN_PARSER():
    desc = "Sources a file written in a foreign shell language."
    parser = argparse.ArgumentParser("source-foreign", description=desc)
    parser.add_argument("shell", help="Name or path to the foreign shell")
    parser.add_argument(
        "files_or_code",
        nargs="+",
        help="file paths to source or code in the target " "language.",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        type=to_bool,
        default=True,
        help="whether the sourced shell should be interactive",
        dest="interactive",
    )
    parser.add_argument(
        "-l",
        "--login",
        type=to_bool,
        default=False,
        help="whether the sourced shell should be login",
        dest="login",
    )
    parser.add_argument(
        "--envcmd", default=None, dest="envcmd", help="command to print environment"
    )
    parser.add_argument(
        "--aliascmd", default=None, dest="aliascmd", help="command to print aliases"
    )
    parser.add_argument(
        "--extra-args",
        default=(),
        dest="extra_args",
        type=(lambda s: tuple(s.split())),
        help="extra arguments needed to run the shell",
    )
    parser.add_argument(
        "-s",
        "--safe",
        type=to_bool,
        default=True,
        help="whether the source shell should be run safely, "
        "and not raise any errors, even if they occur.",
        dest="safe",
    )
    parser.add_argument(
        "-p",
        "--prevcmd",
        default=None,
        dest="prevcmd",
        help="command(s) to run before any other commands, "
        "replaces traditional source.",
    )
    parser.add_argument(
        "--postcmd",
        default="",
        dest="postcmd",
        help="command(s) to run after all other commands",
    )
    parser.add_argument(
        "--funcscmd",
        default=None,
        dest="funcscmd",
        help="code to find locations of all native functions " "in the shell language.",
    )
    parser.add_argument(
        "--sourcer",
        default=None,
        dest="sourcer",
        help="the source command in the target shell " "language, default: source.",
    )
    parser.add_argument(
        "--use-tmpfile",
        type=to_bool,
        default=False,
        help="whether the commands for source shell should be "
        "written to a temporary file.",
        dest="use_tmpfile",
    )
    parser.add_argument(
        "--seterrprevcmd",
        default=None,
        dest="seterrprevcmd",
        help="command(s) to set exit-on-error before any" "other commands.",
    )
    parser.add_argument(
        "--seterrpostcmd",
        default=None,
        dest="seterrpostcmd",
        help="command(s) to set exit-on-error after all" "other commands.",
    )
    parser.add_argument(
        "--overwrite-aliases",
        default=False,
        action="store_true",
        dest="overwrite_aliases",
        help="flag for whether or not sourced aliases should "
        "replace the current xonsh aliases.",
    )
    parser.add_argument(
        "--suppress-skip-message",
        default=None,
        action="store_true",
        dest="suppress_skip_message",
        help="flag for whether or not skip messages should be suppressed.",
    )
    parser.add_argument(
        "--show",
        default=False,
        action="store_true",
        dest="show",
        help="Will show the script output.",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        default=False,
        action="store_true",
        dest="dryrun",
        help="Will not actually source the file.",
    )
    return parser


def source_foreign(args, stdin=None, stdout=None, stderr=None):
    """Sources a file written in a foreign shell language."""
    env = XSH.env
    ns = _SOURCE_FOREIGN_PARSER.parse_args(args)
    ns.suppress_skip_message = (
        env.get("FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE")
        if ns.suppress_skip_message is None
        else ns.suppress_skip_message
    )
    if ns.prevcmd is not None:
        pass  # don't change prevcmd if given explicitly
    elif os.path.isfile(ns.files_or_code[0]):
        # we have filename to source
        ns.prevcmd = '{} "{}"'.format(ns.sourcer, '" "'.join(ns.files_or_code))
    elif ns.prevcmd is None:
        ns.prevcmd = " ".join(ns.files_or_code)  # code to run, no files
    foreign_shell_data.cache_clear()  # make sure that we don't get prev src
    fsenv, fsaliases = foreign_shell_data(
        shell=ns.shell,
        login=ns.login,
        interactive=ns.interactive,
        envcmd=ns.envcmd,
        aliascmd=ns.aliascmd,
        extra_args=ns.extra_args,
        safe=ns.safe,
        prevcmd=ns.prevcmd,
        postcmd=ns.postcmd,
        funcscmd=ns.funcscmd,
        sourcer=ns.sourcer,
        use_tmpfile=ns.use_tmpfile,
        seterrprevcmd=ns.seterrprevcmd,
        seterrpostcmd=ns.seterrpostcmd,
        show=ns.show,
        dryrun=ns.dryrun,
    )
    if fsenv is None:
        if ns.dryrun:
            return
        else:
            msg = "xonsh: error: Source failed: {0!r}\n".format(ns.prevcmd)
            msg += "xonsh: error: Possible reasons: File not found or syntax error\n"
            return (None, msg, 1)
    # apply results
    denv = env.detype()
    for k, v in fsenv.items():
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
        elif ns.overwrite_aliases or k not in baliases:
            baliases[k] = v
        elif ns.suppress_skip_message:
            pass
        else:
            msg = (
                "Skipping application of {0!r} alias from {1!r} "
                "since it shares a name with an existing xonsh alias. "
                'Use "--overwrite-alias" option to apply it anyway.'
                'You may prevent this message with "--suppress-skip-message" or '
                '"$FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE = True".'
            )
            print(msg.format(k, ns.shell), file=stderr)


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
            fpath = locate_binary(fname)
            if fpath is None:
                if env.get("XONSH_DEBUG"):
                    print("source: {}: No such file".format(fname), file=sys.stderr)
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
        with open(fpath, "r", encoding=encoding, errors=errors) as fp:
            src = fp.read()
        if not src.endswith("\n"):
            src += "\n"
        ctx = XSH.ctx
        updates = {"__file__": fpath, "__name__": os.path.abspath(fpath)}
        with env.swap(**make_args_env(args[i + 1 :])), swap_values(ctx, updates):
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


def source_cmd(args, stdin=None):
    """Simple cmd.exe-specific wrapper around source-foreign."""
    args = list(args)
    fpath = locate_binary(args[0])
    args[0] = fpath if fpath else args[0]
    if not os.path.isfile(args[0]):
        return (None, "xonsh: error: File not found: {}\n".format(args[0]), 1)
    prevcmd = "call "
    prevcmd += " ".join([argvquote(arg, force=True) for arg in args])
    prevcmd = escape_windows_cmd_string(prevcmd)
    args.append("--prevcmd={}".format(prevcmd))
    args.insert(0, "cmd")
    args.append("--interactive=0")
    args.append("--sourcer=call")
    args.append("--envcmd=set")
    args.append("--seterrpostcmd=if errorlevel 1 exit 1")
    args.append("--use-tmpfile=1")
    with XSH.env.swap(PROMPT="$P$G"):
        return source_foreign(args, stdin=stdin)


def xexec_fn(
    command: Annotated[tp.List[str], Arg(nargs=argparse.REMAINDER)],
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
        command[0] = "-{}".format(command[0])

    denv = {}
    if not clean:
        denv = XSH.env.detype()

    try:
        os.execvpe(cmd, command, denv)
    except FileNotFoundError as e:
        return (
            None,
            "xonsh: exec: file not found: {}: {}" "\n".format(e.args[1], command[0]),
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
        if ON_WINDOWS or IN_APPIMAGE:
            # XXX: Does windows have an installation mode that requires UAC?
            return basecmd
        elif not os.access(os.path.dirname(sys.executable), os.W_OK):
            return ["sudo"] + basecmd
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
        "source-zsh": ["source-foreign", "zsh", "--sourcer=source"],
        "source-bash": ["source-foreign", "bash", "--sourcer=source"],
        "source-cmd": source_cmd,
        "source-foreign": source_foreign,
        "history": xhm.history_main,
        "trace": trace,
        "timeit": timeit_alias,
        "umask": umask,
        "xonfig": xonfig,
        "scp-resume": ["rsync", "--partial", "-h", "--progress", "--rsh=ssh"],
        "showcmd": showcmd,
        "ipynb": ["jupyter", "notebook", "--no-browser"],
        "which": xxw.which,
        "xontrib": xontribs_main,
        "completer": xca.completer_alias,
        "xpip": detect_xpip_alias(),
        "xonsh-reset": xonsh_reset,
    }
    if ON_POSIX:
        default_aliases["ulimit"] = ulimit
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
            default_aliases[alias] = ["cmd", "/c", alias]
        default_aliases["call"] = ["source-cmd"]
        default_aliases["source-bat"] = ["source-cmd"]
        default_aliases["clear"] = "cls"
        if ON_ANACONDA:
            # Add aliases specific to the Anaconda python distribution.
            default_aliases["activate"] = ["source-cmd", "activate.bat"]
            default_aliases["deactivate"] = ["source-cmd", "deactivate.bat"]
        if not locate_binary("sudo"):
            import xonsh.winutils as winutils

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
