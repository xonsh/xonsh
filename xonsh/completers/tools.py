"""Xonsh completer tools."""
import inspect
import textwrap
import typing as tp
from functools import wraps

from xonsh.built_ins import XSH
from xonsh.lazyasd import lazyobject
from xonsh.parsers.completion_context import CompletionContext, CommandContext


def _filter_normal(s, x):
    return s.startswith(x)


def _filter_ignorecase(s, x):
    return s.lower().startswith(x.lower())


def get_filter_function():
    """
    Return an appropriate filtering function for completions, given the valid
    of $CASE_SENSITIVE_COMPLETIONS
    """
    csc = XSH.env.get("CASE_SENSITIVE_COMPLETIONS")
    if csc:
        return _filter_normal
    else:
        return _filter_ignorecase


def justify(s, max_length, left_pad=0):
    """
    Re-wrap the string s so that each line is no more than max_length
    characters long, padding all lines but the first on the left with the
    string left_pad.
    """
    txt = textwrap.wrap(s, width=max_length, subsequent_indent=" " * left_pad)
    return "\n".join(txt)


class RichCompletion(str):
    """A rich completion that completers can return instead of a string"""

    def __new__(cls, value, *args, **kwargs):
        completion = super().__new__(cls, value)
        # ``str``'s ``__new__`` doesn't call ``__init__``, so we'll call it ourselves
        cls.__init__(completion, value, *args, **kwargs)
        return completion

    def __init__(
        self,
        value: str,
        prefix_len: tp.Optional[int] = None,
        display: tp.Optional[str] = None,
        description: str = "",
        style: str = "",
        append_closing_quote: bool = True,
        append_space: bool = False,
    ):
        """
        Parameters
        ----------
        value :
            The completion's actual value.
        prefix_len :
            Length of the prefix to be replaced in the completion.
            If None, the default prefix len will be used.
        display :
            Text to display in completion option list instead of ``value``.
            NOTE: If supplied, the common prefix with other completions won't be removed.
        description :
            Extra text to display when the completion is selected.
        style :
            Style to pass to prompt-toolkit's ``Completion`` object.
        append_closing_quote :
            Whether to append a closing quote to the completion if the cursor is after it.
            See ``Completer.complete`` in ``xonsh/completer.py``
        append_space :
            Whether to append a space after the completion.
            This is intended to work with ``appending_closing_quote``, so the space will be added correctly **after** the closing quote.
            This is used in ``Completer.complete``.
            An extra bonus is that the space won't show up in the ``display`` attribute.
        """
        super().__init__()
        self.prefix_len = prefix_len
        self.display = display
        self.description = description
        self.style = style
        self.append_closing_quote = append_closing_quote
        self.append_space = append_space

    @property
    def value(self):
        return str(self)

    def __repr__(self):
        # don't print default values
        attrs = ", ".join(
            f"{name}={getattr(self, name)!r}"
            for name, default in RICH_COMPLETION_DEFAULTS
            if getattr(self, name) != default
        )
        return f"RichCompletion({self.value!r}, {attrs})"

    def replace(self, **kwargs):
        """Create a new RichCompletion with replaced attributes"""
        default_kwargs = dict(
            value=self.value,
            **self.__dict__,
        )
        default_kwargs.update(kwargs)
        return RichCompletion(**default_kwargs)


@lazyobject
def RICH_COMPLETION_DEFAULTS():
    """The ``__init__`` parameters' default values (excluding ``self`` and ``value``)."""
    return [
        (name, param.default)
        for name, param in inspect.signature(RichCompletion.__init__).parameters.items()
        if name not in ("self", "value")
    ]


Completion = tp.Union[RichCompletion, str]
CompleterResult = tp.Union[tp.Set[Completion], tp.Tuple[tp.Set[Completion], int], None]
ContextualCompleter = tp.Callable[[CompletionContext], CompleterResult]


def contextual_completer(func: ContextualCompleter):
    """Decorator for a contextual completer

    This is used to mark completers that want to use the parsed completion context.
    See ``xonsh/parsers/completion_context.py``.

    ``func`` receives a single CompletionContext object.
    """
    func.contextual = True  # type: ignore
    return func


def is_contextual_completer(func):
    return getattr(func, "contextual", False)


def contextual_command_completer(func: tp.Callable[[CommandContext], CompleterResult]):
    """like ``contextual_completer``,
    but will only run when completing a command and will directly receive the ``CommandContext`` object"""

    @contextual_completer
    @wraps(func)
    def _completer(context: CompletionContext) -> CompleterResult:
        if context.command is not None:
            return func(context.command)
        return None

    return _completer


def contextual_command_completer_for(cmd: str):
    """like ``contextual_command_completer``,
    but will only run when completing the ``cmd`` command"""

    def decor(func: tp.Callable[[CommandContext], CompleterResult]):
        @contextual_completer
        @wraps(func)
        def _completer(context: CompletionContext) -> CompleterResult:
            if context.command is not None and context.command.completing_command(cmd):
                return func(context.command)
            return None

        return _completer

    return decor


def non_exclusive_completer(func):
    """Decorator for a non-exclusive completer

    This is used to mark completers that will be collected with other completer's results.
    """
    func.non_exclusive = True  # type: ignore
    return func


def is_exclusive_completer(func):
    return not getattr(func, "non_exclusive", False)


def apply_lprefix(comps, lprefix):
    if lprefix is None:
        return comps

    for comp in comps:
        if isinstance(comp, RichCompletion):
            if comp.prefix_len is None:
                yield comp.replace(prefix_len=lprefix)
            else:
                # this comp has a custom prefix len
                yield comp
        else:
            yield RichCompletion(comp, prefix_len=lprefix)


def _complete_argparser_action(act, **kwargs):
    if act.choices:
        yield from act.choices
    elif hasattr(act, "completer") and callable(act.completer):  # type: ignore
        from xonsh.built_ins import XSH

        yield from act.completer(xsh=XSH, action=act, **kwargs)  # type: ignore


def complete_argparser_actions(
    parser,
    positional: tp.Tuple[str, ...] = (),
    current_flag: str = "",
    **kwargs,
):
    """

    Parameters
    ----------
    parser
    positional
        indicates the positional_arguments already filled
    current_flag
        when given returns completions for the flag
    """
    import argparse as ap

    if positional:
        sub_parsers = {}
        for act in parser._get_positional_actions():
            if isinstance(act.choices, dict):
                sub_parsers = act.choices
        if sub_parsers:
            # get the correct parser
            for idx, pos in enumerate(positional):
                if pos in sub_parsers:
                    yield from complete_argparser_actions(
                        sub_parsers[pos], positional[idx + 1 :], current_flag, **kwargs
                    )
                    return

    for act in parser._get_positional_actions():
        # number of arguments it consumes
        nargs = (
            act.nargs
            if isinstance(act.nargs, int)
            else len(positional) + 1
            if act.nargs in {ap.ONE_OR_MORE, ap.ZERO_OR_MORE}
            else 1
        )
        if len(positional) >= nargs:
            # after consuming
            positional = positional[nargs:]
            continue

        if isinstance(act.choices, dict):  # sub-parsers
            for choice, sub_parser in act.choices.items():
                yield RichCompletion(choice, description=sub_parser.description or "")
        else:
            yield from _complete_argparser_action(act, positional=positional, **kwargs)
        # close after a valid positional arg completion
        break

    # todo: handle consume by flag values
    #   1. when flags come before positional
    #   2. when flags have values given handle
    for act in parser._get_optional_actions():
        for flag in act.option_strings:
            if current_flag.startswith(flag):
                yield from _complete_argparser_action(act, **kwargs)
            elif not current_flag:  # show flags only for root parser
                yield RichCompletion(flag, description=act.help or "")


def complete_argparser(parser, command: CommandContext, **kwargs):
    """A completer function for ArgParserAlias commands"""
    args = tuple(c.value for c in command.args[: command.arg_index])
    position = args[1:]
    yield from complete_argparser_actions(parser, position, command=command, **kwargs)
