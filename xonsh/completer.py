# -*- coding: utf-8 -*-
"""A (tab-)completer for xonsh."""
import os
import re
import ast
import sys
import shlex
import pickle
import inspect
import builtins
import importlib
import subprocess

from pathlib import Path
from collections import Sequence

from xonsh.built_ins import iglobpath, expand_path
from xonsh.platform import ON_WINDOWS
from xonsh.tools import (subexpr_from_unbalanced, get_sep,
                         check_for_partial_string, RE_STRING_START)
from xonsh.completers import completers


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
            Length of the prefix to be replaced in the completion
            (only used with prompt_toolkit)
        """
        space = ' '  # intern some strings for faster appending
        ctx = ctx or {}
        empty_set = set()
        for name, func in builtins.__xonsh_completers__.items():
            o = func(prefix, line, begidx, endidx, ctx)
            if isinstance(o, Sequence):
                res, lprefix = o
            else:
                res = o
                lprefix = len(prefix)
            if res is not None and res != empty_set:
                return res, lprefix
        return set(), lprefix
