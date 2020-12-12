# -*- coding: utf-8 -*-
"""A (tab-)completer for xonsh."""
import builtins
import typing as tp
import collections.abc as cabc

from xonsh.completers.tools import is_contextual_completer
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
        ctx : Iterable of str (ie dict, set, etc), optional
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
            ] = self.context_parser.parse(multiline_text, cursor_index)
        else:
            completion_context = None

        ctx = ctx or {}
        for func in builtins.__xonsh__.completers.values():
            try:
                if is_contextual_completer(func):
                    if completion_context is None:
                        continue
                    out = func(completion_context)
                else:
                    out = func(prefix, line, begidx, endidx, ctx)
            except StopIteration:
                return set(), len(prefix)
            except Exception as e:
                print_exception(
                    f"Completer {func.__name__} raises exception when get "
                    f"(prefix={repr(prefix)}, line={repr(line)}, begidx={repr(begidx)}, endidx={repr(endidx)}):\n"
                    f"{e}"
                )
                return set(), len(prefix)
            if isinstance(out, cabc.Sequence):
                res, lprefix = out
            else:
                res = out
                lprefix = len(prefix)
            if res is not None and len(res) != 0:

                def sortkey(s):
                    return s.lstrip(''''"''').lower()

                return tuple(sorted(res, key=sortkey)), lprefix
        return set(), lprefix
