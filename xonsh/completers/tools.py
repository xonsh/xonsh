"""Xonsh completer tools."""
import argparse as ap
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


class ArgparseCompleter:
    """A completer function for ArgParserAlias commands"""

    def __init__(self, parser: ap.ArgumentParser, command: CommandContext, **kwargs):
        args = tuple(c.value for c in command.args[: command.arg_index])

        self.parser, self.remaining_args = self.get_parser(parser, args[1:])

        self.command = command
        kwargs["command"] = command
        self.kwargs = kwargs
        """will be sent to completer function"""

    @staticmethod
    def get_parser(parser, args) -> tp.Tuple[ap.ArgumentParser, tp.Tuple[str, ...]]:
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
        if act.choices:
            yield from act.choices
        elif hasattr(act, "completer") and callable(act.completer):  # type: ignore
            # call the completer function
            from xonsh.built_ins import XSH

            kwargs.update(self.kwargs)
            yield from act.completer(xsh=XSH, action=act, completer=self, **kwargs)  # type: ignore

    def _complete_pos(self, act):
        if isinstance(act.choices, dict):  # sub-parsers
            for choice, sub_parser in act.choices.items():
                yield RichCompletion(
                    choice,
                    description=sub_parser.description or "",
                    append_space=True,
                )
        else:
            yield from self._complete(act)

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
            for flag in act.option_strings:
                yield RichCompletion(flag, description=act.help or "")

    def _complete_options(self, options):
        while self.remaining_args:
            arg = self.remaining_args[0]
            act_res = self.parser._parse_optional(arg)
            if not act_res:
                # it is not a option string: pass
                break
            # it is a valid option and advance
            self.remaining_args = self.remaining_args[1:]
            act, _, value = act_res

            # remove the found option
            # todo: not remove if append/extend
            options.pop(act, None)

            if self.filled(act):
                continue
            # stop suggestion until current option is complete
            return self._complete(act)


def complete_argparser(parser, command: CommandContext, **kwargs):
    completer = ArgparseCompleter(parser, command=command, **kwargs)
    yield from completer.complete()
