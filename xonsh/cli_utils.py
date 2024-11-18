"""
helper functions and classes to create argparse CLI from functions.

Examples
 please see :py:class:`xonsh.completers.completer.CompleterAlias` class
"""

import argparse as ap
import functools
import inspect
import os
import sys
import typing as tp
from collections import defaultdict
from typing import Annotated

from xonsh.built_ins import XSH
from xonsh.completers.tools import RichCompletion


class ArgCompleter:
    """Gives a structure to the argparse completers"""

    def __call__(self, **kwargs):
        """return dynamic completers for the given action."""
        raise NotImplementedError


def Arg(
    *args: str,
    completer: tp.Union[ArgCompleter, tp.Callable[..., tp.Iterator[str]]] = None,
    **kwargs,
):
    # converting to tuple because of limitation with hashing args in py3.6
    # after dropping py36 support, the dict can be returned
    kwargs["completer"] = completer
    return args, tuple(kwargs.items())


class NumpyDoc:
    """Represent parsed function docstring"""

    def __init__(self, func, prefix_chars="-", follow_wraps=True):
        """Parse the function docstring and return its help content

        Parameters
        ----------
        func
            a callable/object that holds docstring
        """

        if follow_wraps and isinstance(func, functools.partial):
            func = func.func

        doc: str = inspect.getdoc(func) or ""
        self.description, rest = self.get_func_doc(doc)

        params, rest = self.get_param_doc(rest)
        self.params = {}
        self.flags = {}
        for head, lines in params.items():
            parts = [st.strip() for st in head.split(":")]
            if len(parts) == 2:
                name, flag = parts
                if flag and any(map(flag.startswith, prefix_chars)):
                    self.flags[name] = [st.strip() for st in flag.split(",")]
            else:
                name = parts[0]

            self.params[name] = self.join(lines)

        self.epilog = self.join(rest)

    @staticmethod
    def join(lines):
        # remove any extra noise after parse
        return inspect.cleandoc(os.linesep.join(lines)).strip()

    @staticmethod
    def get_func_doc(doc):
        lines = doc.splitlines()
        token = "Parameters"
        if token in lines:
            idx = lines.index(token)
            desc = lines[:idx]
        else:
            desc = lines
            idx = len(lines)
        return NumpyDoc.join(desc), lines[idx + 2 :]

    @staticmethod
    def get_param_doc(lines: list[str]):
        docs: dict[str, list[str]] = defaultdict(list)
        name = None

        while lines:
            # check new section by checking next line
            if len(lines) > 1 and (set(lines[1].strip()) == {"-"}):
                break

            lin = lines.pop(0)

            if not lin:
                continue

            if lin.startswith(" ") and name:
                docs[name].append(lin)
            else:
                name = lin

        return docs, lines


_FUNC_NAME = "_func_"


def _get_args_kwargs(annot: tp.Any) -> tuple[tp.Sequence[str], dict[str, tp.Any]]:
    args, kwargs = [], {}
    if isinstance(annot, tuple):
        args, kwargs = annot
    elif "Annotated[" in str(annot):
        if hasattr(annot, "__metadata__"):
            args, kwargs = annot.__metadata__[0]
        else:
            from typing import get_args

            _, (args, kwargs) = get_args(annot)

    if isinstance(kwargs, tuple):
        kwargs = dict(kwargs)

    return args, kwargs


def add_args(
    parser: ap.ArgumentParser,
    func: tp.Callable,
    allowed_params=None,
    doc=None,
) -> None:
    """Using the function's annotation add arguments to the parser

    basically converts ``def fn(param : Arg(*args, **kw), ...): ...``
        -> into equivalent ``parser.add_argument(*args, *kw)`` call.
    """

    # call this function when this sub-command is selected
    parser.set_defaults(**{_FUNC_NAME: func})
    doc = doc or NumpyDoc(func, parser.prefix_chars)
    sign = inspect.signature(func)
    for name, param in sign.parameters.items():
        if name.startswith("_") or (
            allowed_params is not None and name not in allowed_params
        ):
            continue
        flags, kwargs = _get_args_kwargs(param.annotation)
        if (not flags) and (name in doc.flags):  # load from docstring
            flags = doc.flags.get(name)

        if flags:  # optional argument. eg. --option
            kwargs.setdefault("dest", name)
        else:  # positional argument
            flags = [name]

            # checks for optional positional arg
            if (
                (inspect.Parameter.empty != param.default)
                and (param.default is None)
                and ("nargs" not in kwargs)
                and ("action" not in kwargs)
            ):
                kwargs.setdefault("nargs", "?")

        if inspect.Parameter.empty != param.default:
            kwargs.setdefault("default", param.default)

            # for booleans set action automatically
            if (
                flags
                and isinstance(param.default, bool)
                and ("action" not in kwargs)
                and ("type" not in kwargs)
            ):
                # opposite of default value
                act_name = "store_false" if param.default else "store_true"
                kwargs.setdefault("action", act_name)

        # help can be set by passing help argument otherwise inferred from docstring
        kwargs.setdefault("help", doc.params.get(name))

        completer = kwargs.pop("completer", None)
        action = parser.add_argument(*flags, **kwargs)

        if completer:
            action.completer = completer  # type: ignore

        action.help = action.help or ""
        # Don't show default when
        # 1. None : No value is given for the option
        # 2. bool : in case of flags the default is opposite of the flag's meaning
        if (
            action.default
            and (not isinstance(action.default, bool))
            and ("%(default)s" not in action.help)
        ):
            action.help += os.linesep + " (default: '%(default)s')"
        if action.type and "%(type)s" not in action.help:
            action.help += " (type: %(type)s)"


def make_parser(
    func: tp.Union[tp.Callable, str],
    empty_help=False,
    **kwargs,
) -> "ArgParser":
    """A bare-bones argparse builder from functions"""
    doc = NumpyDoc(func)
    if "description" not in kwargs:
        kwargs["description"] = doc.description
    if "epilog" not in kwargs:
        if doc.epilog:
            kwargs["epilog"] = doc.epilog
    parser = ArgParser(**kwargs)
    if empty_help:
        parser.default_command = "--help"
    return parser


class RstHelpFormatter(ap.RawTextHelpFormatter):
    """Highlight help string as rst"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from pygments.formatters.terminal import TerminalFormatter

        self.formatter = TerminalFormatter()

    def start_section(self, heading) -> None:
        from pygments.token import Generic

        heading = self.colorize((Generic.Heading, heading))
        return super().start_section(heading)

    def _get_help_string(self, action) -> str:
        return self.markup_rst(action.help)

    def colorize(self, *tokens: tuple) -> str:
        from pygments import format

        return format(tokens, self.formatter)

    def markup_rst(self, text):
        from pygments import highlight
        from pygments.lexers.markup import RstLexer

        return highlight(text, RstLexer(), self.formatter)

    def _format_text(self, text):
        text = super()._format_text(text)
        if text:
            text = self.markup_rst(text)
        return text

    def _format_usage(self, usage, actions, groups, prefix):
        from pygments.token import Generic, Name

        text = super()._format_usage(usage, actions, groups, prefix)
        parts = text.split(self._prog, maxsplit=1)
        if len(parts) == 2 and all(parts):
            text = self.colorize(
                (Generic.Heading, parts[0]),
                (Name.Function, self._prog),
                (Name.Attribute, parts[1]),  # from _format_actions_usage
            )
        return text

    def _format_action_invocation(self, action):
        from pygments.token import Name

        text = super()._format_action_invocation(action)
        return self.colorize((Name.Attribute, text))


def get_argparse_formatter_class():
    from xonsh.platform import HAS_PYGMENTS

    if (
        hasattr(sys, "stderr")
        and sys.stderr.isatty()
        and XSH.env.get("XONSH_INTERACTIVE")
        and HAS_PYGMENTS
    ):
        return RstHelpFormatter
    return ap.RawTextHelpFormatter


class ArgParser(ap.ArgumentParser):
    """Sub-class of ArgumentParser with special methods to nest commands"""

    def __init__(self, **kwargs):
        if "formatter_class" not in kwargs:
            kwargs["formatter_class"] = get_argparse_formatter_class()

        super().__init__(**kwargs)
        self.commands = None
        self.default_command = None

    def add_command(
        self,
        func: tp.Callable,
        default=False,
        args: "tuple[str, ...] | None" = None,
        **kwargs,
    ):
        """
            create a sub-parser and call this function during dispatch

        Parameters
        ----------
        func
            a type-annotated function that will be used to create ArgumentParser instance.
            All parameters that start with ``_`` will not be added to parser arguments.
            Use _stdout, _stack ... to receive them from callable-alias/commands.
            Use _parser to get the generated parser instance.
            Use _args to get what is passed from sys.argv
            Use _parsed to get result of ``parser.parse_args``
        default
            Marks this sub-command as the default command for this parser.
        args
            if given only add these arguments to the parser.
            Otherwise all parameters to the function without `_` prefixed
            in their name gets added to the parser.
        kwargs
            passed to ``subparser.add_parser`` call

        Returns
        -------
            result from ``subparser.add_parser``
        """
        if not self.commands:
            self.commands = self.add_subparsers(title="commands", dest="command")

        doc = NumpyDoc(func)
        kwargs.setdefault("description", doc.description)
        kwargs.setdefault("help", doc.description)
        name = kwargs.pop("prog", None)
        if not name:
            name = func.__name__.lstrip("_").replace("_", "-")

        if default:
            self.default_command = name

        parser = self.commands.add_parser(name, **kwargs)
        add_args(parser, func, allowed_params=args, doc=doc)
        return parser

    def _parse_known_args(
        self, arg_strings: list[str], namespace: ap.Namespace, *args, **kwargs
    ):
        arg_set = set(arg_strings)
        if (
            self.commands
            and self.default_command
            and ({"-h", "--help"}.isdisjoint(arg_set))
            and (set(self.commands.choices).isdisjoint(arg_set))
        ):
            arg_strings = [self.default_command] + arg_strings
        return super()._parse_known_args(arg_strings, namespace, *args, **kwargs)


def run_with_partial_args(func: tp.Callable, ns: dict[str, tp.Any]):
    """Run function based on signature. Filling the arguments will be based on the values in ``ns``."""
    sign = inspect.signature(func)
    kwargs = {}
    for name, param in sign.parameters.items():
        default = None
        # sometimes the args are skipped in the parser.
        # like ones having _ prefix(private to the function), or some special cases like exclusive group.
        # it is better to fill the defaults from paramspec when available.
        if param.default != inspect.Parameter.empty:
            default = param.default
        kwargs[name] = ns.get(name, default)
    return func(**kwargs)


def dispatch(parser: ap.ArgumentParser, args=None, lenient=False, **ns):
    """Call the underlying function with arguments parsed from sys.argv

    Parameters
    ----------
    parser
        root parser
    args
        sys.argv as parsed by Alias
    lenient
        if True, then use parser_know_args and pass the extra arguments as `_unparsed`
    ns
        a dict that will be passed to underlying function
    """
    ns.setdefault("_parser", parser)
    ns.setdefault("_args", args)

    if lenient:
        parsed, unparsed = parser.parse_known_args(args)
        ns["_unparsed"] = unparsed
    else:
        parsed = parser.parse_args(args)
    ns["_parsed"] = parsed
    ns.update(vars(parsed))

    if _FUNC_NAME in ns:
        func = ns[_FUNC_NAME]
        return run_with_partial_args(func, ns)


class ArgparseCompleter:
    """A completer function for ArgParserAlias commands"""

    def __init__(self, parser: ap.ArgumentParser, command, **kwargs):
        args = tuple(c.value for c in command.args[: command.arg_index])

        self.parser, self.remaining_args = self.get_parser(parser, args[1:])

        self.long_opts_only = XSH.env.get("ALIAS_COMPLETIONS_OPTIONS_LONGEST", False)
        self.command = command
        kwargs["command"] = command
        # will be sent to completer function
        self.kwargs = kwargs

    @staticmethod
    def get_parser(parser, args) -> tuple[ap.ArgumentParser, tuple[str, ...]]:
        """Check for sub-parsers"""
        sub_parsers = {}
        for act in parser._get_positional_actions():
            if act.nargs == ap.PARSER:
                sub_parsers = act.choices  # there should be only one subparser
        if sub_parsers:
            for idx, pos in enumerate(args):
                if pos in sub_parsers:
                    # get the correct parser
                    return ArgparseCompleter.get_parser(
                        sub_parsers[pos], args[idx + 1 :]
                    )
        # base scenario
        return parser, args

    def filled(self, act: ap.Action) -> int:
        """Consume remaining_args for the given action"""
        args_len = 0
        for arg in self.remaining_args:
            if arg and arg[0] in self.parser.prefix_chars:
                # stop when other --option explicitly given
                break
            args_len += 1
        nargs = (
            act.nargs
            if isinstance(act.nargs, int)
            else args_len + 1
            if act.nargs in {ap.ONE_OR_MORE, ap.ZERO_OR_MORE}
            else 1
        )
        if len(self.remaining_args) >= nargs:
            # consume n-number of args
            self.remaining_args = self.remaining_args[nargs:]
            # complete for next action
            return True
        return False

    def _complete(self, act: ap.Action, **kwargs):
        if hasattr(act, "completer") and callable(act.completer):  # type: ignore
            # call the completer function
            kwargs.update(self.kwargs)
            yield from act.completer(xsh=XSH, action=act, completer=self, **kwargs)  # type: ignore

        if (
            hasattr(act, "choices")
            and act.choices
            and not isinstance(act.choices, dict)
        ):
            # any sequence or iterable
            yield from act.choices

    def _complete_pos(self, act):
        # even subparserAction can have completer attribute set
        yield from self._complete(act)

        if isinstance(act.choices, dict):  # sub-parsers
            for choice, sub_parser in act.choices.items():
                yield RichCompletion(
                    choice,
                    description=sub_parser.description or "",
                    append_space=True,
                )

    def complete(self):
        # options will come before/after positionals
        options = {act: None for act in self.parser._get_optional_actions()}

        # remove options that are already filled
        opt_completions = self._complete_options(options)
        if opt_completions:
            yield from opt_completions
            return

        for act in self.parser._get_positional_actions():
            # number of arguments it consumes
            if self.filled(act):
                continue
            yield from self._complete_pos(act)
            # close after a valid positional arg completion
            break

        opt_completions = self._complete_options(options)
        if opt_completions:
            yield from opt_completions
            return

        # complete remaining options only if requested or enabled
        show_opts = XSH.env.get("ALIAS_COMPLETIONS_OPTIONS_BY_DEFAULT", False)
        if not show_opts:
            if not (
                self.command.prefix
                and self.command.prefix[0] in self.parser.prefix_chars
            ):
                return

        # in the end after positionals show remaining unfilled options
        for act in options:
            for flag in sorted(act.option_strings, key=len, reverse=True):
                desc = ""
                if act.help:
                    formatter = self.parser._get_formatter()
                    try:
                        desc = formatter._expand_help(act)
                    except KeyError:
                        desc = act.help
                yield RichCompletion(flag, description=desc)
                if self.long_opts_only:
                    break

    def _complete_options(self, options):
        while self.remaining_args:
            arg = self.remaining_args[0]
            act_res = self.parser._parse_optional(arg)
            if not act_res:
                # it is not a option string: pass
                break
            if isinstance(act_res, list):
                assert len(act_res) == 1
                act_res = act_res[0]
            # it is a valid option and advance
            self.remaining_args = self.remaining_args[1:]
            act, *_, value = act_res

            # remove the found option
            # todo: not remove if append/extend
            options.pop(act, None)

            if self.filled(act):
                continue
            # stop suggestion until current option is complete
            return self._complete(act)


class ArgParserAlias:
    """Provides a structure to the Alias. The parser is lazily loaded.

    can help create ``argparse.ArgumentParser`` parser from function
    signature and dispatch the functions.

    Examples
    ---------
        For usage please check :py:mod:`xonsh.completers.completer`
    """

    class Error(Exception):
        """Special case, when raised, the traceback will not be shown.
        Instead the process with exit with error code and message"""

        def __init__(self, message: str, errno=1):
            super().__init__(message)
            self.errno = errno

    def __init__(self, threadable=True, **kwargs) -> None:
        if not threadable:
            from xonsh.tools import unthreadable

            unthreadable(self)
        self._parser = None
        self.kwargs = kwargs
        self.stdout = None
        self.stderr = None

    def build(self) -> "ArgParser":
        """Sub-classes should return constructed ArgumentParser"""
        if self.kwargs:
            return self.create_parser(**self.kwargs)
        raise NotImplementedError

    @property
    def parser(self):
        if self._parser is None:
            self._parser = self.build()
        return self._parser

    def create_parser(
        self, func=None, has_args=False, allowed_params=None, **kwargs
    ) -> "ArgParser":
        """create root parser"""
        func = func or self
        has_args = has_args or bool(allowed_params)
        if has_args:
            kwargs.setdefault("empty_help", False)

        parser = make_parser(func, **kwargs)
        if has_args:
            add_args(parser, func, allowed_params=allowed_params)
        return parser

    def xonsh_complete(self, command, **kwargs):
        completer = ArgparseCompleter(self.parser, command=command, **kwargs)
        yield from completer.complete()

    def write_to(self, stream: str, *args, **kwargs):
        value = getattr(self, stream)
        out = getattr(sys, stream) if value is None else value
        kwargs.setdefault("file", out)
        print(*args, **kwargs)

    def err(self, *args, **kwargs):
        """Write text to error stream"""
        self.write_to("stderr", *args, **kwargs)

    def out(self, *args, **kwargs):
        """Write text to output stream"""
        self.write_to("stdout", *args, **kwargs)

    def __call__(
        self,
        args,
        stdin=None,
        stdout=None,
        stderr=None,
        spec=None,
        stack=None,
        **kwargs,
    ):
        self.stdout = stdout
        self.stderr = stderr
        try:
            result = dispatch(
                self.parser,
                args,
                _stdin=stdin,
                _stdout=stdout,
                _stderr=stderr,
                _spec=spec,
                _stack=stack,
                **kwargs,
            )
        except self.Error as ex:
            self.err(f"Error: {ex}")
            sys.exit(getattr(ex, "errno", 1))
        finally:
            # free the reference to input/output. Otherwise it will result in errors
            self.stdout = None
            self.stderr = None
        return result


__all__ = (
    "Arg",
    "ArgParserAlias",
    "ArgparseCompleter",
    "Annotated",
    "ArgParser",
    "make_parser",
    "add_args",
    "NumpyDoc",
    "dispatch",
)
