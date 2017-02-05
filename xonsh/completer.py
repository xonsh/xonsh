# -*- coding: utf-8 -*-
"""A (tab-)completer for xonsh."""
import builtins
import collections.abc as cabc


class Completer(object):
    """This provides a list of optional completions for the xonsh shell."""
    def complete(self, prefix, line, begidx, endidx, ctx=None):
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

        Returns
        -------
        rtn : list of str
            Possible completions of prefix, sorted alphabetically.
        lprefix : int
            Length of the prefix to be replaced in the completion.
        """
        ctx = ctx or {}
        for func in builtins.__xonsh_completers__.values():
            try:
                out = func(prefix, line, begidx, endidx, ctx)
            except StopIteration:
                return set(), len(prefix)
            if isinstance(out, cabc.Sequence):
                res, lprefix = out
            else:
                res = out
                lprefix = len(prefix)
            if res is not None and len(res) != 0:
                def sortkey(s): return s.lstrip(''''"''').lower()
                return tuple(sorted(res, key=sortkey)), lprefix
        return set(), lprefix
