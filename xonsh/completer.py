"""A (tab-)completer for xonsh."""
from __future__ import print_function, unicode_literals
import os
import sys
import builtins
import subprocess
from glob import glob, iglob

XONSH_TOKENS = {'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 
    'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 
    'import', 'if', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 
    'raise', 'return', 'try', 'while', 'with', 'yield', '+', '-', '/', '//', 
    '%', '**', '|', '&', '~', '^', '>>', '<<', '<', '<=', '>', '>=', '==', 
    '!=', '->', '=', '+=', '-=', '*=', '/=', '%=', '**=', '>>=', '<<=', 
    '&=', '^=', '|=', '//=', ',', ';', ':', '?', '??', '$(', '${', '$[', 
    '..', '...'}

class Completer(object):
    """This provides a list of optional completions for the xonsh shell."""

    def complete(self, prefix, line, begidx, endidx, ctx=None):
        """Complete the string s, given a possible execution context.

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
        """
        rtn = {s for s in XONSH_TOKENS if s.startswith(prefix)}
        if ctx is not None:
            rtn |= {s for s in ctx if s.startswith(prefix)}
        rtn |= {s for s in dir(builtins) if s.startswith(prefix)}
        rtn |= {s for s in builtins.aliases if s.startswith(prefix)}
        if prefix.startswith('$'):
            key = prefix[1:]
            rtn |= {k for k in builtins.__xonsh_env__ if k.startswith(key)}
        rtn.update(iglob(prefix + '*'))
        #print(rtn)
        return sorted(rtn)
