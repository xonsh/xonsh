import argparse as ap
import typing as tp

from xonsh.built_ins import XSH
from xonsh.completers.tools import RichCompletion
from xonsh.parsers.completion_context import CommandContext


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
                desc = ""
                if act.help:
                    formatter = self.parser._get_formatter()
                    try:
                        desc = formatter._expand_help(act)
                    except KeyError:
                        desc = act.help
                yield RichCompletion(flag, description=desc)

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
