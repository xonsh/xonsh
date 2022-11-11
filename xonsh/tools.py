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
import ast
import collections
import collections.abc as cabc
import contextlib
import ctypes
import datetime
import functools
import glob
import itertools
import operator
import os
import pathlib
import re
import shlex
import string
import subprocess
import sys
import threading
import traceback
import typing as tp
import warnings

# adding imports from further xonsh modules is discouraged to avoid circular
# dependencies
from xonsh import __version__
from xonsh.lazyasd import LazyDict, LazyObject, lazyobject
from xonsh.platform import (
    DEFAULT_ENCODING,
    HAS_PYGMENTS,
    ON_LINUX,
    ON_WINDOWS,
    expanduser,
    os_environ,
    pygments_version_info,
)


@functools.lru_cache(1)
def is_superuser():
    if ON_WINDOWS:
        rtn = ctypes.windll.shell32.IsUserAnAdmin() != 0
    else:
        rtn = os.getuid() == 0
    return rtn


@lazyobject
def xsh():
    from xonsh.built_ins import XSH

    return XSH


class XonshError(Exception):
    pass


class XonshCalledProcessError(XonshError, subprocess.CalledProcessError):
    """Raised when there's an error with a called process

    Inherits from XonshError and subprocess.CalledProcessError, catching
    either will also catch this error.

    Raised *after* iterating over stdout of a captured command, if the
    returncode of the command is nonzero.

    Example:
    --------
        try:
            for line in !(ls):
                print(line)
        except subprocess.CalledProcessError as error:
            print("Error in process: {}.format(error.completed_command.pid))

    This also handles differences between Python3.4 and 3.5 where
    CalledProcessError is concerned.
    """

    def __init__(
        self, returncode, command, output=None, stderr=None, completed_command=None
    ):
        super().__init__(returncode, command, output)
        self.stderr = stderr
        self.completed_command = completed_command


def expand_path(s, expand_user=True):
    """Takes a string path and expands ~ to home if expand_user is set
    and environment vars if EXPAND_ENV_VARS is set."""
    env = xsh.env or os_environ
    if env.get("EXPAND_ENV_VARS", False):
        s = expandvars(s)
    if expand_user:
        # expand ~ according to Bash unquoted rules "Each variable assignment is
        # checked for unquoted tilde-prefixes immediately following a ':' or the
        # first '='". See the following for more details.
        # https://www.gnu.org/software/bash/manual/html_node/Tilde-Expansion.html
        pre, char, post = s.partition("=")
        if char:
            s = expanduser(pre) + char
            s += os.pathsep.join(map(expanduser, post.split(os.pathsep)))
        else:
            s = expanduser(s)
    return s


def _expandpath(path):
    """Performs environment variable / user expansion on a given path
    if EXPAND_ENV_VARS is set.
    """
    env = xsh.env or os_environ
    expand_user = env.get("EXPAND_ENV_VARS", False)
    return expand_path(path, expand_user=expand_user)


def simple_random_choice(lst):
    """Returns random element from the list with length less than 1 million elements."""
    size = len(lst)
    if size > 1000000:  # microsecond maximum
        raise ValueError("The list is too long.")
    return lst[datetime.datetime.now().microsecond % size]


def decode_bytes(b):
    """Tries to decode the bytes using XONSH_ENCODING if available,
    otherwise using sys.getdefaultencoding().
    """
    env = xsh.env or os_environ
    enc = env.get("XONSH_ENCODING") or DEFAULT_ENCODING
    err = env.get("XONSH_ENCODING_ERRORS") or "strict"
    return b.decode(encoding=enc, errors=err)


def findfirst(s, substrs):
    """Finds whichever of the given substrings occurs first in the given string
    and returns that substring, or returns None if no such strings occur.
    """
    i = len(s)
    result = None
    for substr in substrs:
        pos = s.find(substr)
        if -1 < pos < i:
            i = pos
            result = substr
    return i, result


class EnvPath(cabc.MutableSequence):
    """A class that implements an environment path, which is a list of
    strings. Provides a custom method that expands all paths if the
    relevant env variable has been set.
    """

    def __init__(self, args=None):
        if not args:
            self._l = []
        else:
            if isinstance(args, str):
                self._l = args.split(os.pathsep)
            elif isinstance(args, pathlib.Path):
                self._l = [args]
            elif isinstance(args, bytes):
                # decode bytes to a string and then split based on
                # the default path separator
                self._l = decode_bytes(args).split(os.pathsep)
            elif isinstance(args, cabc.Iterable):
                # put everything in a list -before- performing the type check
                # in order to be able to retrieve it later, for cases such as
                # when a generator expression was passed as an argument
                args = list(args)
                if not all(isinstance(i, (str, bytes, pathlib.Path)) for i in args):
                    # make TypeError's message as informative as possible
                    # when given an invalid initialization sequence
                    raise TypeError(
                        "EnvPath's initialization sequence should only "
                        "contain str, bytes and pathlib.Path entries"
                    )
                self._l = args
            else:
                raise TypeError(
                    "EnvPath cannot be initialized with items "
                    "of type %s" % type(args)
                )

    def __getitem__(self, item):
        # handle slices separately
        if isinstance(item, slice):
            return [_expandpath(i) for i in self._l[item]]
        else:
            return _expandpath(self._l[item])

    def __setitem__(self, index, item):
        self._l.__setitem__(index, item)

    def __len__(self):
        return len(self._l)

    def __delitem__(self, key):
        self._l.__delitem__(key)

    def insert(self, index, value):
        self._l.insert(index, value)

    @property
    def paths(self):
        """
        Returns the list of directories that this EnvPath contains.
        """
        return list(self)

    def __repr__(self):
        return repr(self._l)

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        return all(map(operator.eq, self, other))

    def _repr_pretty_(self, p, cycle):
        """Pretty print path list"""
        if cycle:
            p.text("EnvPath(...)")
        else:
            with p.group(1, "EnvPath(\n[", "]\n)"):
                for idx, item in enumerate(self):
                    if idx:
                        p.text(",")
                        p.breakable()
                    p.pretty(item)

    def __add__(self, other):
        if isinstance(other, EnvPath):
            other = other._l
        return EnvPath(self._l + other)

    def __radd__(self, other):
        if isinstance(other, EnvPath):
            other = other._l
        return EnvPath(other + self._l)

    def add(self, data, front=False, replace=False):
        """Add a value to this EnvPath,

        path.add(data, front=bool, replace=bool) -> ensures that path contains data, with position determined by kwargs

        Parameters
        ----------
        data : string or bytes or pathlib.Path
            value to be added
        front : bool
            whether the value should be added to the front, will be
            ignored if the data already exists in this EnvPath and
            replace is False
            Default : False
        replace : bool
            If True, the value will be removed and added to the
            start or end(depending on the value of front)
            Default : False

        Returns
        -------
        None

        """
        data = str(expand_path(data))
        if data not in self._l:
            self._l.insert(0 if front else len(self._l), data)
        elif replace:
            # https://stackoverflow.com/a/25251306/1621381
            self._l = list(filter(lambda x: x != data, self._l))
            self._l.insert(0 if front else len(self._l), data)


class FlexibleFormatter(string.Formatter):
    """Support nested fields inside conditional formatters

    e.g. template ``{user:| {RED}{}{RESET}}`` will become ``| {RED}user{RESET}`` when user=user.
    """

    def get_value(self, key: "int|str", args, kwargs) -> str:
        if isinstance(key, int):
            return args[key]
        else:
            if key in kwargs:
                return kwargs[key]
            # in case of colors, this will work without nested braces
            return "{" + key + "}"


@lazyobject
def FORMATTER():
    return FlexibleFormatter()


class DefaultNotGivenType:
    """Singleton for representing when no default value is given."""

    __inst: tp.Optional["DefaultNotGivenType"] = None

    def __new__(cls):
        if DefaultNotGivenType.__inst is None:
            DefaultNotGivenType.__inst = object.__new__(cls)
        return DefaultNotGivenType.__inst


DefaultNotGiven = DefaultNotGivenType()

BEG_TOK_SKIPS = LazyObject(
    lambda: frozenset(["WS", "INDENT", "NOT", "LPAREN"]), globals(), "BEG_TOK_SKIPS"
)
END_TOK_TYPES = LazyObject(
    lambda: frozenset(["SEMI", "AND", "OR", "RPAREN"]), globals(), "END_TOK_TYPES"
)
RE_END_TOKS = LazyObject(
    lambda: re.compile(r"(;|and|\&\&|or|\|\||\))"), globals(), "RE_END_TOKS"
)
LPARENS = LazyObject(
    lambda: frozenset(
        ["LPAREN", "AT_LPAREN", "BANG_LPAREN", "DOLLAR_LPAREN", "ATDOLLAR_LPAREN"]
    ),
    globals(),
    "LPARENS",
)


def _is_not_lparen_and_rparen(lparens, rtok):
    """Tests if an RPAREN token is matched with something other than a plain old
    LPAREN type.
    """
    # note that any([]) is False, so this covers len(lparens) == 0
    return rtok.type == "RPAREN" and any(x != "LPAREN" for x in lparens)


def balanced_parens(line, mincol=0, maxcol=None, lexer=None):
    """Determines if parentheses are balanced in an expression."""
    line = line[mincol:maxcol]
    if lexer is None:
        lexer = xsh.execer.parser.lexer
    if "(" not in line and ")" not in line:
        return True
    cnt = 0
    lexer.input(line)
    for tok in lexer:
        if tok.type in LPARENS:
            cnt += 1
        elif tok.type == "RPAREN":
            cnt -= 1
        elif tok.type == "ERRORTOKEN" and ")" in tok.value:
            cnt -= 1
    return cnt == 0


def ends_with_colon_token(line, lexer=None):
    """Determines whether a line ends with a colon token, ignoring comments."""
    if lexer is None:
        lexer = xsh.execer.parser.lexer
    lexer.input(line)
    toks = list(lexer)
    return len(toks) > 0 and toks[-1].type == "COLON"


def find_next_break(line, mincol=0, lexer=None):
    """Returns the column number of the next logical break in subproc mode.
    This function may be useful in finding the maxcol argument of
    subproc_toks().
    """
    if mincol >= 1:
        line = line[mincol:]
    if lexer is None:
        lexer = xsh.execer.parser.lexer
    if RE_END_TOKS.search(line) is None:
        return None
    maxcol = None
    lparens = []
    lexer.input(line)
    for tok in lexer:
        if tok.type in LPARENS:
            lparens.append(tok.type)
        elif tok.type in END_TOK_TYPES:
            if _is_not_lparen_and_rparen(lparens, tok):
                lparens.pop()
            else:
                maxcol = tok.lexpos + mincol + 1
                break
        elif tok.type == "ERRORTOKEN" and ")" in tok.value:
            maxcol = tok.lexpos + mincol + 1
            break
        elif tok.type == "BANG":
            maxcol = mincol + len(line) + 1
            break
    return maxcol


def _offset_from_prev_lines(line, last):
    lines = line.splitlines(keepends=True)[:last]
    return sum(map(len, lines))


def subproc_toks(
    line, mincol=-1, maxcol=None, lexer=None, returnline=False, greedy=False
):
    """Encapsulates tokens in a source code line in a uncaptured
    subprocess ![] starting at a minimum column. If there are no tokens
    (ie in a comment line) this returns None. If greedy is True, it will encapsulate
    normal parentheses. Greedy is False by default.
    """
    if lexer is None:
        lexer = xsh.execer.parser.lexer
    if maxcol is None:
        maxcol = len(line) + 1
    lexer.reset()
    lexer.input(line)
    toks = []
    lparens = []
    saw_macro = False
    end_offset = 0
    for tok in lexer:
        pos = tok.lexpos
        if tok.type not in END_TOK_TYPES and pos >= maxcol:
            break
        if tok.type == "BANG":
            saw_macro = True
        if saw_macro and tok.type not in ("NEWLINE", "DEDENT"):
            toks.append(tok)
            continue
        if tok.type in LPARENS:
            lparens.append(tok.type)
        if greedy and len(lparens) > 0 and "LPAREN" in lparens:
            toks.append(tok)
            if tok.type == "RPAREN":
                lparens.pop()
            continue
        if len(toks) == 0 and tok.type in BEG_TOK_SKIPS:
            continue  # handle indentation
        elif len(toks) > 0 and toks[-1].type in END_TOK_TYPES:
            if _is_not_lparen_and_rparen(lparens, toks[-1]):
                lparens.pop()  # don't continue or break
            elif pos < maxcol and tok.type not in ("NEWLINE", "DEDENT", "WS"):
                if not greedy:
                    toks.clear()
                if tok.type in BEG_TOK_SKIPS:
                    continue
            else:
                break
        if pos < mincol:
            continue
        toks.append(tok)
        if tok.type == "WS" and tok.value == "\\":
            pass  # line continuation
        elif tok.type == "NEWLINE":
            break
        elif tok.type == "DEDENT":
            # fake a newline when dedenting without a newline
            tok.type = "NEWLINE"
            tok.value = "\n"
            tok.lineno -= 1
            if len(toks) >= 2:
                prev_tok_end = toks[-2].lexpos + len(toks[-2].value)
            else:
                prev_tok_end = len(line)
            if "#" in line[prev_tok_end:]:
                tok.lexpos = prev_tok_end  # prevents wrapping comments
            else:
                tok.lexpos = len(line)
            break
        elif check_bad_str_token(tok):
            return
    else:
        if len(toks) > 0 and toks[-1].type in END_TOK_TYPES:
            if _is_not_lparen_and_rparen(lparens, toks[-1]):
                pass
            elif greedy and toks[-1].type == "RPAREN":
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
            el = line[pos:].split("#")[0].rstrip()
            end_offset = len(el)
    if len(toks) == 0:
        return  # handle comment lines
    elif saw_macro or greedy:
        end_offset = len(toks[-1].value.rstrip()) + 1
    if toks[0].lineno != toks[-1].lineno:
        # handle multiline cases
        end_offset += _offset_from_prev_lines(line, toks[-1].lineno)
    beg, end = toks[0].lexpos, (toks[-1].lexpos + end_offset)
    end = len(line[:end].rstrip())
    rtn = "![" + line[beg:end] + "]"
    if returnline:
        rtn = line[:beg] + rtn + line[end:]
    return rtn


def check_bad_str_token(tok):
    """Checks if a token is a bad string."""
    if tok.type == "ERRORTOKEN" and tok.value == "EOF in multi-line string":
        return True
    elif isinstance(tok.value, str) and not check_quotes(tok.value):
        return True
    else:
        return False


def check_quotes(s):
    """Checks a string to make sure that if it starts with quotes, it also
    ends with quotes.
    """
    starts_as_str = RE_BEGIN_STRING.match(s) is not None
    ends_as_str = s.endswith('"') or s.endswith("'")
    if not starts_as_str and not ends_as_str:
        ok = True
    elif starts_as_str and not ends_as_str:
        ok = False
    elif not starts_as_str and ends_as_str:
        ok = False
    else:
        m = RE_COMPLETE_STRING.match(s)
        ok = m is not None
    return ok


def _have_open_triple_quotes(s):
    if s.count('"""') % 2 == 1:
        open_triple = '"""'
    elif s.count("'''") % 2 == 1:
        open_triple = "'''"
    else:
        open_triple = False
    return open_triple


def get_line_continuation():
    """The line continuation characters used in subproc mode. In interactive
    mode on Windows the backslash must be preceded by a space. This is because
    paths on Windows may end in a backslash.
    """
    if ON_WINDOWS:
        env = getattr(xsh, "env", None) or {}
        if env.get("XONSH_INTERACTIVE", False):
            return " \\"

    return "\\"


def get_logical_line(lines, idx):
    """Returns a single logical line (i.e. one without line continuations)
    from a list of lines.  This line should begin at index idx. This also
    returns the number of physical lines the logical line spans. The lines
    should not contain newlines
    """
    n = 1
    nlines = len(lines)
    linecont = get_line_continuation()
    while idx > 0 and lines[idx - 1].endswith(linecont):
        idx -= 1
    start = idx
    line = lines[idx]
    open_triple = _have_open_triple_quotes(line)
    while (line.endswith(linecont) or open_triple) and idx < nlines - 1:
        n += 1
        idx += 1
        if line.endswith(linecont):
            line = line[:-1] + lines[idx]
        else:
            line = line + "\n" + lines[idx]
        open_triple = _have_open_triple_quotes(line)
    return line, n, start


def replace_logical_line(lines, logical, idx, n):
    """Replaces lines at idx that may end in line continuation with a logical
    line that spans n lines.
    """
    linecont = get_line_continuation()
    if n == 1:
        lines[idx] = logical
        return
    space = " "
    for i in range(idx, idx + n - 1):
        a = len(lines[i])
        b = logical.find(space, a - 1)
        if b < 0:
            # no space found
            lines[i] = logical
            logical = ""
        else:
            # found space to split on
            lines[i] = logical[:b] + linecont
            logical = logical[b:]
    lines[idx + n - 1] = logical


def is_balanced(expr, ltok, rtok):
    """Determines whether an expression has unbalanced opening and closing tokens."""
    lcnt = expr.count(ltok)
    if lcnt == 0:
        return True
    rcnt = expr.count(rtok)
    if lcnt == rcnt:
        return True
    else:
        return False


def subexpr_from_unbalanced(expr, ltok, rtok):
    """Attempts to pull out a valid subexpression for unbalanced grouping,
    based on opening tokens, eg. '(', and closing tokens, eg. ')'.  This
    does not do full tokenization, but should be good enough for tab
    completion.
    """
    if is_balanced(expr, ltok, rtok):
        return expr
    subexpr = expr.rsplit(ltok, 1)[-1]
    subexpr = subexpr.rsplit(",", 1)[-1]
    subexpr = subexpr.rsplit(":", 1)[-1]
    return subexpr


def subexpr_before_unbalanced(expr, ltok, rtok):
    """Obtains the expression prior to last unbalanced left token."""
    subexpr, _, post = expr.rpartition(ltok)
    nrtoks_in_post = post.count(rtok)
    while nrtoks_in_post != 0:
        for _ in range(nrtoks_in_post):
            subexpr, _, post = subexpr.rpartition(ltok)
        nrtoks_in_post = post.count(rtok)
    _, _, subexpr = subexpr.rpartition(rtok)
    _, _, subexpr = subexpr.rpartition(ltok)
    return subexpr


@lazyobject
def STARTING_WHITESPACE_RE():
    return re.compile(r"^(\s*)")


def starting_whitespace(s):
    """Returns the whitespace at the start of a string"""
    return STARTING_WHITESPACE_RE.match(s).group(1)


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
    except Exception:
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
    ind = "\t" * ntabs + " " * nspaces
    if flatten:
        pat = re.compile(r"^\s*", re.MULTILINE)
    else:
        pat = re.compile(r"^", re.MULTILINE)
    outstr = re.sub(pat, ind, instr)
    if outstr.endswith(os.linesep + ind):
        return outstr[: -len(ind)]
    else:
        return outstr


def get_sep():
    """Returns the appropriate filepath separator char depending on OS and
    xonsh options set
    """
    if ON_WINDOWS and xsh.env.get("FORCE_POSIX_PATHS"):
        return os.altsep
    else:
        return os.sep


def fallback(cond, backup):
    """Decorator for returning the object if cond is true and a backup if cond
    is false.
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
    _stream: tp.Optional[str] = None

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


def _yield_accessible_unix_file_names(path):
    """yield file names of executable files in path."""
    if not os.path.exists(path):
        return
    for file_ in os.scandir(path):
        try:
            if file_.is_file() and os.access(file_.path, os.X_OK):
                yield file_.name
        except OSError:
            # broken Symlink are neither dir not files
            pass


def _executables_in_posix(path):
    if not os.path.exists(path):
        return
    else:
        yield from _yield_accessible_unix_file_names(path)


def _executables_in_windows(path):
    if not os.path.isdir(path):
        return
    extensions = xsh.env["PATHEXT"]
    try:
        for x in os.scandir(path):
            try:
                is_file = x.is_file()
            except OSError:
                continue
            if is_file:
                fname = x.name
            else:
                continue
            base_name, ext = os.path.splitext(fname)
            if ext.upper() in extensions:
                yield fname
    except FileNotFoundError:
        # On Windows, there's no guarantee for the directory to really
        # exist even if isdir returns True. This may happen for instance
        # if the path contains trailing spaces.
        return


def executables_in(path) -> tp.Iterable[str]:
    """Returns a generator of files in path that the user could execute."""
    if ON_WINDOWS:
        func = _executables_in_windows
    else:
        func = _executables_in_posix
    try:
        yield from func(path)
    except PermissionError:
        return


def debian_command_not_found(cmd):
    """Uses the debian/ubuntu command-not-found utility to suggest packages for a
    command that cannot currently be found.
    """
    if not ON_LINUX:
        return ""

    cnf = xsh.commands_cache.lazyget(
        "command-not-found", ("/usr/lib/command-not-found",)
    )[0]

    if not os.path.isfile(cnf):
        return ""

    c = "{0} {1}; exit 0"
    s = subprocess.check_output(
        c.format(cnf, shlex.quote(cmd)),
        text=True,
        stderr=subprocess.STDOUT,
        shell=True,
    )
    s = "\n".join(s.rstrip().splitlines()).strip()
    return s


def conda_suggest_command_not_found(cmd, env):
    """Uses conda-suggest to suggest packages for a command that cannot
    currently be found.
    """
    try:
        from conda_suggest import find
    except ImportError:
        return ""
    return find.message_string(
        cmd, conda_suggest_path=env.get("CONDA_SUGGEST_PATH", None)
    )


def command_not_found(cmd, env):
    """Uses various mechanism to suggest packages for a command that cannot
    currently be found.
    """
    if ON_LINUX:
        rtn = debian_command_not_found(cmd)
    else:
        rtn = ""
    conda = conda_suggest_command_not_found(cmd, env)
    if conda:
        rtn = rtn + "\n\n" + conda if rtn else conda
    return rtn


@functools.lru_cache
def suggest_commands(cmd, env):
    """Suggests alternative commands given an environment and aliases."""
    if not env.get("SUGGEST_COMMANDS"):
        return ""
    thresh = env.get("SUGGEST_THRESHOLD")
    max_sugg = env.get("SUGGEST_MAX_NUM")
    if max_sugg < 0:
        max_sugg = float("inf")
    cmd = cmd.lower()
    suggested = {}

    for alias in xsh.aliases:
        if alias not in suggested:
            if levenshtein(alias.lower(), cmd, thresh) < thresh:
                suggested[alias] = "Alias"

    for _cmd in xsh.commands_cache.all_commands:
        if _cmd not in suggested:
            if levenshtein(_cmd.lower(), cmd, thresh) < thresh:
                suggested[_cmd] = f"Command ({_cmd})"

    suggested = collections.OrderedDict(
        sorted(
            suggested.items(), key=lambda x: suggestion_sort_helper(x[0].lower(), cmd)
        )
    )
    num = min(len(suggested), max_sugg)

    if num == 0:
        rtn = command_not_found(cmd, env)
    else:
        oneof = "" if num == 1 else "one of "
        tips = f"Did you mean {oneof}the following?"
        items = list(suggested.popitem(False) for _ in range(num))
        length = max(len(key) for key, _ in items) + 2
        alternatives = "\n".join(
            "    {: <{}} {}".format(key + ":", length, val) for key, val in items
        )
        rtn = f"{tips}\n{alternatives}"
        c = command_not_found(cmd, env)
        rtn += ("\n\n" + c) if len(c) > 0 else ""
    return rtn


def _get_manual_env_var(name, default=None):
    """Returns if the given variable is manually set as well as it's value."""
    env = getattr(xsh, "env", None)
    if env is None:
        env = os_environ
        manually_set = name in env
    else:
        manually_set = env.is_manually_set(name)

    value = env.get(name, default)
    return (manually_set, value)


def print_warning(msg):
    """Print warnings with/without traceback."""
    manually_set_trace, show_trace = _get_manual_env_var("XONSH_SHOW_TRACEBACK", False)
    manually_set_logfile, log_file = _get_manual_env_var("XONSH_TRACEBACK_LOGFILE")
    if (not manually_set_trace) and (not manually_set_logfile):
        # Notify about the traceback output possibility if neither of
        # the two options have been manually set
        sys.stderr.write(
            "xonsh: For full traceback set: " "$XONSH_SHOW_TRACEBACK = True\n"
        )
    # convert show_trace to bool if necessary
    if not is_bool(show_trace):
        show_trace = to_bool(show_trace)
    # if the trace option has been set, print all traceback info to stderr
    if show_trace:
        # notify user about XONSH_TRACEBACK_LOGFILE if it has
        # not been set manually
        if not manually_set_logfile:
            sys.stderr.write(
                "xonsh: To log full traceback to a file set: "
                "$XONSH_TRACEBACK_LOGFILE = <filename>\n"
            )
        traceback.print_stack()
    # additionally, check if a file for traceback logging has been
    # specified and convert to a proper option if needed
    log_file = to_logfile_opt(log_file)
    if log_file:
        # if log_file <> '' or log_file <> None, append
        # traceback log there as well
        with open(os.path.abspath(log_file), "a") as f:
            traceback.print_stack(file=f)

    msg = msg if msg.endswith("\n") else msg + "\n"
    sys.stderr.write(msg)


def print_exception(msg=None, exc_info=None):
    """Print given exception (or current if None) with/without traceback and set sys.last_type, sys.last_value, sys.last_traceback accordingly."""

    # is no exec_info() triple is given, use the exception beeing handled at the moment
    if exc_info is None:
        exc_info = sys.exc_info()

    # these values (initialized with their default for traceback.print_exception) control how an exception is printed
    limit = None
    chain = True

    _, debug_level = _get_manual_env_var("XONSH_DEBUG", 0)

    # the interal state of the parsers stack is
    # not helpful in normal operation (XONSH_DEBUG == 0).
    # this is also done to be consistent with python
    is_syntax_error = issubclass(exc_info[0], SyntaxError)

    # XonshErrors don't show where in the users code they occured
    # (most are reported deeper in the callstack, e.g. see procs/pipelines.py),
    # but only show non-helpful xonsh internals.
    # These are only relevent when developing/debugging xonsh itself.
    # Therefore, dont print these traces until this gets overhauled.
    is_xonsh_error = exc_info[0] in (XonshError, XonshCalledProcessError)

    # hide unhelpful traces if not debugging
    hide_stacktrace = debug_level == 0 and (is_syntax_error or is_xonsh_error)
    if hide_stacktrace:
        limit = 0
        chain = False

    sys.last_type, sys.last_value, sys.last_traceback = exc_info

    manually_set_trace, show_trace = _get_manual_env_var("XONSH_SHOW_TRACEBACK", False)
    manually_set_logfile, log_file = _get_manual_env_var("XONSH_TRACEBACK_LOGFILE")
    if (not manually_set_trace) and (not manually_set_logfile):
        # Notify about the traceback output possibility if neither of
        # the two options have been manually set
        sys.stderr.write(
            "xonsh: For full traceback set: " "$XONSH_SHOW_TRACEBACK = True\n"
        )
    # convert show_trace to bool if necessary
    if not is_bool(show_trace):
        show_trace = to_bool(show_trace)
    # if the trace option has been set, print all traceback info to stderr
    if show_trace:
        # notify user about XONSH_TRACEBACK_LOGFILE if it has
        # not been set manually
        if not manually_set_logfile:
            sys.stderr.write(
                "xonsh: To log full traceback to a file set: "
                "$XONSH_TRACEBACK_LOGFILE = <filename>\n"
            )

        traceback_str = "".join(
            traceback.format_exception(*exc_info, limit=limit, chain=chain)
        )

        # color the traceback if available
        _, interactive = _get_manual_env_var("XONSH_INTERACTIVE", 0)
        _, color_results = _get_manual_env_var("COLOR_RESULTS", 0)
        if interactive and color_results and HAS_PYGMENTS:
            import pygments.lexers.python

            lexer = pygments.lexers.python.PythonTracebackLexer()
            tokens = list(pygments.lex(traceback_str, lexer=lexer))
            # this goes to stdout, but since we are interactive it doesn't matter
            print_color(tokens, end="")
        else:
            print(traceback_str, file=sys.stderr, end="")

    # additionally, check if a file for traceback logging has been
    # specified and convert to a proper option if needed
    log_file = to_logfile_opt(log_file)
    if log_file:
        # if log_file <> '' or log_file <> None, append
        # traceback log there as well
        with open(os.path.abspath(log_file), "a") as f:
            traceback.print_exception(*exc_info, limit=limit, chain=chain, file=f)

    if not show_trace:
        # if traceback output is disabled, print the exception's
        # error message on stderr.
        display_error_message(exc_info)
    if msg:
        msg = msg if msg.endswith("\n") else msg + "\n"
        sys.stderr.write(msg)


def display_error_message(exc_info, strip_xonsh_error_types=True):
    """
    Prints the error message of the given sys.exc_info() triple on stderr.
    """
    exc_type, exc_value, exc_traceback = exc_info
    exception_only = traceback.format_exception_only(exc_type, exc_value)
    if exc_type is XonshError and strip_xonsh_error_types:
        exception_only[0] = exception_only[0].partition(": ")[-1]
    sys.stderr.write("".join(exception_only))


def is_writable_file(filepath):
    """
    Checks if a filepath is valid for writing.
    """
    filepath = expand_path(filepath)
    # convert to absolute path if needed
    if not os.path.isabs(filepath):
        filepath = os.path.abspath(filepath)
    # cannot write to directories
    if os.path.isdir(filepath):
        return False
    # if the file exists and is writable, we're fine
    if os.path.exists(filepath):
        return True if os.access(filepath, os.W_OK) else False
    # if the path doesn't exist, isolate its directory component
    # and ensure that directory is writable instead
    return os.access(os.path.dirname(filepath), os.W_OK)


# Modified from Public Domain code, by Magnus Lie Hetland
# from http://hetland.org/coding/python/levenshtein.py
def levenshtein(a, b, max_dist=float("inf")):
    """Calculates the Levenshtein distance between a and b."""
    n, m = len(a), len(b)
    if abs(n - m) > max_dist:
        return float("inf")
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
    The escaping is based on details here and empirical testing:
    http://www.robvanderwoude.com/escapechars.php
    """
    for c in '^()%!<>&|"':
        s = s.replace(c, "^" + c)
    return s


def argvquote(arg, force=False):
    """Returns an argument quoted in such a way that that CommandLineToArgvW
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
            if c == "\\":
                # first count the number of current backslashes
                n_backslashes += 1
                continue
            if c == '"':
                # Escape all backslashes and the following double quotation mark
                cmdline += (n_backslashes * 2 + 1) * "\\"
            else:
                # backslashes are not special here
                cmdline += n_backslashes * "\\"
            n_backslashes = 0
            cmdline += c
        # Escape all backslashes, but let the terminating
        # double quotation mark we add below be interpreted
        # as a metacharacter
        cmdline += +n_backslashes * 2 * "\\" + '"'
        return cmdline


def on_main_thread():
    """Checks if we are on the main thread or not."""
    return threading.current_thread() is threading.main_thread()


_DEFAULT_SENTINEL = object()


@contextlib.contextmanager
def swap(namespace, name, value, default=_DEFAULT_SENTINEL):
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


@contextlib.contextmanager
def swap_values(d, updates, default=_DEFAULT_SENTINEL):
    """Updates a dictionary (or other mapping) with values from another mapping,
    and then restores the original mapping when the context is exited.
    """
    old = {k: d.get(k, default) for k in updates}
    d.update(updates)
    yield
    for k, v in old.items():
        if v is default and k in d:
            del d[k]
        else:
            d[k] = v


#
# Validators and converters
#


def detype(x):
    """This assumes that the object has a detype method, and calls that."""
    return x.detype()


def is_int(x):
    """Tests if something is an integer"""
    return isinstance(x, int)


def is_float(x):
    """Tests if something is a float"""
    return isinstance(x, float)


def is_string(x):
    """Tests if something is a string"""
    return isinstance(x, str)


def is_slice(x):
    """Tests if something is a slice"""
    return isinstance(x, slice)


def is_callable(x):
    """Tests if something is callable"""
    return callable(x)


def is_string_or_callable(x):
    """Tests if something is a string or callable"""
    return is_string(x) or is_callable(x)


def is_class(x):
    """Tests if something is a class"""
    return isinstance(x, type)


def always_true(x):
    """Returns True"""
    return True


def always_false(x):
    """Returns False"""
    return False


def always_none(x):
    """Returns None"""
    return None


def ensure_string(x):
    """Returns a string if x is not a string, and x if it already is. If x is None, the empty string is returned."""
    return str(x) if x is not None else ""


def is_path(x):
    """This tests if something is a path."""
    return isinstance(x, pathlib.Path)


def is_env_path(x):
    """This tests if something is an environment path, ie a list of strings."""
    return isinstance(x, EnvPath)


def str_to_path(x):
    """Converts a string to a path."""
    if x is None or x == "":
        return None
    elif isinstance(x, str):
        return pathlib.Path(x)
    elif isinstance(x, pathlib.Path):
        return x
    elif isinstance(x, EnvPath) and len(x) == 1:
        return pathlib.Path(x[0]) if x[0] else None
    else:
        raise TypeError(
            f"Variable should be a pathlib.Path, str or single EnvPath type. {type(x)} given."
        )


def str_to_env_path(x):
    """Converts a string to an environment path, ie a list of strings,
    splitting on the OS separator.
    """
    # splitting will be done implicitly in EnvPath's __init__
    return EnvPath(x)


def path_to_str(x):
    """Converts a path to a string."""
    return str(x) if x is not None else ""


def env_path_to_str(x):
    """Converts an environment path to a string by joining on the OS
    separator.
    """
    return os.pathsep.join(x)


def is_bool(x):
    """Tests if something is a boolean."""
    return isinstance(x, bool)


def is_bool_or_none(x):
    """Tests if something is a boolean or None."""
    return (x is None) or isinstance(x, bool)


def is_logfile_opt(x):
    """
    Checks if x is a valid $XONSH_TRACEBACK_LOGFILE option. Returns False
    if x is not a writable/creatable file or an empty string or None.
    """
    if x is None:
        return True
    if not isinstance(x, str):
        return False
    else:
        return is_writable_file(x) or x == ""


def to_logfile_opt(x):
    """Converts a $XONSH_TRACEBACK_LOGFILE option to either a str containing
    the filepath if it is a writable file or None if the filepath is not
    valid, informing the user on stderr about the invalid choice.
    """
    if isinstance(x, os.PathLike):  # type: ignore
        x = str(x)
    if is_logfile_opt(x):
        return expand_path(x) if x else x
    else:
        # if option is not valid, return a proper
        # option and inform the user on stderr
        sys.stderr.write(
            "xonsh: $XONSH_TRACEBACK_LOGFILE must be a "
            "filepath pointing to a file that either exists "
            "and is writable or that can be created.\n"
        )
        return None


def logfile_opt_to_str(x):
    """
    Detypes a $XONSH_TRACEBACK_LOGFILE option.
    """
    if x is None:
        # None should not be detyped to 'None', as 'None' constitutes
        # a perfectly valid filename and retyping it would introduce
        # ambiguity. Detype to the empty string instead.
        return ""
    return str(x)


_FALSES = LazyObject(
    lambda: frozenset(["", "0", "n", "f", "no", "none", "false", "off"]),
    globals(),
    "_FALSES",
)


def to_bool(x):
    """Converts to a boolean in a semantically meaningful way."""
    if isinstance(x, bool):
        return x
    elif isinstance(x, str):
        return False if x.lower() in _FALSES else True
    else:
        return bool(x)


def to_bool_or_none(x):
    """Converts to a boolean or none in a semantically meaningful way."""
    if x is None or isinstance(x, bool):
        return x
    elif isinstance(x, str):
        low_x = x.lower()
        if low_x == "none":
            return None
        else:
            return False if x.lower() in _FALSES else True
    else:
        return bool(x)


def to_itself(x):
    """No conversion, returns itself."""
    return x


def to_int_or_none(x) -> tp.Optional[int]:
    """Convert the given value to integer if possible. Otherwise return None"""
    if isinstance(x, str) and x.lower() == "none":
        return None
    else:
        return int(x)


def bool_to_str(x):
    """Converts a bool to an empty string if False and the string '1' if
    True.
    """
    return "1" if x else ""


def bool_or_none_to_str(x):
    """Converts a bool or None value to a string."""
    if x is None:
        return "None"
    else:
        return "1" if x else ""


_BREAKS = LazyObject(
    lambda: frozenset(["b", "break", "s", "skip", "q", "quit"]), globals(), "_BREAKS"
)


def to_bool_or_break(x):
    if isinstance(x, str) and x.lower() in _BREAKS:
        return "break"
    else:
        return to_bool(x)


def is_bool_or_int(x):
    """Returns whether a value is a boolean or integer."""
    return is_bool(x) or is_int(x)


def to_bool_or_int(x):
    """Converts a value to a boolean or an integer."""
    if isinstance(x, str):
        return int(x) if x.isdigit() else to_bool(x)
    elif is_int(x):  # bools are ints too!
        return x
    else:
        return bool(x)


def bool_or_int_to_str(x):
    """Converts a boolean or integer to a string."""
    return bool_to_str(x) if is_bool(x) else str(x)


@lazyobject
def SLICE_REG():
    return re.compile(
        r"(?P<start>(?:-\d)?\d*):(?P<end>(?:-\d)?\d*):?(?P<step>(?:-\d)?\d*)"
    )


def to_shlvl(x):
    """Converts a value to an $SHLVL integer according to bash's behaviour (variables.c::adjust_shell_level)."""
    if x is None:
        return 0
    else:
        x = str(x)
    try:
        return adjust_shlvl(max(0, int(x)), 0)
    except ValueError:
        return 0


def is_valid_shlvl(x):
    """Checks whether a variable is a proper $SHLVL integer."""
    return isinstance(x, int) and to_shlvl(x) == x


def adjust_shlvl(old_lvl: int, change: int):
    """Adjusts an $SHLVL integer according to bash's behaviour (variables.c::adjust_shell_level)."""
    new_level = old_lvl + change
    if new_level < 0:
        new_level = 0
    elif new_level >= 1000:
        new_level = 1
    return new_level


def ensure_slice(x):
    """Try to convert an object into a slice, complain on failure"""
    if not x and x != 0:
        return slice(None)
    elif is_slice(x):
        return x
    try:
        x = int(x)
        if x != -1:
            s = slice(x, x + 1)
        else:
            s = slice(-1, None, None)
    except ValueError:
        x = x.strip("[]()")
        m = SLICE_REG.fullmatch(x)
        if m:
            groups = (int(i) if i else None for i in m.groups())
            s = slice(*groups)
        else:
            raise ValueError(f"cannot convert {x!r} to slice")
    except TypeError:
        try:
            s = slice(*(int(i) for i in x))
        except (TypeError, ValueError):
            raise ValueError(f"cannot convert {x!r} to slice")
    return s


def get_portions(it, slices):
    """Yield from portions of an iterable.

    Parameters
    ----------
    it : iterable
    slices : a slice or a list of slice objects
    """
    if is_slice(slices):
        slices = [slices]
    if len(slices) == 1:
        s = slices[0]
        try:
            yield from itertools.islice(it, s.start, s.stop, s.step)
            return
        except ValueError:  # islice failed
            pass
    it = list(it)
    for s in slices:
        yield from it[s]


def is_slice_as_str(x):
    """
    Test if string x is a slice. If not a string return False.
    """
    try:
        x = x.strip("[]()")
        m = SLICE_REG.fullmatch(x)
        if m:
            return True
    except AttributeError:
        pass
    return False


def is_int_as_str(x):
    """
    Test if string x is an integer. If not a string return False.
    """
    try:
        return x.isdecimal()
    except AttributeError:
        return False


def is_string_set(x):
    """Tests if something is a set of strings"""
    return isinstance(x, cabc.Set) and all(isinstance(a, str) for a in x)


def csv_to_set(x):
    """Convert a comma-separated list of strings to a set of strings."""
    if not x:
        return set()
    else:
        return set(x.split(","))


def set_to_csv(x):
    """Convert a set of strings to a comma-separated list of strings."""
    return ",".join(x)


def pathsep_to_set(x):
    """Converts a os.pathsep separated string to a set of strings."""
    if not x:
        return set()
    else:
        return set(x.split(os.pathsep))


def set_to_pathsep(x, sort=False):
    """Converts a set to an os.pathsep separated string. The sort kwarg
    specifies whether to sort the set prior to str conversion.
    """
    if sort:
        x = sorted(x)
    return os.pathsep.join(x)


def is_string_seq(x):
    """Tests if something is a sequence of strings"""
    return isinstance(x, cabc.Sequence) and all(isinstance(a, str) for a in x)


def is_nonstring_seq_of_strings(x):
    """Tests if something is a sequence of strings, where the top-level
    sequence is not a string itself.
    """
    return (
        isinstance(x, cabc.Sequence)
        and not isinstance(x, str)
        and all(isinstance(a, str) for a in x)
    )


def pathsep_to_seq(x):
    """Converts a os.pathsep separated string to a sequence of strings."""
    if not x:
        return []
    else:
        return x.split(os.pathsep)


def seq_to_pathsep(x):
    """Converts a sequence to an os.pathsep separated string."""
    return os.pathsep.join(x)


def pathsep_to_upper_seq(x):
    """Converts a os.pathsep separated string to a sequence of
    uppercase strings.
    """
    if not x:
        return []
    else:
        return x.upper().split(os.pathsep)


def seq_to_upper_pathsep(x):
    """Converts a sequence to an uppercase os.pathsep separated string."""
    return os.pathsep.join(x).upper()


def is_bool_seq(x):
    """Tests if an object is a sequence of bools."""
    return isinstance(x, cabc.Sequence) and all(isinstance(y, bool) for y in x)


def csv_to_bool_seq(x):
    """Takes a comma-separated string and converts it into a list of bools."""
    return [to_bool(y) for y in csv_to_set(x)]


def bool_seq_to_csv(x):
    """Converts a sequence of bools to a comma-separated string."""
    return ",".join(map(str, x))


def ptk2_color_depth_setter(x):
    """Setter function for $PROMPT_TOOLKIT_COLOR_DEPTH. Also
    updates os.environ so prompt toolkit can pickup the value.
    """
    x = str(x)
    if x in {
        "DEPTH_1_BIT",
        "MONOCHROME",
        "DEPTH_4_BIT",
        "ANSI_COLORS_ONLY",
        "DEPTH_8_BIT",
        "DEFAULT",
        "DEPTH_24_BIT",
        "TRUE_COLOR",
    }:
        pass
    elif x in {"", None}:
        x = ""
    else:
        msg = f'"{x}" is not a valid value for $PROMPT_TOOLKIT_COLOR_DEPTH. '
        warnings.warn(msg, RuntimeWarning)
        x = ""
    if x == "" and "PROMPT_TOOLKIT_COLOR_DEPTH" in os_environ:
        del os_environ["PROMPT_TOOLKIT_COLOR_DEPTH"]
    else:
        os_environ["PROMPT_TOOLKIT_COLOR_DEPTH"] = x
    return x


def is_completions_display_value(x):
    """Enumerated values of ``$COMPLETIONS_DISPLAY``"""
    return x in {"none", "single", "multi"}


def to_completions_display_value(x):
    """Convert user input to value of ``$COMPLETIONS_DISPLAY``"""
    x = str(x).lower()
    if x in {"none", "false"}:
        x = "none"
    elif x in {"multi", "true"}:
        x = "multi"
    elif x in {"single", "readline"}:
        pass
    else:
        msg = f'"{x}" is not a valid value for $COMPLETIONS_DISPLAY. '
        msg += 'Using "multi".'
        warnings.warn(msg, RuntimeWarning)
        x = "multi"
    return x


CANONIC_COMPLETION_MODES = frozenset({"default", "menu-complete"})


def is_completion_mode(x):
    """Enumerated values of $COMPLETION_MODE"""
    return x in CANONIC_COMPLETION_MODES


def to_completion_mode(x):
    """Convert user input to value of $COMPLETION_MODE"""
    y = str(x).casefold().replace("_", "-")
    y = (
        "default"
        if y in ("", "d", "xonsh", "none", "def")
        else "menu-complete"
        if y in ("m", "menu", "menu-completion")
        else y
    )
    if y not in CANONIC_COMPLETION_MODES:
        warnings.warn(
            f"'{x}' is not valid for $COMPLETION_MODE, must be one of {CANONIC_COMPLETION_MODES}.  Using 'default'.",
            RuntimeWarning,
        )
        y = "default"
    return y


def is_tok_color_dict(x):
    from pygments.token import _TokenType, string_to_tokentype

    from xonsh.ptk_shell.shell import _style_from_pygments_dict

    """Tests if something is a Token:Style dictionary"""
    if not isinstance(x, dict):
        return False
    """Check if is a Token:str dict"""
    for k, v in x.items():
        if not isinstance(v, str):
            return False
        try:
            k = _TokenType(k)
            string_to_tokentype(k)
        except (TypeError, AttributeError):
            msg = f'"{k}" is not a valid Token.'
            warnings.warn(msg, RuntimeWarning)
            return False
    """Check each str is a valid style"""
    try:
        _style_from_pygments_dict(x)
    except (AssertionError, ValueError):
        msg = f'"{x}" contains an invalid style.'
        warnings.warn(msg, RuntimeWarning)
        return False
    return True


def to_dict(x):
    """Converts a string to a dictionary"""
    if isinstance(x, dict):
        return x
    try:
        x = ast.literal_eval(x)
    except (ValueError, SyntaxError):
        msg = f'"{x}" can not be converted to Python dictionary.'
        warnings.warn(msg, RuntimeWarning)
        x = dict()
    return x


def to_tok_color_dict(x):
    """Converts a string to Token:str dictionary"""
    if is_tok_color_dict(x):
        return x
    x = to_dict(x)
    if not is_tok_color_dict(x):
        msg = f'"{x}" can not be converted to Token:str dictionary.'
        warnings.warn(msg, RuntimeWarning)
        x = dict()
    return x


def dict_to_str(x):
    """Converts a dictionary to a string"""
    if not x or len(x) == 0:
        return ""
    return str(x)


# history validation

_min_to_sec = lambda x: 60.0 * float(x)
_hour_to_sec = lambda x: 60.0 * _min_to_sec(x)
_day_to_sec = lambda x: 24.0 * _hour_to_sec(x)
_month_to_sec = lambda x: 30.4375 * _day_to_sec(x)
_year_to_sec = lambda x: 365.25 * _day_to_sec(x)
_kb_to_b = lambda x: 1024 * int(x)
_mb_to_b = lambda x: 1024 * _kb_to_b(x)
_gb_to_b = lambda x: 1024 * _mb_to_b(x)
_tb_to_b = lambda x: 1024 * _tb_to_b(x)  # type: ignore

CANON_HISTORY_UNITS = LazyObject(
    lambda: frozenset(["commands", "files", "s", "b"]), globals(), "CANON_HISTORY_UNITS"
)

HISTORY_UNITS = LazyObject(
    lambda: {
        "": ("commands", int),
        "c": ("commands", int),
        "cmd": ("commands", int),
        "cmds": ("commands", int),
        "command": ("commands", int),
        "commands": ("commands", int),
        "f": ("files", int),
        "files": ("files", int),
        "s": ("s", float),
        "sec": ("s", float),
        "second": ("s", float),
        "seconds": ("s", float),
        "m": ("s", _min_to_sec),
        "min": ("s", _min_to_sec),
        "mins": ("s", _min_to_sec),
        "h": ("s", _hour_to_sec),
        "hr": ("s", _hour_to_sec),
        "hour": ("s", _hour_to_sec),
        "hours": ("s", _hour_to_sec),
        "d": ("s", _day_to_sec),
        "day": ("s", _day_to_sec),
        "days": ("s", _day_to_sec),
        "mon": ("s", _month_to_sec),
        "month": ("s", _month_to_sec),
        "months": ("s", _month_to_sec),
        "y": ("s", _year_to_sec),
        "yr": ("s", _year_to_sec),
        "yrs": ("s", _year_to_sec),
        "year": ("s", _year_to_sec),
        "years": ("s", _year_to_sec),
        "b": ("b", int),
        "byte": ("b", int),
        "bytes": ("b", int),
        "kb": ("b", _kb_to_b),
        "kilobyte": ("b", _kb_to_b),
        "kilobytes": ("b", _kb_to_b),
        "mb": ("b", _mb_to_b),
        "meg": ("b", _mb_to_b),
        "megs": ("b", _mb_to_b),
        "megabyte": ("b", _mb_to_b),
        "megabytes": ("b", _mb_to_b),
        "gb": ("b", _gb_to_b),
        "gig": ("b", _gb_to_b),
        "gigs": ("b", _gb_to_b),
        "gigabyte": ("b", _gb_to_b),
        "gigabytes": ("b", _gb_to_b),
        "tb": ("b", _tb_to_b),
        "terabyte": ("b", _tb_to_b),
        "terabytes": ("b", _tb_to_b),
    },
    globals(),
    "HISTORY_UNITS",
)
"""Maps lowercase unit names to canonical name and conversion utilities."""


def is_history_tuple(x):
    """Tests if something is a proper history value, units tuple."""
    if (
        isinstance(x, cabc.Sequence)
        and len(x) == 2
        and isinstance(x[0], (int, float))
        and x[1].lower() in CANON_HISTORY_UNITS
    ):
        return True
    return False


def is_regex(x):
    """Tests if something is a valid regular expression."""
    try:
        re.compile(x)
        return True
    except re.error:
        pass
    return False


def is_history_backend(x):
    """Tests if something is a valid history backend."""
    return is_string(x) or is_class(x) or isinstance(x, object)


def is_dynamic_cwd_width(x):
    """Determine if the input is a valid input for the DYNAMIC_CWD_WIDTH
    environment variable.
    """
    return (
        isinstance(x, tuple)
        and len(x) == 2
        and isinstance(x[0], float)
        and x[1] in set("c%")
    )


def to_dynamic_cwd_tuple(x):
    """Convert to a canonical cwd_width tuple."""
    unit = "c"
    if isinstance(x, str):
        if x[-1] == "%":
            x = x[:-1]
            unit = "%"
        else:
            unit = "c"
        return (float(x), unit)
    else:
        return (float(x[0]), x[1])


def dynamic_cwd_tuple_to_str(x):
    """Convert a canonical cwd_width tuple to a string."""
    if x[1] == "%":
        return str(x[0]) + "%"
    else:
        return str(x[0])


RE_HISTORY_TUPLE = LazyObject(
    lambda: re.compile(r"([-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)\s*([A-Za-z]*)"),
    globals(),
    "RE_HISTORY_TUPLE",
)


def to_history_tuple(x):
    """Converts to a canonical history tuple."""
    if not isinstance(x, (cabc.Sequence, float, int)):
        raise ValueError("history size must be given as a sequence or number")
    if isinstance(x, str):
        m = RE_HISTORY_TUPLE.match(x.strip().lower())
        return to_history_tuple((m.group(1), m.group(3)))
    elif isinstance(x, (float, int)):
        return to_history_tuple((x, "commands"))
    units, converter = HISTORY_UNITS[x[1]]
    value = converter(x[0])
    return (value, units)


def history_tuple_to_str(x):
    """Converts a valid history tuple to a canonical string."""
    return "{} {}".format(*x)


def all_permutations(iterable):
    """Yeilds all permutations, not just those of a specified length"""
    for r in range(1, len(iterable) + 1):
        yield from itertools.permutations(iterable, r=r)


def format_color(string, **kwargs):
    """Formats strings that may contain colors. This simply dispatches to the
    shell instances method of the same name. The results of this function should
    be directly usable by print_color().
    """
    if hasattr(xsh.shell, "shell"):
        return xsh.shell.shell.format_color(string, **kwargs)
    else:
        # fallback for ANSI if shell is not yet initialized
        from xonsh.ansi_colors import ansi_partial_color_format

        style = xsh.env.get("XONSH_COLOR_STYLE")
        return ansi_partial_color_format(string, style=style)


def print_color(string, **kwargs):
    """Prints a string that may contain colors. This dispatched to the shell
    method of the same name. Colors will be formatted if they have not already
    been.
    """
    if hasattr(xsh.shell, "shell"):
        xsh.shell.shell.print_color(string, **kwargs)
    else:
        # fallback for ANSI if shell is not yet initialized
        print(format_color(string, **kwargs))


def color_style_names():
    """Returns an iterable of all available style names."""
    return xsh.shell.shell.color_style_names()


def color_style():
    """Returns the current color map."""
    return xsh.shell.shell.color_style()


def register_custom_style(
    name, styles, highlight_color=None, background_color=None, base="default"
):
    """Register custom style.

    Parameters
    ----------
    name : str
        Style name.
    styles : dict
        Token -> style mapping.
    highlight_color : str
        Hightlight color.
    background_color : str
        Background color.
    base : str, optional
        Base style to use as default.

    Returns
    -------
    style : The style object created, None if not succeeded
    """
    style = None
    if pygments_version_info():
        from xonsh.pyghooks import register_custom_pygments_style

        style = register_custom_pygments_style(
            name, styles, highlight_color, background_color, base
        )

    # register ANSI colors
    from xonsh.ansi_colors import register_custom_ansi_style

    register_custom_ansi_style(name, styles, base)

    return style


def _token_attr_from_stylemap(stylemap):
    """yields tokens attr, and index from a stylemap"""
    import prompt_toolkit as ptk

    if xsh.shell.shell_type == "prompt_toolkit1":
        style = ptk.styles.style_from_dict(stylemap)
        for token in stylemap:
            yield token, style.token_to_attrs[token]
    else:
        style = ptk.styles.style_from_pygments_dict(stylemap)
        for token in stylemap:
            style_str = "class:{}".format(
                ptk.styles.pygments.pygments_token_to_classname(token)
            )
            yield (token, style.get_attrs_for_style_str(style_str))


def _get_color_lookup_table():
    """Returns the prompt_toolkit win32 ColorLookupTable"""
    if xsh.shell.shell_type == "prompt_toolkit1":
        from prompt_toolkit.terminal.win32_output import ColorLookupTable
    else:
        from prompt_toolkit.output.win32 import ColorLookupTable
    return ColorLookupTable()


def _get_color_indexes(style_map):
    """Generates the color and windows color index for a style"""
    table = _get_color_lookup_table()
    for token, attr in _token_attr_from_stylemap(style_map):
        if attr.color:
            index = table.lookup_fg_color(attr.color)
            try:
                rgb = (
                    int(attr.color[0:2], 16),
                    int(attr.color[2:4], 16),
                    int(attr.color[4:6], 16),
                )
            except Exception:
                rgb = None
            yield token, index, rgb


# Map of new PTK2 color names to PTK1 variants
PTK_NEW_OLD_COLOR_MAP = LazyObject(
    lambda: {
        "black": "black",
        "red": "darkred",
        "green": "darkgreen",
        "yellow": "brown",
        "blue": "darkblue",
        "magenta": "purple",
        "cyan": "teal",
        "gray": "lightgray",
        "brightblack": "darkgray",
        "brightred": "red",
        "brightgreen": "green",
        "brightyellow": "yellow",
        "brightblue": "blue",
        "brightmagenta": "fuchsia",
        "brightcyan": "turquoise",
        "white": "white",
    },
    globals(),
    "PTK_NEW_OLD_COLOR_MAP",
)

# Map of new ansicolor names to old PTK1 names
ANSICOLOR_NAMES_MAP = LazyObject(
    lambda: {"ansi" + k: "#ansi" + v for k, v in PTK_NEW_OLD_COLOR_MAP.items()},
    globals(),
    "ANSICOLOR_NAMES_MAP",
)


def _win10_color_map():
    cmap = {
        "ansiblack": (12, 12, 12),
        "ansiblue": (0, 55, 218),
        "ansigreen": (19, 161, 14),
        "ansicyan": (58, 150, 221),
        "ansired": (197, 15, 31),
        "ansimagenta": (136, 23, 152),
        "ansiyellow": (193, 156, 0),
        "ansigray": (204, 204, 204),
        "ansibrightblack": (118, 118, 118),
        "ansibrightblue": (59, 120, 255),
        "ansibrightgreen": (22, 198, 12),
        "ansibrightcyan": (97, 214, 214),
        "ansibrightred": (231, 72, 86),
        "ansibrightmagenta": (180, 0, 158),
        "ansibrightyellow": (249, 241, 165),
        "ansiwhite": (242, 242, 242),
    }
    return {k: f"#{r:02x}{g:02x}{b:02x}" for k, (r, g, b) in cmap.items()}


WIN10_COLOR_MAP = LazyObject(_win10_color_map, globals(), "WIN10_COLOR_MAP")


def _win_bold_color_map():
    """Map dark ansi colors to lighter version."""
    return {
        "ansiblack": "ansibrightblack",
        "ansiblue": "ansibrightblue",
        "ansigreen": "ansibrightgreen",
        "ansicyan": "ansibrightcyan",
        "ansired": "ansibrightred",
        "ansimagenta": "ansibrightmagenta",
        "ansiyellow": "ansibrightyellow",
        "ansigray": "ansiwhite",
    }


WIN_BOLD_COLOR_MAP = LazyObject(_win_bold_color_map, globals(), "WIN_BOLD_COLOR_MAP")


def hardcode_colors_for_win10(style_map):
    """Replace all ansi colors with hardcoded colors to avoid unreadable defaults
    in conhost.exe
    """
    modified_style = {}
    if not xsh.env["PROMPT_TOOLKIT_COLOR_DEPTH"]:
        xsh.env["PROMPT_TOOLKIT_COLOR_DEPTH"] = "DEPTH_24_BIT"
    # Replace all ansi colors with hardcoded colors to avoid unreadable defaults
    # in conhost.exe
    for token, style_str in style_map.items():
        for ansicolor in WIN10_COLOR_MAP:
            if ansicolor in style_str:
                if "bold" in style_str and "nobold" not in style_str:
                    # Win10  doesn't yet handle bold colors. Instead dark
                    # colors are mapped to their lighter version. We simulate
                    # the same here.
                    style_str.replace("bold", "")
                    hexcolor = WIN10_COLOR_MAP[
                        WIN_BOLD_COLOR_MAP.get(ansicolor, ansicolor)
                    ]
                else:
                    hexcolor = WIN10_COLOR_MAP[ansicolor]
                style_str = style_str.replace(ansicolor, hexcolor)
        modified_style[token] = style_str
    return modified_style


def ansicolors_to_ptk1_names(stylemap):
    """Converts ansicolor names in a stylemap to old PTK1 color names"""
    if pygments_version_info() and pygments_version_info() >= (2, 4, 0):
        return stylemap
    modified_stylemap = {}
    for token, style_str in stylemap.items():
        for color, ptk1_color in ANSICOLOR_NAMES_MAP.items():
            if "#" + color not in style_str:
                style_str = style_str.replace(color, ptk1_color)
        modified_stylemap[token] = style_str
    return modified_stylemap


def intensify_colors_for_cmd_exe(style_map):
    """Returns a modified style to where colors that maps to dark
    colors are replaced with brighter versions.
    """
    modified_style = {}
    replace_colors = {
        1: "ansibrightcyan",  # subst blue with bright cyan
        2: "ansibrightgreen",  # subst green with bright green
        4: "ansibrightred",  # subst red with bright red
        5: "ansibrightmagenta",  # subst magenta with bright magenta
        6: "ansibrightyellow",  # subst yellow with bright yellow
        9: "ansicyan",  # subst intense blue with dark cyan (more readable)
    }
    if xsh.shell.shell_type == "prompt_toolkit1":
        replace_colors = ansicolors_to_ptk1_names(replace_colors)
    for token, idx, _ in _get_color_indexes(style_map):
        if idx in replace_colors:
            modified_style[token] = replace_colors[idx]
    return modified_style


def intensify_colors_on_win_setter(enable):
    """Resets the style when setting the INTENSIFY_COLORS_ON_WIN
    environment variable.
    """
    enable = to_bool(enable)
    if xsh.shell is not None and hasattr(xsh.shell.shell.styler, "style_name"):
        delattr(xsh.shell.shell.styler, "style_name")
    return enable


def format_std_prepost(template, env=None):
    """Formats a template prefix/postfix string for a standard buffer.
    Returns a string suitable for prepending or appending.
    """
    if not template:
        return ""
    env = xsh.env if env is None else env
    invis = "\001\002"
    if xsh.shell is None:
        # shell hasn't fully started up (probably still in xonshrc)
        from xonsh.ansi_colors import ansi_partial_color_format
        from xonsh.prompt.base import PromptFormatter

        pf = PromptFormatter()
        s = pf(template)
        style = env.get("XONSH_COLOR_STYLE")
        s = ansi_partial_color_format(invis + s + invis, hide=False, style=style)
    else:
        # shell has fully started. do the normal thing
        shell = xsh.shell.shell
        try:
            s = shell.prompt_formatter(template)
        except Exception:
            print_exception()
        # \001\002 is there to fool pygments into not returning an empty string
        # for potentially empty input. This happens when the template is just a
        # color code with no visible text.
        s = shell.format_color(invis + s + invis, force_string=True)
    s = s.replace(invis, "")
    return s


_RE_STRING_START = "[bBprRuUf]*"
_RE_STRING_TRIPLE_DOUBLE = '"""'
_RE_STRING_TRIPLE_SINGLE = "'''"
_RE_STRING_DOUBLE = '"'
_RE_STRING_SINGLE = "'"
_STRINGS = (
    _RE_STRING_TRIPLE_DOUBLE,
    _RE_STRING_TRIPLE_SINGLE,
    _RE_STRING_DOUBLE,
    _RE_STRING_SINGLE,
)
RE_BEGIN_STRING = LazyObject(
    lambda: re.compile("(" + _RE_STRING_START + "(" + "|".join(_STRINGS) + "))"),
    globals(),
    "RE_BEGIN_STRING",
)
"""Regular expression matching the start of a string, including quotes and
leading characters (r, b, or u)"""

RE_STRING_START = LazyObject(
    lambda: re.compile(_RE_STRING_START), globals(), "RE_STRING_START"
)
"""Regular expression matching the characters before the quotes when starting a
string (r, b, or u, case insensitive)"""

RE_STRING_CONT = LazyDict(
    {
        '"': lambda: re.compile(r'((\\(.|\n))|([^"\\]))*'),
        "'": lambda: re.compile(r"((\\(.|\n))|([^'\\]))*"),
        '"""': lambda: re.compile(r'((\\(.|\n))|([^"\\])|("(?!""))|\n)*'),
        "'''": lambda: re.compile(r"((\\(.|\n))|([^'\\])|('(?!''))|\n)*"),
    },
    globals(),
    "RE_STRING_CONT",
)
"""Dictionary mapping starting quote sequences to regular expressions that
match the contents of a string beginning with those quotes (not including the
terminating quotes)"""


@lazyobject
def RE_COMPLETE_STRING():
    ptrn = (
        "^"
        + _RE_STRING_START
        + "(?P<quote>"
        + "|".join(_STRINGS)
        + ")"
        + ".*?(?P=quote)$"
    )
    return re.compile(ptrn, re.DOTALL)


def strip_simple_quotes(s):
    """Gets rid of single quotes, double quotes, single triple quotes, and
    single double quotes from a string, if present front and back of a string.
    Otherwiswe, does nothing.
    """
    starts_single = s.startswith("'")
    starts_double = s.startswith('"')
    if not starts_single and not starts_double:
        return s
    elif starts_single:
        ends_single = s.endswith("'")
        if not ends_single:
            return s
        elif s.startswith("'''") and s.endswith("'''") and len(s) >= 6:
            return s[3:-3]
        elif len(s) >= 2:
            return s[1:-1]
        else:
            return s
    else:
        # starts double
        ends_double = s.endswith('"')
        if not ends_double:
            return s
        elif s.startswith('"""') and s.endswith('"""') and len(s) >= 6:
            return s[3:-3]
        elif len(s) >= 2:
            return s[1:-1]
        else:
            return s


def check_for_partial_string(x):
    """Returns the starting index (inclusive), ending index (exclusive), and
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
        ender = re.sub(RE_STRING_START, "", quote)
        x = x[start + lenquote :]
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
        x = x[leninside + len(ender) :]
        # find the next match
        match = re.search(RE_BEGIN_STRING, x)
    numquotes = len(string_indices)
    if numquotes == 0:
        return (None, None, None)
    elif numquotes % 2:
        return (string_indices[-1], None, starting_quote[-1])
    else:
        return (string_indices[-2], string_indices[-1], starting_quote[-1])


# regular expressions for matching environment variables
# i.e $FOO, ${'FOO'}
@lazyobject
def POSIX_ENVVAR_REGEX():
    pat = r"""\$({(?P<quote>['"])|)(?P<envvar>\w+)((?P=quote)}|(?:\1\b))"""
    return re.compile(pat)


def expandvars(path):
    """Expand shell variables of the forms $var, ${var} and %var%.
    Unknown variables are left unchanged."""
    env = xsh.env
    if isinstance(path, bytes):
        path = path.decode(
            encoding=env.get("XONSH_ENCODING"), errors=env.get("XONSH_ENCODING_ERRORS")
        )
    elif isinstance(path, pathlib.Path):
        # get the path's string representation
        path = str(path)
    if "$" in path:
        shift = 0
        for match in POSIX_ENVVAR_REGEX.finditer(path):
            name = match.group("envvar")
            if name in env:
                detyper = env.get_detyper(name)
                val = env[name]
                value = str(val) if detyper is None else detyper(val)
                value = str(val) if value is None else value
                start_pos, end_pos = match.span()
                path_len_before_replace = len(path)
                path = path[: start_pos + shift] + value + path[end_pos + shift :]
                shift = shift + len(path) - path_len_before_replace
    return path


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
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    newfname = f"{base}.{timestamp}{ext}"
    shutil.move(fname, newfname)


def normabspath(p):
    """Returns as normalized absolute path, namely, normcase(abspath(p))"""
    return os.path.normcase(os.path.abspath(p))


def expanduser_abs_path(inp):
    """Provides user expanded absolute path"""
    return os.path.abspath(expanduser(inp))


WINDOWS_DRIVE_MATCHER = LazyObject(
    lambda: re.compile(r"^\w:"), globals(), "WINDOWS_DRIVE_MATCHER"
)


def expand_case_matching(s):
    """Expands a string to a case insensitive globable string."""
    t = []
    openers = {"[", "{"}
    closers = {"]", "}"}
    nesting = 0

    drive_part = WINDOWS_DRIVE_MATCHER.match(s) if ON_WINDOWS else None

    if drive_part:
        drive_part = drive_part.group(0)
        t.append(drive_part)
        s = s[len(drive_part) :]

    for c in s:
        if c in openers:
            nesting += 1
        elif c in closers:
            nesting -= 1
        elif nesting > 0:
            pass
        elif c.isalpha():
            folded = c.casefold()
            if len(folded) == 1:
                c = f"[{c.upper()}{c.lower()}]"
            else:
                newc = [f"[{f.upper()}{f.lower()}]?" for f in folded[:-1]]
                newc = "".join(newc)
                newc += f"[{folded[-1].upper()}{folded[-1].lower()}{c}]"
                c = newc
        t.append(c)
    return "".join(t)


def globpath(
    s, ignore_case=False, return_empty=False, sort_result=None, include_dotfiles=None
):
    """Simple wrapper around glob that also expands home and env vars."""
    o, s = _iglobpath(
        s,
        ignore_case=ignore_case,
        sort_result=sort_result,
        include_dotfiles=include_dotfiles,
    )
    o = list(o)
    no_match = [] if return_empty else [s]
    return o if len(o) != 0 else no_match


def _dotglobstr(s):
    modified = False
    dotted_s = s
    if "/*" in dotted_s:
        dotted_s = dotted_s.replace("/*", "/.*")
        dotted_s = dotted_s.replace("/.**/.*", "/**/.*")
        modified = True
    if dotted_s.startswith("*") and not dotted_s.startswith("**"):
        dotted_s = "." + dotted_s
        modified = True
    return dotted_s, modified


def _iglobpath(s, ignore_case=False, sort_result=None, include_dotfiles=None):
    s = xsh.expand_path(s)
    if sort_result is None:
        sort_result = xsh.env.get("GLOB_SORTED")
    if include_dotfiles is None:
        include_dotfiles = xsh.env.get("DOTGLOB")
    if ignore_case:
        s = expand_case_matching(s)
    if "**" in s and "**/*" not in s:
        s = s.replace("**", "**/*")
    if include_dotfiles:
        dotted_s, dotmodified = _dotglobstr(s)
    if sort_result:
        paths = glob.glob(s, recursive=True)
        if include_dotfiles and dotmodified:
            paths.extend(glob.iglob(dotted_s, recursive=True))
        paths.sort()
        paths = iter(paths)
    else:
        paths = glob.iglob(s, recursive=True)
        if include_dotfiles and dotmodified:
            paths = itertools.chain(glob.iglob(dotted_s, recursive=True), paths)
    return paths, s


def iglobpath(s, ignore_case=False, sort_result=None, include_dotfiles=None):
    """Simple wrapper around iglob that also expands home and env vars."""
    try:
        return _iglobpath(
            s,
            ignore_case=ignore_case,
            sort_result=sort_result,
            include_dotfiles=include_dotfiles,
        )[0]
    except IndexError:
        # something went wrong in the actual iglob() call
        return iter(())


def ensure_timestamp(t, datetime_format=None):
    if isinstance(t, (int, float)):
        return t
    try:
        return float(t)
    except (ValueError, TypeError):
        pass
    if datetime_format is None:
        datetime_format = xsh.env["XONSH_DATETIME_FORMAT"]
    if isinstance(t, datetime.datetime):
        t = t.timestamp()
    else:
        t = datetime.datetime.strptime(t, datetime_format).timestamp()
    return t


def format_datetime(dt):
    """Format datetime object to string base on $XONSH_DATETIME_FORMAT Env."""
    format_ = xsh.env["XONSH_DATETIME_FORMAT"]
    return dt.strftime(format_)


def columnize(elems, width=80, newline="\n"):
    """Takes an iterable of strings and returns a list of lines with the
    elements placed in columns. Each line will be at most *width* columns.
    The newline character will be appended to the end of each line.
    """
    sizes = [len(e) + 1 for e in elems]
    total = sum(sizes)
    nelem = len(elems)
    if total - 1 <= width:
        ncols = len(sizes)
        nrows = 1
        columns = [sizes]
        last_longest_row = total
        enter_loop = False
    else:
        ncols = 1
        nrows = len(sizes)
        columns = [sizes]
        last_longest_row = max(sizes)
        enter_loop = True
    while enter_loop:
        longest_row = sum(map(max, columns))
        if longest_row - 1 <= width:
            # we might be able to fit another column.
            ncols += 1
            nrows = nelem // ncols
            columns = [sizes[i * nrows : (i + 1) * nrows] for i in range(ncols)]
            last_longest_row = longest_row
        else:
            # we can't fit another column
            ncols -= 1
            nrows = nelem // ncols
            break
    pad = (width - last_longest_row + ncols) // ncols
    pad = pad if pad > 1 else 1
    data = [elems[i * nrows : (i + 1) * nrows] for i in range(ncols)]
    colwidths = [max(map(len, d)) + pad for d in data]
    colwidths[-1] -= pad
    row_t = "".join(["{{row[{i}]: <{{w[{i}]}}}}".format(i=i) for i in range(ncols)])
    row_t += newline
    lines = [
        row_t.format(row=row, w=colwidths)
        for row in itertools.zip_longest(*data, fillvalue="")
    ]
    return lines


ALIAS_KWARG_NAMES = frozenset(["args", "stdin", "stdout", "stderr", "spec", "stack"])


def unthreadable(f):
    """Decorator that specifies that a callable alias should be run only
    on the main thread process. This is often needed for debuggers and
    profilers.
    """
    f.__xonsh_threadable__ = False
    return f


def uncapturable(f):
    """Decorator that specifies that a callable alias should not be run with
    any capturing. This is often needed if the alias call interactive
    subprocess, like pagers and text editors.
    """
    f.__xonsh_capturable__ = False
    return f


def carriage_return():
    """Writes a carriage return to stdout, and nothing else."""
    print("\r", flush=True, end="")


def deprecated(deprecated_in=None, removed_in=None):
    """Parametrized decorator that deprecates a function in a graceful manner.

    Updates the decorated function's docstring to mention the version
    that deprecation occurred in and the version it will be removed
    in if both of these values are passed.

    When removed_in is not a release equal to or less than the current
    release, call ``warnings.warn`` with details, while raising
    ``DeprecationWarning``.

    When removed_in is a release equal to or less than the current release,
    raise an ``AssertionError``.

    Parameters
    ----------
    deprecated_in : str
        The version number that deprecated this function.
    removed_in : str
        The version number that this function will be removed in.
    """
    message_suffix = _deprecated_message_suffix(deprecated_in, removed_in)
    if not message_suffix:
        message_suffix = ""

    def decorated(func):
        warning_message = f"{func.__name__} has been deprecated"
        warning_message += message_suffix

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            _deprecated_error_on_expiration(func.__name__, removed_in)
            func(*args, **kwargs)
            warnings.warn(warning_message, DeprecationWarning)

        wrapped.__doc__ = (
            f"{wrapped.__doc__}\n\n{warning_message}"
            if wrapped.__doc__
            else warning_message
        )

        return wrapped

    return decorated


def _deprecated_message_suffix(deprecated_in, removed_in):
    if deprecated_in and removed_in:
        message_suffix = " in version {} and will be removed in version {}".format(
            deprecated_in, removed_in
        )
    elif deprecated_in and not removed_in:
        message_suffix = f" in version {deprecated_in}"
    elif not deprecated_in and removed_in:
        message_suffix = f" and will be removed in version {removed_in}"
    else:
        message_suffix = None

    return message_suffix


def _deprecated_error_on_expiration(name, removed_in):
    from packaging.version import Version

    if not removed_in:
        return
    elif Version(__version__) >= Version(removed_in):
        raise AssertionError(f"{name} has passed its version {removed_in} expiry date!")


def to_repr_pretty_(inst, p, cycle):
    name = f"{inst.__class__.__module__}.{inst.__class__.__name__}"
    with p.group(0, name + "(", ")"):
        if cycle:
            p.text("...")
        elif len(inst):
            p.break_()
            p.pretty(dict(inst))
