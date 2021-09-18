# -*- coding: utf-8 -*-
"""A (tab-)completer for xonsh."""
import sys
import typing as tp
import collections.abc as cabc

from xonsh.completers.tools import (
    is_contextual_completer,
    Completion,
    RichCompletion,
    apply_lprefix,
    is_exclusive_completer,
)
from xonsh.built_ins import XSH
from xonsh.parsers.completion_context import CompletionContext, CompletionContextParser
from xonsh.tools import print_exception


class Completer(object):
    """This provides a list of optional completions for the xonsh shell."""

    def __init__(self):
        self.context_parser = CompletionContextParser()

    def complete(
        self,
        prefix,
        line,
        begidx,
        endidx,
        ctx=None,
        multiline_text=None,
        cursor_index=None,
    ):
        """Complete the string, given a possible execution context.

        Parameters
        ----------
        prefix : str
            The string to match
        line : str
            The line that prefix appears on.
        begidx : int
            The index in line that prefix starts on.
        endidx : int
            The index in line that prefix ends on.
        ctx : dict, optional
            Names in the current execution context.
        multiline_text : str
            The complete multiline text. Needed to get completion context.
        cursor_index : int
            The current cursor's index in the multiline text.
            May be ``len(multiline_text)`` for cursor at the end.
            Needed to get completion context.

        Returns
        -------
        rtn : list of str
            Possible completions of prefix, sorted alphabetically.
        lprefix : int
            Length of the prefix to be replaced in the completion.
        """

        if multiline_text is not None and cursor_index is not None:
            completion_context: tp.Optional[
                CompletionContext
            ] = self.context_parser.parse(
                multiline_text,
                cursor_index,
                ctx,
            )
        else:
            completion_context = None

        ctx = ctx or {}
        return self.complete_from_context(
            completion_context,
            (prefix, line, begidx, endidx, ctx),
        )

    @staticmethod
    def _format_completion(
        completion,
        completion_context,
        completing_contextual_command: bool,
        lprefix: int,
        custom_lprefix: bool,
    ) -> tp.Tuple[Completion, int]:
        if (
            completing_contextual_command
            and completion_context.command.is_after_closing_quote
        ):
            """
            The cursor is appending to a closed string literal, i.e. cursor at the end of ``ls "/usr/"``.
            1. The closing quote will be appended to all completions.
                I.e the completion ``/usr/bin`` will turn into ``/usr/bin"``
                To prevent this behavior, a completer can return a ``RichCompletion`` with ``append_closing_quote=False``.
            2. If not specified, lprefix will cover the closing prefix.
                I.e for ``ls "/usr/"``, the default lprefix will be 6 to include the closing quote.
                To prevent this behavior, a completer can return a different lprefix or specify it inside ``RichCompletion``.
            """
            closing_quote = completion_context.command.closing_quote
            if not custom_lprefix:
                lprefix += len(closing_quote)
            if closing_quote:
                if isinstance(completion, RichCompletion):
                    if completion.append_closing_quote:
                        completion = completion.replace(
                            value=completion.value + closing_quote
                        )
                else:
                    completion = completion + closing_quote

        completion = list(apply_lprefix([completion], lprefix))[0]

        if (
            isinstance(completion, RichCompletion)
            and completion.append_space
            and not completion.value.endswith(" ")
        ):
            # append spaces AFTER appending closing quote
            completion = completion.replace(value=completion.value + " ")

        return completion, lprefix

    @staticmethod
    def generate_completions(
        completion_context, old_completer_args, trace: bool
    ) -> tp.Iterator[tp.Tuple[Completion, int]]:
        for name, func in XSH.completers.items():
            try:
                if is_contextual_completer(func):
                    if completion_context is None:
                        continue
                    out = func(completion_context)
                else:
                    if old_completer_args is None:
                        continue
                    out = func(*old_completer_args)
            except StopIteration:
                # completer requested to stop collecting completions
                break
            except Exception as e:
                print_exception(
                    f"Completer {func.__name__} raises exception when gets "
                    f"old_args={old_completer_args[:-1]} / completion_context={completion_context!r}:\n"
                    f"{type(e)} - {e}"
                )
                continue

            completing_contextual_command = (
                is_contextual_completer(func)
                and completion_context is not None
                and completion_context.command is not None
            )
            if isinstance(out, cabc.Sequence):
                res, lprefix = out
                custom_lprefix = True
            else:
                res = out
                custom_lprefix = False
                if completing_contextual_command:
                    lprefix = len(completion_context.command.prefix)
                elif old_completer_args is not None:
                    lprefix = len(old_completer_args[0])
                else:
                    lprefix = 0

            if res is None:
                continue

            items = []
            for comp in res:
                comp = Completer._format_completion(
                    comp,
                    completion_context,
                    completing_contextual_command,
                    lprefix or 0,
                    custom_lprefix,
                )
                items.append(comp)
                yield comp

            if not items:  # empty completion
                continue

            if trace:
                print(
                    f"TRACE COMPLETIONS: Got {len(items)} results"
                    f" from {'' if is_exclusive_completer(func) else 'non-'}exclusive completer '{name}':"
                )
                sys.displayhook(items)

            if is_exclusive_completer(func):
                # we got completions for an exclusive completer
                break

    def complete_from_context(self, completion_context, old_completer_args=None):
        trace = XSH.env.get("XONSH_TRACE_COMPLETIONS")
        if trace:
            print("\nTRACE COMPLETIONS: Getting completions with context:")
            sys.displayhook(completion_context)
        lprefix = 0
        completions = set()
        query_limit = XSH.env.get("COMPLETION_QUERY_LIMIT")

        for comp in self.generate_completions(
            completion_context,
            old_completer_args,
            trace,
        ):
            completion, lprefix = comp
            completions.add(completion)
            if query_limit and len(completions) >= query_limit:
                if trace:
                    print(
                        "TRACE COMPLETIONS: Stopped after $COMPLETION_QUERY_LIMIT reached."
                    )
                break

        def sortkey(s):
            return s.lstrip(''''"''').lower()

        # the last completer's lprefix is returned. other lprefix values are inside the RichCompletions.
        return tuple(sorted(completions, key=sortkey)), lprefix
