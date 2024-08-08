"""A (tab-)completer for xonsh."""

import collections.abc as cabc
import sys
import typing as tp

from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    Completion,
    RichCompletion,
    apply_lprefix,
    get_filter_function,
    is_contextual_completer,
    is_exclusive_completer,
)
from xonsh.parsers.completion_context import CompletionContext, CompletionContextParser
from xonsh.tools import print_exception


class Completer:
    """This provides a list of optional completions for the xonsh shell."""

    def __init__(self):
        self.context_parser = CompletionContextParser()

    def parse(
        self, text: str, cursor_index: "None|int" = None, ctx=None
    ) -> "CompletionContext":
        """Parse the given text

        Parameters
        ----------
        text
            multi-line text
        cursor_index
            position of the cursor. If not given, then it is considered to be at the end.
        ctx
            Execution context
        """
        cursor_index = len(text) if cursor_index is None else cursor_index
        return self.context_parser.parse(text, cursor_index, ctx)

    def complete_line(self, text: str):
        """Handy wrapper to build command-completion-context when cursor is at the end.

        Notes
        -----
        suffix is not supported; text after last space is parsed as prefix.
        """
        ctx = self.parse(text)

        if not ctx:
            raise RuntimeError("CompletionContext is None")

        if ctx.python is not None:
            prefix = ctx.python.prefix
        elif ctx.command is not None:
            prefix = ctx.command.prefix
        else:
            raise RuntimeError("CompletionContext is empty")

        line = text
        begidx = text.rfind(prefix)
        endidx = begidx + len(prefix)

        return self.complete(
            prefix,
            line,
            begidx,
            endidx,
            cursor_index=len(line),
            multiline_text=line,
            completion_context=ctx,
        )

    def complete(
        self,
        prefix,
        line,
        begidx,
        endidx,
        ctx=None,
        multiline_text=None,
        cursor_index=None,
        completion_context=None,
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

        if (
            (multiline_text is not None)
            and (cursor_index is not None)
            and (completion_context is None)
        ):
            completion_context: tp.Optional[CompletionContext] = self.parse(
                multiline_text,
                cursor_index,
                ctx,
            )

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
    ) -> tuple[Completion, int]:
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
    ) -> tp.Iterator[tuple[Completion, int]]:
        filter_func = get_filter_function()

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
                name = func.__name__ if hasattr(func, "__name__") else str(func)
                print_exception(
                    f"Completer {name} raises exception when gets "
                    f"old_args={old_completer_args[:-1]} / completion_context={completion_context!r}:\n"
                    f"{type(e)} - {e}"
                )
                continue

            completing_contextual_command = (
                is_contextual_completer(func)
                and completion_context is not None
                and completion_context.command is not None
            )

            # -- set comp-defaults --

            # the default is that the completer function filters out as necessary
            # we can change that once fuzzy/substring matches are added
            is_filtered = True
            custom_lprefix = False
            prefix = ""
            if completing_contextual_command:
                prefix = completion_context.command.prefix
            elif old_completer_args is not None:
                prefix = old_completer_args[0]
            lprefix = len(prefix)

            if isinstance(out, cabc.Sequence):
                # update comp-defaults from
                res, lprefix_filtered = out
                if isinstance(lprefix_filtered, bool):
                    is_filtered = lprefix_filtered
                else:
                    lprefix = lprefix_filtered
                    custom_lprefix = True
            else:
                res = out

            if res is None:
                continue

            items = []
            for comp in res:
                if (not is_filtered) and (not filter_func(comp, prefix)):
                    continue
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

        # using dict to keep order py3.6+
        completions = {}

        query_limit = XSH.env.get("COMPLETION_QUERY_LIMIT")

        for comp in self.generate_completions(
            completion_context,
            old_completer_args,
            trace,
        ):
            completion, lprefix = comp
            completions[completion] = None
            if query_limit and len(completions) >= query_limit:
                if trace:
                    print(
                        "TRACE COMPLETIONS: Stopped after $COMPLETION_QUERY_LIMIT reached."
                    )
                break

        if completion_context:
            if completion_context.python is not None:
                prefix = completion_context.python.prefix
            elif completion_context.command is not None:
                prefix = completion_context.command.prefix
            else:
                raise RuntimeError("Completion context is empty")

            if prefix.startswith("$"):
                prefix = prefix[1:]

            def sortkey(s):
                """Sort values by prefix position and then alphabetically."""
                return (s.lower().find(prefix.lower()), s.lower())
        else:
            # Fallback sort.
            sortkey = lambda s: s.lstrip(''''"''').lower()

        # the last completer's lprefix is returned. other lprefix values are inside the RichCompletions.
        return tuple(sorted(completions, key=sortkey)), lprefix
