# -*- coding: utf-8 -*-
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
import string
import ctypes
import builtins
import subprocess
import threading
import traceback
from warnings import warn
from contextlib import contextmanager
from collections import OrderedDict, Sequence, Set

# adding further imports from xonsh modules is discouraged to avoid cirular
# dependencies
from xonsh.platform import (has_prompt_toolkit, win_unicode_console,
                            DEFAULT_ENCODING, ON_LINUX, ON_WINDOWS)

if has_prompt_toolkit():
    import prompt_toolkit
else:
    prompt_toolkit = None


IS_SUPERUSER = ctypes.windll.shell32.IsUserAnAdmin() != 0 if ON_WINDOWS else os.getuid() == 0


class XonshError(Exception):
    pass


class DefaultNotGivenType(object):
    """Singleton for representing when no default value is given."""


DefaultNotGiven = DefaultNotGivenType()

BEG_TOK_SKIPS = frozenset(['WS', 'INDENT', 'NOT', 'LPAREN'])
END_TOK_TYPES = frozenset(['SEMI', 'AND', 'OR', 'RPAREN'])
LPARENS = frozenset(['LPAREN', 'AT_LPAREN', 'BANG_LPAREN', 'DOLLAR_LPAREN'])

def _is_not_lparen_and_rparen(lparens, rtok):
    """Tests if an RPAREN token is matched with something other than a plain old
    LPAREN type.
    """
    # note that any([]) is False, so this covers len(lparens) == 0
    return rtok.type == 'RPAREN' and any(x != 'LPAREN' for x in lparens)


def subproc_toks(line, mincol=-1, maxcol=None, lexer=None, returnline=False):
    """Excapsulates tokens in a source code line in a uncaptured
    subprocess ![] starting at a minimum column. If there are no tokens
    (ie in a comment line) this returns None.
    """
    if lexer is None:
        lexer = builtins.__xonsh_execer__.parser.lexer
    if maxcol is None:
        maxcol = len(line) + 1
    lexer.reset()
    lexer.input(line)
    toks = []
    lparens = []
    end_offset = 0
    for tok in lexer:
        pos = tok.lexpos
        if tok.type not in END_TOK_TYPES and pos >= maxcol:
            break
        if tok.type in LPARENS:
            lparens.append(tok.type)
        if len(toks) == 0 and tok.type in BEG_TOK_SKIPS:
            continue  # handle indentation
        elif len(toks) > 0 and toks[-1].type in END_TOK_TYPES:
            if _is_not_lparen_and_rparen(lparens, toks[-1]):
                lparens.pop()  # don't continue or break
            elif pos < maxcol and tok.type not in ('NEWLINE', 'DEDENT', 'WS'):
                toks.clear()
                if tok.type in BEG_TOK_SKIPS:
                    continue
            else:
                break
        if pos < mincol:
            continue
        toks.append(tok)
        if tok.type == 'NEWLINE':
            break
        elif tok.type == 'DEDENT':
            # fake a newline when dedenting without a newline
            tok.type = 'NEWLINE'
            tok.value = '\n'
            tok.lineno -= 1
            if len(toks) >= 2:
                prev_tok_end = toks[-2].lexpos + len(toks[-2].value)
            else:
                prev_tok_end = len(line)
            if '#' in line[prev_tok_end:]:
                tok.lexpos = prev_tok_end  # prevents wrapping comments
            else:
                tok.lexpos = len(line)
            break
    else:
        if len(toks) > 0 and toks[-1].type in END_TOK_TYPES:
            if _is_not_lparen_and_rparen(lparens, toks[-1]):
                pass
            else:
                toks.pop()
        if len(toks) == 0:
            return  # handle comment lines
        tok = toks[-1]
        pos = tok.lexpos
        if isinstance(tok.value, str):
            end_offset = len(tok.value.rstrip())
        else:
            el = line[pos:].split('#')[0].rstrip()
            end_offset = len(el)
    if len(toks) == 0:
        return  # handle comment lines
    beg, end = toks[0].lexpos, (toks[-1].lexpos + end_offset)
    end = len(line[:end].rstrip())
    rtn = '![' + line[beg:end] + ']'
    if returnline:
        rtn = line[:beg] + rtn + line[end:]
    return rtn


def subexpr_from_unbalanced(expr, ltok, rtok):
    """Attempts to pull out a valid subexpression for unbalanced grouping,
    based on opening tokens, eg. '(', and closing tokens, eg. ')'.  This
    does not do full tokenization, but should be good enough for tab
    completion.
    """
    lcnt = expr.count(ltok)
    if lcnt == 0:
        return expr
    rcnt = expr.count(rtok)
    if lcnt == rcnt:
        return expr
    subexpr = expr.rsplit(ltok, 1)[-1]
    subexpr = subexpr.rsplit(',', 1)[-1]
    subexpr = subexpr.rsplit(':', 1)[-1]
    return subexpr


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
    except Exception:  # pylint:disable=bare-except
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
    ind = '\t' * ntabs + ' ' * nspaces
    if flatten:
        pat = re.compile(r'^\s*', re.MULTILINE)
    else:
        pat = re.compile(r'^', re.MULTILINE)
    outstr = re.sub(pat, ind, instr)
    if outstr.endswith(os.linesep + ind):
        return outstr[:-len(ind)]
    else:
        return outstr

def get_sep():
    """ Returns the appropriate filepath separator char depending on OS and
    xonsh options set
    """
    return (os.altsep if ON_WINDOWS
            and builtins.__xonsh_env__.get('FORCE_POSIX_PATHS') else
            os.sep)



def fallback(cond, backup):
    """Decorator for returning the object if cond is true and a backup if cond is false.
    """
    def dec(obj):
        return obj if cond else backup
    return dec


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


def command_not_found(cmd):
    """Uses the debian/ubuntu command-not-found utility to suggest packages for a
    command that cannot currently be found.
    """
    if not ON_LINUX:
        return ''
    elif not os.path.isfile('/usr/lib/command-not-found'):
        # utility is not on PATH
        return ''
    c = '/usr/lib/command-not-found {0}; exit 0'
    s = subprocess.check_output(c.format(cmd), universal_newlines=True,
                                stderr=subprocess.STDOUT, shell=True)
    s = '\n'.join(s.splitlines()[:-1]).strip()
    return s


def suggest_commands(cmd, env, aliases):
    """Suggests alternative commands given an environment and aliases."""
    suggest_cmds = env.get('SUGGEST_COMMANDS')
    if not suggest_cmds:
        return
    thresh = env.get('SUGGEST_THRESHOLD')
    max_sugg = env.get('SUGGEST_MAX_NUM')
    if max_sugg < 0:
        max_sugg = float('inf')

    cmd = cmd.lower()
    suggested = {}
    for a in builtins.aliases:
        if a not in suggested:
            if levenshtein(a.lower(), cmd, thresh) < thresh:
                suggested[a] = 'Alias'

    for d in filter(os.path.isdir, env.get('PATH')):
        for f in os.listdir(d):
            if f not in suggested:
                if levenshtein(f.lower(), cmd, thresh) < thresh:
                    fname = os.path.join(d, f)
                    suggested[f] = 'Command ({0})'.format(fname)
    suggested = OrderedDict(
        sorted(suggested.items(),
               key=lambda x: suggestion_sort_helper(x[0].lower(), cmd)))
    num = min(len(suggested), max_sugg)

    if num == 0:
        rtn = command_not_found(cmd)
    else:
        oneof = '' if num == 1 else 'one of '
        tips = 'Did you mean {}the following?'.format(oneof)
        items = list(suggested.popitem(False) for _ in range(num))
        length = max(len(key) for key, _ in items) + 2
        alternatives = '\n'.join('    {: <{}} {}'.format(key + ":", length, val)
                                 for key, val in items)
        rtn = '{}\n{}'.format(tips, alternatives)
        c = command_not_found(cmd)
        rtn += ('\n\n' + c) if len(c) > 0 else ''
    return rtn


def print_exception():
    """Print exceptions with/without traceback."""
    env = getattr(builtins, '__xonsh_env__', os.environ)
    if 'XONSH_SHOW_TRACEBACK' not in env:
        sys.stderr.write('xonsh: For full traceback set: '
                         '$XONSH_SHOW_TRACEBACK = True\n')
    if env.get('XONSH_SHOW_TRACEBACK', False):
        traceback.print_exc()
    else:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exception_only = traceback.format_exception_only(exc_type, exc_value)
        sys.stderr.write(''.join(exception_only))


# Modified from Public Domain code, by Magnus Lie Hetland
# from http://hetland.org/coding/python/levenshtein.py
def levenshtein(a, b, max_dist=float('inf')):
    """Calculates the Levenshtein distance between a and b."""
    n, m = len(a), len(b)
    if abs(n - m) > max_dist:
        return float('inf')
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a, b = b, a
        n, m = m, n
    current = range(n + 1)
    for i in range(1, m + 1):
        previous, current = current, [i] + [0] * n
        for j in range(1, n + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if a[j - 1] != b[i - 1]:
                change = change + 1
            current[j] = min(add, delete, change)
    return current[n]


def suggestion_sort_helper(x, y):
    """Returns a score (lower is better) for x based on how similar
    it is to y.  Used to rank suggestions."""
    x = x.lower()
    y = y.lower()
    lendiff = len(x) + len(y)
    inx = len([i for i in x if i not in y])
    iny = len([i for i in y if i not in x])
    return lendiff + inx + iny


def escape_windows_cmd_string(s):
    """Returns a string that is usable by the Windows cmd.exe.
    The escaping is based on details here and emperical testing:
    http://www.robvanderwoude.com/escapechars.php
    """
    for c in '()%!^<>&|"':
        s = s.replace(c, '^' + c)
    s = s.replace('/?', '/.')
    return s


def argvquote(arg, force=False):
    """ Returns an argument quoted in such a way that that CommandLineToArgvW
    on Windows will return the argument string unchanged.
    This is the same thing Popen does when supplied with an list of arguments.
    Arguments in a command line should be separated by spaces; this
    function does not add these spaces. This implementation follows the
    suggestions outlined here:
    https://blogs.msdn.microsoft.com/twistylittlepassagesallalike/2011/04/23/everyone-quotes-command-line-arguments-the-wrong-way/
    """
    if not force and len(arg) != 0 and not any([c in arg for c in ' \t\n\v"']):
        return arg
    else:
        n_backslashes = 0
        cmdline = '"'
        for c in arg:
            if c == '"':
                cmdline += (n_backslashes * 2 + 1) * '\\'
            else:
                cmdline += n_backslashes * '\\'
            if c != '\\':
                cmdline += c
                n_backslashes = 0
            else:
                n_backslashes += 1
        return cmdline + n_backslashes * 2 * '\\' + '"'


def on_main_thread():
    """Checks if we are on the main thread or not."""
    return threading.current_thread() is threading.main_thread()


@contextmanager
def swap(namespace, name, value, default=NotImplemented):
    """Swaps a current variable name in a namespace for another value, and then
    replaces it when the context is exited.
    """
    old = getattr(namespace, name, default)
    setattr(namespace, name, value)
    yield value
    if old is default:
        delattr(namespace, name)
    else:
        setattr(namespace, name, old)

#
# Validators and contervers
#


def is_int(x):
    """Tests if something is an integer"""
    return isinstance(x, int)


def is_float(x):
    """Tests if something is a float"""
    return isinstance(x, float)


def is_string(x):
    """Tests if something is a string"""
    return isinstance(x, str)


def always_true(x):
    """Returns True"""
    return True


def always_false(x):
    """Returns False"""
    return False


def ensure_string(x):
    """Returns a string if x is not a string, and x if it already is."""
    return str(x)


def is_env_path(x):
    """This tests if something is an environment path, ie a list of strings."""
    if isinstance(x, str):
        return False
    else:
        return (isinstance(x, Sequence) and
                all(isinstance(a, str) for a in x))


def str_to_env_path(x):
    """Converts a string to an environment path, ie a list of strings,
    splitting on the OS separator.
    """
    return x.split(os.pathsep)


def env_path_to_str(x):
    """Converts an environment path to a string by joining on the OS separator."""
    return os.pathsep.join(x)


def is_bool(x):
    """Tests if something is a boolean."""
    return isinstance(x, bool)


_FALSES = frozenset(['', '0', 'n', 'f', 'no', 'none', 'false'])

def to_bool(x):
    """"Converts to a boolean in a semantically meaningful way."""
    if isinstance(x, bool):
        return x
    elif isinstance(x, str):
        return False if x.lower() in _FALSES else True
    else:
        return bool(x)


def bool_to_str(x):
    """Converts a bool to an empty string if False and the string '1' if True."""
    return '1' if x else ''


_BREAKS = frozenset(['b', 'break', 's', 'skip', 'q', 'quit'])


def to_bool_or_break(x):
    if isinstance(x, str) and x.lower() in _BREAKS:
        return 'break'
    else:
        return to_bool(x)


def ensure_int_or_slice(x):
    """Makes sure that x is list-indexable."""
    if x is None:
        return slice(None)
    elif is_int(x):
        return x
    # must have a string from here on
    if ':' in x:
        x = x.strip('[]()')
        return slice(*(int(x) if len(x) > 0 else None for x in x.split(':')))
    else:
        return int(x)


def is_string_set(x):
    """Tests if something is a set"""
    return (isinstance(x, Set) and
            all(isinstance(a, str) for a in x))


def csv_to_set(x):
    """Convert a comma-separated list of strings to a set of strings."""
    if not x:
        return set()
    else:
        return set(x.split(','))


def set_to_csv(x):
    """Convert a set of strings to a comma-separated list of strings."""
    return ','.join(x)


def is_bool_seq(x):
    """Tests if an object is a sequence of bools."""
    return isinstance(x, Sequence) and all(isinstance(y, bool) for y in x)


def csv_to_bool_seq(x):
    """Takes a comma-separated string and converts it into a list of bools."""
    return [to_bool(y) for y in csv_to_set(x)]


def bool_seq_to_csv(x):
    """Converts a sequence of bools to a comma-separated string."""
    return ','.join(map(str, x))


def is_completions_display_value(x):
    return x in {'none', 'single', 'multi'}


def to_completions_display_value(x):
    x = str(x).lower()
    if x in {'none', 'false'}:
        x = 'none'
    elif x in {'multi', 'true'}:
        x = 'multi'
    elif x == 'single':
        pass
    else:
        warn('"{}" is not a valid value for $COMPLETIONS_DISPLAY. '.format(x) +
             'Using "multi".', RuntimeWarning)
        x = 'multi'
    return x


def setup_win_unicode_console(enable):
    """"Enables or disables unicode display on windows."""
    enable = to_bool(enable)
    if ON_WINDOWS and win_unicode_console:
        if enable:
            win_unicode_console.enable()
        else:
            win_unicode_console.disable()
    return enable

# history validation

_min_to_sec = lambda x: 60.0 * float(x)
_hour_to_sec = lambda x: 60.0 * _min_to_sec(x)
_day_to_sec = lambda x: 24.0 * _hour_to_sec(x)
_month_to_sec = lambda x: 30.4375 * _day_to_sec(x)
_year_to_sec = lambda x: 365.25 * _day_to_sec(x)
_kb_to_b = lambda x: 1024 * int(x)
_mb_to_b = lambda x: 1024 * _kb_to_b(x)
_gb_to_b = lambda x: 1024 * _mb_to_b(x)
_tb_to_b = lambda x: 1024 * _tb_to_b(x)

CANON_HISTORY_UNITS = frozenset(['commands', 'files', 's', 'b'])

HISTORY_UNITS = {
    '': ('commands', int),
    'c': ('commands', int),
    'cmd': ('commands', int),
    'cmds': ('commands', int),
    'command': ('commands', int),
    'commands': ('commands', int),
    'f': ('files', int),
    'files': ('files', int),
    's': ('s', float),
    'sec': ('s', float),
    'second': ('s', float),
    'seconds': ('s', float),
    'm': ('s', _min_to_sec),
    'min': ('s', _min_to_sec),
    'mins': ('s', _min_to_sec),
    'h': ('s', _hour_to_sec),
    'hr': ('s', _hour_to_sec),
    'hour': ('s', _hour_to_sec),
    'hours': ('s', _hour_to_sec),
    'd': ('s', _day_to_sec),
    'day': ('s', _day_to_sec),
    'days': ('s', _day_to_sec),
    'mon': ('s', _month_to_sec),
    'month': ('s', _month_to_sec),
    'months': ('s', _month_to_sec),
    'y': ('s', _year_to_sec),
    'yr': ('s', _year_to_sec),
    'yrs': ('s', _year_to_sec),
    'year': ('s', _year_to_sec),
    'years': ('s', _year_to_sec),
    'b': ('b', int),
    'byte': ('b', int),
    'bytes': ('b', int),
    'kb': ('b', _kb_to_b),
    'kilobyte': ('b', _kb_to_b),
    'kilobytes': ('b', _kb_to_b),
    'mb': ('b', _mb_to_b),
    'meg': ('b', _mb_to_b),
    'megs': ('b', _mb_to_b),
    'megabyte': ('b', _mb_to_b),
    'megabytes': ('b', _mb_to_b),
    'gb': ('b', _gb_to_b),
    'gig': ('b', _gb_to_b),
    'gigs': ('b', _gb_to_b),
    'gigabyte': ('b', _gb_to_b),
    'gigabytes': ('b', _gb_to_b),
    'tb': ('b', _tb_to_b),
    'terabyte': ('b', _tb_to_b),
    'terabytes': ('b', _tb_to_b),
    }
"""Maps lowercase unit names to canonical name and conversion utilities."""

def is_history_tuple(x):
    """Tests if something is a proper history value, units tuple."""
    if isinstance(x, Sequence) and len(x) == 2 and isinstance(x[0], (int, float)) \
                               and x[1].lower() in CANON_HISTORY_UNITS:
         return True
    return False


RE_HISTORY_TUPLE = re.compile('([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)\s*([A-Za-z]*)')

def to_history_tuple(x):
    """Converts to a canonincal history tuple."""
    if not isinstance(x, (Sequence, float, int)):
        raise ValueError('history size must be given as a sequence or number')
    if isinstance(x, str):
        m = RE_HISTORY_TUPLE.match(x.strip().lower())
        return to_history_tuple((m.group(1), m.group(3)))
    elif isinstance(x, (float, int)):
        return to_history_tuple((x, 'commands'))
    units, converter = HISTORY_UNITS[x[1]]
    value = converter(x[0])
    return (value, units)


def history_tuple_to_str(x):
    """Converts a valid history tuple to a canonical string."""
    return '{0} {1}'.format(*x)


def format_color(string, **kwargs):
    """Formats strings that may contain colors. This simply dispatches to the
    shell instances method of the same name. The results of this function should
    be directly usable by print_color().
    """
    return builtins.__xonsh_shell__.shell.format_color(string, **kwargs)


def print_color(string, **kwargs):
    """Prints a string that may contain colors. This dispatched to the shell
    method of the same name. Colors will be formatted if they have not already
    been.
    """
    builtins.__xonsh_shell__.shell.print_color(string, **kwargs)


def color_style_names():
    """Returns an iterable of all available style names."""
    return builtins.__xonsh_shell__.shell.color_style_names()


def color_style():
    """Returns the current color map."""
    return builtins.__xonsh_shell__.shell.color_style()


def _get_color_indexes(style_map):
    """ Generates the color and windows color index for a style """
    table = prompt_toolkit.terminal.win32_output.ColorLookupTable()
    pt_style = prompt_toolkit.styles.style_from_dict(style_map)
    for token in style_map:
        attr = pt_style.token_to_attrs[token]
        if attr.color is not None:
            index = table.lookup_color(attr.color, attr.bgcolor)
            try:
                rgb = (int(attr.color[0:2], 16),
                       int(attr.color[2:4], 16),
                       int(attr.color[4:6], 16))
            except:
                rgb = None
            yield token, index, rgb


def intensify_colors_for_cmd_exe(style_map, replace_colors=None):
    """Returns a modified style to where colors that maps to dark
       colors are replaced with brighter versions. Also expands the
       range used by the gray colors
    """
    modified_style = {}
    if not ON_WINDOWS or prompt_toolkit is None:
        return modified_style
    if replace_colors is None:
        replace_colors = {1: '#44ffff',  # subst blue with bright cyan
                          2: '#44ff44',  # subst green with bright green
                          4: '#ff4444',  # subst red with bright red
                          5: '#ff44ff',  # subst magenta with bright magenta
                          6: '#ffff44',  # subst yellow with bright yellow
                          9: '#00aaaa',  # subst intense blue (hard to read)
                                         # with dark cyan (which is readable)
                          }
    for token, idx, _ in _get_color_indexes(style_map):
        if idx in replace_colors:
            modified_style[token] = replace_colors[idx]
    return modified_style


def expand_gray_colors_for_cmd_exe(style_map):
    """ Expand the style's gray scale color range.
        All gray scale colors has a tendency to map to the same default GRAY
        in cmd.exe.
    """
    modified_style = {}
    if not ON_WINDOWS or prompt_toolkit is None:
        return modified_style
    for token, idx, rgb in _get_color_indexes(style_map):
        if idx == 7 and rgb:
            if sum(rgb) <= 306:
                # Equal and below '#666666 is reset to dark gray
                modified_style[token] = '#444444'
            elif sum(rgb) >= 408:
                # Equal and above 0x888888 is reset to white
                modified_style[token] = '#ffffff'
    return modified_style


def intensify_colors_on_win_setter(enable):
    """ Resets the style when setting the INTENSIFY_COLORS_ON_WIN
        environment variable. """
    enable = to_bool(enable)
    delattr(builtins.__xonsh_shell__.shell.styler, 'style_name')
    return enable


_RE_STRING_START = "[bBrRuU]*"
_RE_STRING_TRIPLE_DOUBLE = '"""'
_RE_STRING_TRIPLE_SINGLE = "'''"
_RE_STRING_DOUBLE = '"'
_RE_STRING_SINGLE = "'"
_STRINGS = (_RE_STRING_TRIPLE_DOUBLE,
            _RE_STRING_TRIPLE_SINGLE,
            _RE_STRING_DOUBLE,
            _RE_STRING_SINGLE)
RE_BEGIN_STRING = re.compile("(" + _RE_STRING_START +
                             '(' + "|".join(_STRINGS) +
                             '))')
"""Regular expression matching the start of a string, including quotes and
leading characters (r, b, or u)"""

RE_STRING_START = re.compile(_RE_STRING_START)
"""Regular expression matching the characters before the quotes when starting a
string (r, b, or u, case insensitive)"""

RE_STRING_CONT = {k: re.compile(v) for k,v in {
    '"': r'((\\(.|\n))|([^"\\]))*',
    "'": r"((\\(.|\n))|([^'\\]))*",
    '"""': r'((\\(.|\n))|([^"\\])|("(?!""))|\n)*',
    "'''": r"((\\(.|\n))|([^'\\])|('(?!''))|\n)*",
}.items()}
"""Dictionary mapping starting quote sequences to regular expressions that
match the contents of a string beginning with those quotes (not including the
terminating quotes)"""


def check_for_partial_string(x):
    """
    Returns the starting index (inclusive), ending index (exclusive), and
    starting quote string of the most recent Python string found in the input.

    check_for_partial_string(x) -> (startix, endix, quote)

    Parameters
    ----------
    x : str
        The string to be checked (representing a line of terminal input)

    Returns
    -------
    startix : int (or None)
        The index where the most recent Python string found started
        (inclusive), or None if no strings exist in the input

    endix : int (or None)
        The index where the most recent Python string found ended (exclusive),
        or None if no strings exist in the input OR if the input ended in the
        middle of a Python string

    quote : str (or None)
        A string containing the quote used to start the string (e.g., b", ",
        '''), or None if no string was found.
    """
    string_indices = []
    starting_quote = []
    current_index = 0
    match = re.search(RE_BEGIN_STRING, x)
    while match is not None:
        # add the start in
        start = match.start()
        quote = match.group(0)
        lenquote = len(quote)
        current_index += start
        # store the starting index of the string, as well as the
        # characters in the starting quotes (e.g., ", ', """, r", etc)
        string_indices.append(current_index)
        starting_quote.append(quote)
        # determine the string that should terminate this string
        ender = re.sub(RE_STRING_START, '', quote)
        x = x[start + lenquote:]
        current_index += lenquote
        # figure out what is inside the string
        continuer = RE_STRING_CONT[ender]
        contents = re.match(continuer, x)
        inside = contents.group(0)
        leninside = len(inside)
        current_index += contents.start() + leninside + len(ender)
        # if we are not at the end of the input string, add the ending index of
        # the string to string_indices
        if contents.end() < len(x):
            string_indices.append(current_index)
        x = x[leninside + len(ender):]
        # find the next match
        match = re.search(RE_BEGIN_STRING, x)
    numquotes = len(string_indices)
    if numquotes == 0:
        return (None, None, None)
    elif numquotes % 2:
        return (string_indices[-1], None, starting_quote[-1])
    else:
        return (string_indices[-2], string_indices[-1], starting_quote[-1])


# expandvars is a modified version of os.path.expandvars from the Python 3.5.1
# source code (root/Lib/ntpath.py, line 353)

def _is_in_env(name):
    ENV = builtins.__xonsh_env__
    return name in ENV._d or name in ENV.defaults

def _get_env_string(name):
    ENV = builtins.__xonsh_env__
    value = ENV.get(name)
    ensurer = ENV.get_ensurer(name)
    if ensurer.detype is bool_to_str:
        value = ensure_string(value)
    else:
        value = ensurer.detype(value)
    return value


def expandvars(path):
    """Expand shell variables of the forms $var, ${var} and %var%.

    Unknown variables are left unchanged."""
    ENV = builtins.__xonsh_env__
    if isinstance(path, bytes):
        path = path.decode(encoding=ENV.get('XONSH_ENCODING'),
                           errors=ENV.get('XONSH_ENCODING_ERRORS'))
    if '$' not in path and (not ON_WINDOWS or '%' not in path):
        return path
    varchars = string.ascii_letters + string.digits + '_-'
    quote = '\''
    percent = '%'
    brace = '{'
    rbrace = '}'
    dollar = '$'
    res = path[:0]
    index = 0
    pathlen = len(path)
    while index < pathlen:
        c = path[index:index+1]
        if c == quote:   # no expansion within single quotes
            path = path[index + 1:]
            pathlen = len(path)
            try:
                index = path.index(c)
                res += c + path[:index + 1]
            except ValueError:
                res += c + path
                index = pathlen - 1
        elif c == percent and ON_WINDOWS:  # variable or '%'
            if path[index + 1:index + 2] == percent:
                res += c
                index += 1
            else:
                path = path[index+1:]
                pathlen = len(path)
                try:
                    index = path.index(percent)
                except ValueError:
                    res += percent + path
                    index = pathlen - 1
                else:
                    var = path[:index]
                    if _is_in_env(var):
                        value = _get_env_string(var)
                    else:
                        value = percent + var + percent
                    res += value
        elif c == dollar:  # variable or '$$'
            if path[index + 1:index + 2] == dollar:
                res += c
                index += 1
            elif path[index + 1:index + 2] == brace:
                path = path[index+2:]
                pathlen = len(path)
                try:
                    index = path.index(rbrace)
                except ValueError:
                    res += dollar + brace + path
                    index = pathlen - 1
                else:
                    var = path[:index]
                    try:
                        var = eval(var, builtins.__xonsh_ctx__)
                        if _is_in_env(var):
                            value = _get_env_string(var)
                        elif var is Ellipsis:
                            value = dollar + brace + '...' + rbrace
                        else:
                            value = dollar + brace + var + rbrace
                    except:
                        value = dollar + brace + var + rbrace
                    res += value
            else:
                var = path[:0]
                index += 1
                c = path[index:index + 1]
                while c and c in varchars:
                    var += c
                    index += 1
                    c = path[index:index + 1]
                if _is_in_env(var):
                    value = _get_env_string(var)
                else:
                    value = dollar + var
                res += value
                if c:
                    index -= 1
        else:
            res += c
        index += 1
    return res

#
# File handling tools
#

def backup_file(fname):
    """Moves an existing file to a new name that has the current time right
    before the extension.
    """
    # lazy imports
    import shutil
    from datetime import datetime
    base, ext = os.path.splitext(fname)
    newfname = base + '.' + datetime.now().isoformat() + ext
    shutil.move(fname, newfname)


def normabspath(p):
    """Retuns as normalized absolute path, namely, normcase(abspath(p))"""
    return os.path.normcase(os.path.abspath(p))


class CommandsCache(Set):
    """A lazy cache representing the commands available on the file system."""

    def __init__(self):
        self._cmds_cache = frozenset()
        self._path_checksum = None
        self._alias_checksum = None
        self._path_mtime = -1

    def __contains__(self, item):
        return item in self.all_commands

    def __iter__(self):
        return iter(self.all_commands)

    def __len__(self):
        return len(self.all_commands)

    @property
    def all_commands(self):
        paths = builtins.__xonsh_env__.get('PATH', [])
        paths = frozenset(x for x in paths if os.path.isdir(x))
        # did PATH change?
        path_hash = hash(paths)
        cache_valid = path_hash == self._path_checksum
        self._path_checksum = path_hash
        # did aliases change?
        al_hash = hash(frozenset(builtins.aliases))
        cache_valid = cache_valid and al_hash == self._alias_checksum
        self._alias_checksum = al_hash
        # did the contents of any directory in PATH change?
        max_mtime = 0
        for path in paths:
            mtime = os.stat(path).st_mtime
            if mtime > max_mtime:
                max_mtime = mtime
        cache_valid = cache_valid and max_mtime > self._path_mtime
        self._path_mtime = max_mtime
        if cache_valid:
            return self._cmds_cache
        allcmds = set()
        for path in paths:
            allcmds |= set(x for x in os.listdir(path)
                           if os.path.isfile(x) and os.access(x, os.X_OK))
            allcmds |= set(builtins.aliases)
        self._cmds_cache = frozenset(allcmds)
        return self._cmds_cache
