"""Misc. xonsh tools.

The following implementations were forked from the IPython project:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>

Implementations:

* decode()
* encode()
* cast_unicode()
* safe_hasattr()
* indent()

"""
import os
import re
import sys
import builtins
from collections import OrderedDict


if sys.version_info[0] >= 3:
    string_types = (str, bytes)
    unicode_type = str
else:
    string_types = (str, unicode)
    unicode_type = unicode

DEFAULT_ENCODING = sys.getdefaultencoding()

def subproc_toks(line, mincol=-1, maxcol=None, lexer=None, returnline=False):
    """Excapsulates tokens in a source code line in a uncaptured 
    subprocess $[] starting at a minimum column. If there are no tokens 
    (ie in a comment line) this returns None.
    """
    if lexer is None:
        lexer = builtins.__xonsh_execer__.parser.lexer
    if maxcol is None:
        maxcol = len(line) + 1
    lexer.reset()
    lexer.input(line)
    toks = []
    end_offset = 0
    for tok in lexer:
        pos = tok.lexpos
        if tok.type != 'SEMI' and pos >= maxcol:
            break
        if len(toks) > 0 and toks[-1].type == 'SEMI':
            toks.clear()
        if pos < mincol:
            continue
        toks.append(tok)
        if tok.type == 'NEWLINE':
            break
    else:
        if len(toks) == 0:
            return  # handle comment lines
        if toks[-1].type == 'SEMI':
            toks.pop()
        tok = toks[-1]
        pos = tok.lexpos
        if isinstance(tok.value, string_types):
            end_offset = len(tok.value)
        else:
            el = line[pos:].split('#')[0].rstrip()
            end_offset = len(el)
    if len(toks) == 0:
        return  # handle comment lines
    beg, end = toks[0].lexpos, (toks[-1].lexpos + end_offset)
    rtn = '$[' + line[beg:end] + ']'
    if returnline:
        rtn = line[:beg] + rtn + line[end:]
    return rtn

def decode(s, encoding=None):
    encoding = encoding or DEFAULT_ENCODING
    return s.decode(encoding, "replace")

def encode(u, encoding=None):
    encoding = encoding or DEFAULT_ENCODING
    return u.encode(encoding, "replace")

def cast_unicode(s, encoding=None):
    if isinstance(s, bytes):
        return decode(s, encoding)
    return s

def safe_hasattr(obj, attr):
    """In recent versions of Python, hasattr() only catches AttributeError.
    This catches all errors.
    """
    try:
        getattr(obj, attr)
        return True
    except:
        return False

def indent(instr, nspaces=4, ntabs=0, flatten=False):
    """Indent a string a given number of spaces or tabstops.

    indent(str,nspaces=4,ntabs=0) -> indent str by ntabs+nspaces.

    Parameters
    ----------
    instr : basestring
        The string to be indented.
    nspaces : int (default: 4)
        The number of spaces to be indented.
    ntabs : int (default: 0)
        The number of tabs to be indented.
    flatten : bool (default: False)
        Whether to scrub existing indentation.  If True, all lines will be
        aligned to the same indentation.  If False, existing indentation will
        be strictly increased.

    Returns
    -------
    outstr : string indented by ntabs and nspaces.

    """
    if instr is None:
        return
    ind = '\t'*ntabs+' '*nspaces
    if flatten:
        pat = re.compile(r'^\s*', re.MULTILINE)
    else:
        pat = re.compile(r'^', re.MULTILINE)
    outstr = re.sub(pat, ind, instr)
    if outstr.endswith(os.linesep+ind):
        return outstr[:-len(ind)]
    else:
        return outstr


TERM_COLORS = {
    # Reset
    'NO_COLOR': '\001\033[0m\002',       # Text Reset
    # Regular Colors
    'BLACK': '\033[0;30m\002',        # BLACK
    'RED': '\001\033[0;31m\002',          # RED
    'GREEN': '\001\033[0;32m\002',        # GREEN
    'YELLOW': '\001\033[0;33m\002',       # YELLOW
    'BLUE': '\001\033[0;34m\002',         # BLUE
    'PURPLE': '\001\033[0;35m\002',       # PURPLE
    'CYAN': '\001\033[0;36m\002',         # CYAN
    'WHITE': '\001\033[0;37m\002',        # WHITE
    # Bold
    'BOLD_BLACK': '\001\033[1;30m\002',       # BLACK
    'BOLD_RED': '\001\033[1;31m\002',         # RED
    'BOLD_GREEN': '\001\033[1;32m\002',       # GREEN
    'BOLD_YELLOW': '\001\033[1;33m\002',      # YELLOW
    'BOLD_BLUE': '\001\033[1;34m\002',        # BLUE
    'BOLD_PURPLE': '\001\033[1;35m\002',      # PURPLE
    'BOLD_CYAN': '\001\033[1;36m\002',        # CYAN
    'BOLD_WHITE': '\001\033[1;37m\002',       # WHITE
    # Underline
    'UNDERLINE_BLACK': '\001\033[4;30m\002',       # BLACK
    'UNDERLINE_RED': '\001\033[4;31m\002',         # RED
    'UNDERLINE_GREEN': '\001\033[4;32m\002',       # GREEN
    'UNDERLINE_YELLOW': '\001\033[4;33m\002',      # YELLOW
    'UNDERLINE_BLUE': '\001\033[4;34m\002',        # BLUE
    'UNDERLINE_PURPLE': '\001\033[4;35m\002',      # PURPLE
    'UNDERLINE_CYAN': '\001\033[4;36m\002',        # CYAN
    'UNDERLINE_WHITE': '\001\033[4;37m\002',       # WHITE
    # Background
    'BACKGROUND_BLACK': '\001\033[40m\002',       # BLACK
    'BACKGROUND_RED': '\001\033[41m\002',         # RED
    'BACKGROUND_GREEN': '\001\033[42m\002',       # GREEN
    'BACKGROUND_YELLOW': '\001\033[43m\002',      # YELLOW
    'BACKGROUND_BLUE': '\001\033[44m\002',        # BLUE
    'BACKGROUND_PURPLE': '\001\033[45m\002',      # PURPLE
    'BACKGROUND_CYAN': '\001\033[46m\002',        # CYAN
    'BACKGROUND_WHITE': '\001\033[47m\002',       # WHITE
    # High Intensity
    'INTENSE_BLACK': '\001\033[0;90m\002',       # BLACK
    'INTENSE_RED': '\001\033[0;91m\002',         # RED
    'INTENSE_GREEN': '\001\033[0;92m\002',       # GREEN
    'INTENSE_YELLOW': '\001\033[0;93m\002',      # YELLOW
    'INTENSE_BLUE': '\001\033[0;94m\002',        # BLUE
    'INTENSE_PURPLE': '\001\033[0;95m\002',      # PURPLE
    'INTENSE_CYAN': '\001\033[0;96m\002',        # CYAN
    'INTENSE_WHITE': '\001\033[0;97m\002',       # WHITE
    # Bold High Intensity
    'BOLD_INTENSE_BLACK': '\001\033[1;90m\002',      # BLACK
    'BOLD_INTENSE_RED': '\001\033[1;91m\002',        # RED
    'BOLD_INTENSE_GREEN': '\001\033[1;92m\002',      # GREEN
    'BOLD_INTENSE_YELLOW': '\001\033[1;93m\002',     # YELLOW
    'BOLD_INTENSE_BLUE': '\001\033[1;94m\002',       # BLUE
    'BOLD_INTENSE_PURPLE': '\001\033[1;95m\002',     # PURPLE
    'BOLD_INTENSE_CYAN': '\001\033[1;96m\002',       # CYAN
    'BOLD_INTENSE_WHITE': '\001\033[1;97m\002',      # WHITE
    # High Intensity backgrounds
    'BACKGROUND_INTENSE_BLACK': '\001\033[0;100m\002',   # BLACK
    'BACKGROUND_INTENSE_RED': '\001\033[0;101m\002',     # RED
    'BACKGROUND_INTENSE_GREEN': '\001\033[0;102m\002',   # GREEN
    'BACKGROUND_INTENSE_YELLOW': '\001\033[0;103m\002',  # YELLOW
    'BACKGROUND_INTENSE_BLUE': '\001\033[0;104m\002',    # BLUE
    'BACKGROUND_INTENSE_PURPLE': '\001\033[0;105m\002',  # PURPLE
    'BACKGROUND_INTENSE_CYAN': '\001\033[0;106m\002',    # CYAN
    'BACKGROUND_INTENSE_WHITE': '\001\033[0;107m\002',   # WHITE
    }

# The following redirect classes were taken directly from Python 3.5's source 
# code (from the contextlib module). This can be removed when 3.5 is released, 
# although redirect_stdout exists in 3.4, redirect_stderr does not.
# See the Python software license: https://docs.python.org/3/license.html
# Copyright (c) Python Software Foundation. All rights reserved.
class _RedirectStream:

    _stream = None

    def __init__(self, new_target):
        self._new_target = new_target
        # We use a list of old targets to make this CM re-entrant
        self._old_targets = []

    def __enter__(self):
        self._old_targets.append(getattr(sys, self._stream))
        setattr(sys, self._stream, self._new_target)
        return self._new_target

    def __exit__(self, exctype, excinst, exctb):
        setattr(sys, self._stream, self._old_targets.pop())


class redirect_stdout(_RedirectStream):
    """Context manager for temporarily redirecting stdout to another file::

        # How to send help() to stderr
        with redirect_stdout(sys.stderr):
            help(dir)

        # How to write help() to a file
        with open('help.txt', 'w') as f:
            with redirect_stdout(f):
                help(pow)

    Mostly for backwards compatibility. 
    """
    _stream = "stdout"


class redirect_stderr(_RedirectStream):
    """Context manager for temporarily redirecting stderr to another file."""
    _stream = "stderr"

def suggest_commands(cmd, env, aliases):
    """Suggests alternative commands given an environment and aliases."""
    if env.get('SUGGEST_COMMANDS', True):
        threshold = env.get('SUGGEST_THRESHOLD', 3)
        max_sugg = env.get('SUGGEST_MAX_NUM', 5)
        if max_sugg < 0:
            max_sugg = float('inf')

        suggested = {}
        for a in builtins.aliases:
            if a not in suggested and levenshtein(a, cmd, threshold) < threshold:
                suggested[a] = 'Alias'

        for d in filter(os.path.isdir, env.get('PATH', [])):
            for f in os.listdir(d):
                if f not in suggested and levenshtein(f, cmd, threshold) < threshold:
                    fname = os.path.join(d,f)
                    suggested[f] = 'Command ({0})'.format(fname)
        suggested = OrderedDict(sorted(suggested.items(),
                                key=lambda x: suggestion_sort_helper(x[0], cmd)))
        num = min(len(suggested), max_sugg)
        
        if num == 0:
            return ''
        else:
            tips = 'Did you mean {}the following?'.format(
                '' if num == 1 else 'one of ')
            
            items = list(suggested.popitem(False) for _ in range(num))
            length = max(len(key) for key, _ in items) + 2
            alternatives = '\n'.join('    {: <{}} {}'.format(key+":", length, val)
                                     for key, val in items)
            
            return '{}\n{}\n'.format(tips, alternatives)


# Modified from Public Domain code, by Magnus Lie Hetland
# from http://hetland.org/coding/python/levenshtein.py 
def levenshtein(a, b, max_dist=float('inf')):
    """Calculates the Levenshtein distance between a and b."""
    n, m = len(a), len(b)
    
    if abs(n-m) > max_dist:
        return float('inf')

    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a,b = b,a
        n,m = m,n
        
    current = range(n+1)
    for i in range(1,m+1):
        previous, current = current, [i]+[0]*n
        for j in range(1,n+1):
            add, delete = previous[j]+1, current[j-1]+1
            change = previous[j-1]
            if a[j-1] != b[i-1]:
                change = change + 1
            current[j] = min(add, delete, change)
            
    return current[n]

def suggestion_sort_helper(x, y):
    """Sorts two suggestions."""
    x = x.lower()
    y = y.lower()
    lendiff = len(x) + len(y)
    inx = len([i for i in x if i not in y])
    iny = len([i for i in y if i not in x])
    return lendiff + inx + iny
