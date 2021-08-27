"""
helper functions and classes to create argparse CLI from functions.

Examples
 please see :py:class:`xonsh.completers.completer.CompleterAlias` class
"""

import argparse as ap
import inspect
import os
import sys
import typing as tp

TYPING_ANNOTATED_AVAILABLE = False
"""One can import ``Annotated`` from this module
which adds a stub when it is not available in ``typing``/``typing_extensions`` modules."""

try:
    from typing import Annotated  # noqa

    TYPING_ANNOTATED_AVAILABLE = True
except ImportError:
    try:
        from typing_extensions import Annotated  # type: ignore

        TYPING_ANNOTATED_AVAILABLE = True
    except ImportError:
        T = tp.TypeVar("T")  # Declare type variable

        class _AnnotatedMeta(type):
            def __getitem__(self, item: tp.Tuple[T, tp.Any]) -> T:
                if tp.TYPE_CHECKING:
                    return item[0]

                return item[1]

        class Annotated(metaclass=_AnnotatedMeta):  # type: ignore
            pass


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


def _get_func_doc(doc: str) -> str:
    lines = doc.splitlines()
    if "Parameters" in lines:
        idx = lines.index("Parameters")
        lines = lines[:idx]
    return os.linesep.join(lines)


def _get_param_doc(doc: str, param: str) -> tp.Iterator[str]:
    section_title = "\nParameters"
    if section_title not in doc:
        return
    _, doc = doc.split(section_title)
    started = False
    for lin in doc.splitlines():
        if not lin:
            continue
        if lin.startswith(param):
            started = True
            continue
        if not started:
            continue

        if not lin.startswith(" "):  # new section/parameter
            break
        yield lin


def get_doc(func: tp.Union[tp.Callable, str], parameter: str = None):
    """Parse the function docstring and return its help content

    Parameters
    ----------
    func
        a callable/object that holds docstring
    parameter
        name of the function parameter to parse doc for

    Returns
    -------
    str
        doc of the parameter/function
    """
    if isinstance(func, str):
        return func

    doc = inspect.getdoc(func) or ""
    if parameter:
        par_doc = os.linesep.join(_get_param_doc(doc, parameter))
        return inspect.cleandoc(par_doc).strip()
    else:
        return _get_func_doc(doc).strip()


_FUNC_NAME = "_func_"


def _get_args_kwargs(annot: tp.Any) -> tp.Tuple[tp.Sequence[str], tp.Dict[str, tp.Any]]:
    args, kwargs = [], {}
    if isinstance(annot, tuple):
        args, kwargs = annot
    elif TYPING_ANNOTATED_AVAILABLE and "Annotated[" in str(annot):
        if hasattr(annot, "__metadata__"):
            args, kwargs = annot.__metadata__[0]
        else:
            from typing_extensions import get_args

            _, (args, kwargs) = get_args(annot)

    if isinstance(kwargs, tuple):
        kwargs = dict(kwargs)

    return args, kwargs


def add_args(parser: ap.ArgumentParser, func: tp.Callable, allowed_params=None) -> None:
    """Using the function's annotation add arguments to the parser
    param:Arg(*args, **kw) -> parser.add_argument(*args, *kw)
    """

    # call this function when this sub-command is selected
    parser.set_defaults(**{_FUNC_NAME: func})

    sign = inspect.signature(func)
    for name, param in sign.parameters.items():
        if name.startswith("_") or (
            allowed_params is not None and name not in allowed_params
        ):
            continue
        args, kwargs = _get_args_kwargs(param.annotation)

        if args:  # optional argument. eg. --option
            kwargs.setdefault("dest", name)
        else:  # positional argument
            args = [name]

        if inspect.Parameter.empty != param.default:
            kwargs.setdefault("default", param.default)

        # help can be set by passing help argument otherwise inferred from docstring
        kwargs.setdefault("help", get_doc(func, name))

        completer = kwargs.pop("completer", None)
        action = parser.add_argument(*args, **kwargs)
        if completer:
            action.completer = completer  # type: ignore
        action.help = action.help or ""
        if action.default and "%(default)s" not in action.help:
            action.help += os.linesep + " (default: %(default)s)"
        if action.type and "%(type)s" not in action.help:
            action.help += " (type: %(type)s)"


def make_parser(
    func: tp.Union[tp.Callable, str],
    empty_help=True,
    **kwargs,
) -> "ArgParser":
    """A bare-bones argparse builder from functions"""
    if "description" not in kwargs:
        kwargs["description"] = get_doc(func)
    parser = ArgParser(**kwargs)
    if empty_help:
        parser.set_defaults(
            **{_FUNC_NAME: lambda stdout=None: parser.print_help(file=stdout)}
        )
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
        from pygments.token import Name, Generic

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
    from xonsh.built_ins import XSH
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

    def add_command(
        self, func: tp.Callable, args: tp.Optional[tp.Iterable[str]] = None, **kwargs
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

        doc = get_doc(func)
        kwargs.setdefault("description", doc)
        kwargs.setdefault("help", doc)
        parser = self.commands.add_parser(kwargs.pop("prog", func.__name__), **kwargs)
        add_args(parser, func, allowed_params=args)
        return parser


def dispatch(parser: ap.ArgumentParser, args=None, **ns):
    """call the sub-command selected by user"""

    parsed = parser.parse_args(args)
    ns["_parsed"] = parsed
    ns.update(vars(parsed))

    func = ns[_FUNC_NAME]
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


class ArgParserAlias:
    """Provides a structure to the Alias. The parser is lazily loaded.

    can help create ``argparse.ArgumentParser`` parser from function
    signature and dispatch the functions.

    Examples
    ---------
        For usage please check ``xonsh.completers.completer.py`` module.
    """

    def __init__(self, threadable=True, **kwargs) -> None:
        if not threadable:
            from xonsh.tools import unthreadable

            unthreadable(self)
        self._parser = None
        self.kwargs = kwargs

    def build(self):
        """Sub-classes should return constructed ArgumentParser"""
        if self.kwargs:
            return self.create_parser(**self.kwargs)
        raise NotImplementedError

    @property
    def parser(self):
        if self._parser is None:
            self._parser = self.build()
        return self._parser

    def create_parser(self, func=None, has_args=False, allowed_params=None, **kwargs):
        """create root parser"""
        func = func or self
        has_args = has_args or bool(allowed_params)
        if has_args:
            kwargs.setdefault("empty_help", False)
        parser = make_parser(func, **kwargs)
        if has_args:
            add_args(parser, func, allowed_params=allowed_params)
        return parser

    def __call__(
        self, args, stdin=None, stdout=None, stderr=None, spec=None, stack=None
    ):
        return dispatch(
            self.parser,
            args,
            _parser=self.parser,
            _args=args,
            _stdin=stdin,
            _stdout=stdout,
            _stderr=stderr,
            _spec=spec,
            _stack=stack,
        )


__all__ = (
    "Arg",
    "ArgParserAlias",
    "Annotated",
    "ArgParser",
    "make_parser",
    "add_args",
    "get_doc",
    "dispatch",
)
