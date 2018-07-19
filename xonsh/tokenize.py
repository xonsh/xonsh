"""Tokenization help for xonsh programs.

This file is a modified version of tokenize.py form the Python 3.4 and 3.5
standard libraries (licensed under the Python Software Foundation License,
version 2), which provides tokenization help for Python programs.

It is modified to properly tokenize xonsh code, including backtick regex
path and several xonsh-specific operators.

A few pieces of this file are specific to the version of Python being used.
To find these pieces, search the PY35.

Original file credits:
   __author__ = 'Ka-Ping Yee <ping@lfw.org>'
   __credits__ = ('GvR, ESR, Tim Peters, Thomas Wouters, Fred Drake, '
                  'Skip Montanaro, Raymond Hettinger, Trent Nelson, '
                  'Michael Foord')
"""

import re
import io
import sys
import codecs
import builtins
import itertools
import collections
import token
from token import (AMPER, AMPEREQUAL, AT, CIRCUMFLEX,
                   CIRCUMFLEXEQUAL, COLON, COMMA, DEDENT, DOT, DOUBLESLASH,
                   DOUBLESLASHEQUAL, DOUBLESTAR, DOUBLESTAREQUAL, ENDMARKER, EQEQUAL,
                   EQUAL, ERRORTOKEN, GREATER, GREATEREQUAL, INDENT, LBRACE, LEFTSHIFT,
                   LEFTSHIFTEQUAL, LESS, LESSEQUAL, LPAR, LSQB, MINEQUAL, MINUS, NAME,
                   NEWLINE, NOTEQUAL, NUMBER, N_TOKENS, OP, PERCENT, PERCENTEQUAL, PLUS,
                   PLUSEQUAL, RBRACE, RIGHTSHIFT, RIGHTSHIFTEQUAL, RPAR, RSQB, SEMI,
                   SLASH, SLASHEQUAL, STAR, STAREQUAL, STRING, TILDE, VBAR, VBAREQUAL,
                   tok_name)

from xonsh.lazyasd import LazyObject
from xonsh.platform import PYTHON_VERSION_INFO

cookie_re = LazyObject(
    lambda: re.compile(r'^[ \t\f]*#.*coding[:=][ \t]*([-\w.]+)', re.ASCII),
    globals(), 'cookie_re')
blank_re = LazyObject(lambda: re.compile(br'^[ \t\f]*(?:[#\r\n]|$)', re.ASCII),
                      globals(), 'blank_re')

#
# token modifications
#
tok_name = tok_name.copy()
__all__ = token.__all__ + ["COMMENT", "tokenize", "detect_encoding",
                           "NL", "untokenize", "ENCODING", "TokenInfo",
                           "TokenError", 'SEARCHPATH', 'ATDOLLAR', 'ATEQUAL',
                           'DOLLARNAME', 'IOREDIRECT']
HAS_ASYNC = (3, 5, 0) <= PYTHON_VERSION_INFO < (3, 7, 0)
if HAS_ASYNC:
    ASYNC = token.ASYNC
    AWAIT = token.AWAIT
    ADDSPACE_TOKS = (NAME, NUMBER, ASYNC, AWAIT)
else:
    ADDSPACE_TOKS = (NAME, NUMBER)
del token  # must clean up token
PY35 = (3, 5, 0) <= PYTHON_VERSION_INFO
AUGASSIGN_OPS = r"[+\-*/%&@|^=<>]=?"
if not PY35:
    AUGASSIGN_OPS = AUGASSIGN_OPS.replace('@', '')


COMMENT = N_TOKENS
tok_name[COMMENT] = 'COMMENT'
NL = N_TOKENS + 1
tok_name[NL] = 'NL'
ENCODING = N_TOKENS + 2
tok_name[ENCODING] = 'ENCODING'
N_TOKENS += 3
SEARCHPATH = N_TOKENS
tok_name[N_TOKENS] = 'SEARCHPATH'
N_TOKENS += 1
IOREDIRECT = N_TOKENS
tok_name[N_TOKENS] = 'IOREDIRECT'
N_TOKENS += 1
DOLLARNAME = N_TOKENS
tok_name[N_TOKENS] = 'DOLLARNAME'
N_TOKENS += 1
ATDOLLAR = N_TOKENS
tok_name[N_TOKENS] = 'ATDOLLAR'
N_TOKENS += 1
ATEQUAL = N_TOKENS
tok_name[N_TOKENS] = 'ATEQUAL'
N_TOKENS += 1
_xonsh_tokens = {
    '?': 'QUESTION',
    '@=': 'ATEQUAL',
    '@$': 'ATDOLLAR',
    '||': 'DOUBLEPIPE',
    '&&': 'DOUBLEAMPER',
    '@(': 'ATLPAREN',
    '!(': 'BANGLPAREN',
    '![': 'BANGLBRACKET',
    '$(': 'DOLLARLPAREN',
    '$[': 'DOLLARLBRACKET',
    '${': 'DOLLARLBRACE',
    '??': 'DOUBLEQUESTION',
    '@$(': 'ATDOLLARLPAREN',
}

additional_parenlevs = frozenset({'@(', '!(', '![', '$(', '$[', '${', '@$('})

_glbs = globals()
for v in _xonsh_tokens.values():
    _glbs[v] = N_TOKENS
    tok_name[N_TOKENS] = v
    N_TOKENS += 1
    __all__.append(v)
del _glbs, v

EXACT_TOKEN_TYPES = {
    '(': LPAR,
    ')': RPAR,
    '[': LSQB,
    ']': RSQB,
    ':': COLON,
    ',': COMMA,
    ';': SEMI,
    '+': PLUS,
    '-': MINUS,
    '*': STAR,
    '/': SLASH,
    '|': VBAR,
    '&': AMPER,
    '<': LESS,
    '>': GREATER,
    '=': EQUAL,
    '.': DOT,
    '%': PERCENT,
    '{': LBRACE,
    '}': RBRACE,
    '==': EQEQUAL,
    '!=': NOTEQUAL,
    '<=': LESSEQUAL,
    '>=': GREATEREQUAL,
    '~': TILDE,
    '^': CIRCUMFLEX,
    '<<': LEFTSHIFT,
    '>>': RIGHTSHIFT,
    '**': DOUBLESTAR,
    '+=': PLUSEQUAL,
    '-=': MINEQUAL,
    '*=': STAREQUAL,
    '/=': SLASHEQUAL,
    '%=': PERCENTEQUAL,
    '&=': AMPEREQUAL,
    '|=': VBAREQUAL,
    '^=': CIRCUMFLEXEQUAL,
    '<<=': LEFTSHIFTEQUAL,
    '>>=': RIGHTSHIFTEQUAL,
    '**=': DOUBLESTAREQUAL,
    '//': DOUBLESLASH,
    '//=': DOUBLESLASHEQUAL,
    '@': AT,
}

EXACT_TOKEN_TYPES.update(_xonsh_tokens)


class TokenInfo(collections.namedtuple('TokenInfo', 'type string start end line')):
    def __repr__(self):
        annotated_type = '%d (%s)' % (self.type, tok_name[self.type])
        return ('TokenInfo(type=%s, string=%r, start=%r, end=%r, line=%r)' %
                self._replace(type=annotated_type))

    @property
    def exact_type(self):
        if self.type == OP and self.string in EXACT_TOKEN_TYPES:
            return EXACT_TOKEN_TYPES[self.string]
        else:
            return self.type


def group(*choices):
    return '(' + '|'.join(choices) + ')'


def tokany(*choices):
    return group(*choices) + '*'


def maybe(*choices):
    return group(*choices) + '?'


# Note: we use unicode matching for names ("\w") but ascii matching for
# number literals.
Whitespace = r'[ \f\t]*'
Comment = r'#[^\r\n]*'
Ignore = Whitespace + tokany(r'\\\r?\n' + Whitespace) + maybe(Comment)
Name_RE = r'\$?\w+'

Hexnumber = r'0[xX](?:_?[0-9a-fA-F])+'
Binnumber = r'0[bB](?:_?[01])+'
Octnumber = r'0[oO](?:_?[0-7])+'
Decnumber = r'(?:0(?:_?0)*|[1-9](?:_?[0-9])*)'
Intnumber = group(Hexnumber, Binnumber, Octnumber, Decnumber)
Exponent = r'[eE][-+]?[0-9](?:_?[0-9])*'
Pointfloat = group(r'[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?',
                   r'\.[0-9](?:_?[0-9])*') + maybe(Exponent)
Expfloat = r'[0-9](?:_?[0-9])*' + Exponent
Floatnumber = group(Pointfloat, Expfloat)
Imagnumber = group(r'[0-9](?:_?[0-9])*[jJ]', Floatnumber + r'[jJ]')
Number = group(Imagnumber, Floatnumber, Intnumber)

StringPrefix = r'(?:[bBp][rR]?|[rR][bBpfF]?|[uU]|[fF][rR]?)?'

# Tail end of ' string.
Single = r"[^'\\]*(?:\\.[^'\\]*)*'"
# Tail end of " string.
Double = r'[^"\\]*(?:\\.[^"\\]*)*"'
# Tail end of ''' string.
Single3 = r"[^'\\]*(?:(?:\\.|'(?!''))[^'\\]*)*'''"
# Tail end of """ string.
Double3 = r'[^"\\]*(?:(?:\\.|"(?!""))[^"\\]*)*"""'
Triple = group(StringPrefix + "'''", StringPrefix + '"""')
# Single-line ' or " string.
String = group(StringPrefix + r"'[^\n'\\]*(?:\\.[^\n'\\]*)*'",
               StringPrefix + r'"[^\n"\\]*(?:\\.[^\n"\\]*)*"')

# Xonsh-specific Syntax
SearchPath = r"((?:[rgp]+|@\w*)?)`([^\n`\\]*(?:\\.[^\n`\\]*)*)`"

# Because of leftmost-then-longest match semantics, be sure to put the
# longest operators first (e.g., if = came before ==, == would get
# recognized as two instances of =).
_redir_names = ('out', 'all', 'err', 'e', '2', 'a', '&', '1', 'o')
_redir_map = (
    # stderr to stdout
    'err>out', 'err>&1', '2>out', 'err>o', 'err>1', 'e>out', 'e>&1',
    '2>&1', 'e>o', '2>o', 'e>1', '2>1',
    # stdout to stderr
    'out>err', 'out>&2', '1>err', 'out>e', 'out>2', 'o>err', 'o>&2',
    '1>&2', 'o>e', '1>e', 'o>2', '1>2',
)
IORedirect = group(group(*_redir_map), '{}>>?'.format(group(*_redir_names)))
_redir_check = set(_redir_map)
_redir_check = {'{}>'.format(i) for i in _redir_names}.union(_redir_check)
_redir_check = {'{}>>'.format(i) for i in _redir_names}.union(_redir_check)
_redir_check = frozenset(_redir_check)
Operator = group(r"\*\*=?", r">>=?", r"<<=?", r"!=", r"//=?", r"->",
                 r"@\$\(?", r'\|\|', '&&', r'@\(', r'!\(', r'!\[', r'\$\(',
                 r'\$\[', '\${', r'\?\?', r'\?', AUGASSIGN_OPS, r"~")

Bracket = '[][(){}]'
Special = group(r'\r?\n', r'\.\.\.', r'[:;.,@]')
Funny = group(Operator, Bracket, Special)

PlainToken = group(IORedirect, Number, Funny, String, Name_RE, SearchPath)

# First (or only) line of ' or " string.
ContStr = group(StringPrefix + r"'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                group("'", r'\\\r?\n'),
                StringPrefix + r'"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                group('"', r'\\\r?\n'))
PseudoExtras = group(r'\\\r?\n|\Z', Comment, Triple, SearchPath)
PseudoToken = Whitespace + group(PseudoExtras, IORedirect, Number, Funny,
                                 ContStr, Name_RE)


def _compile(expr):
    return re.compile(expr, re.UNICODE)


endpats = {"'": Single, '"': Double,
           "'''": Single3, '"""': Double3,
           "r'''": Single3, 'r"""': Double3,
           "b'''": Single3, 'b"""': Double3,
           "f'''": Single3, 'f"""': Double3,
           "R'''": Single3, 'R"""': Double3,
           "B'''": Single3, 'B"""': Double3,
           "F'''": Single3, 'F"""': Double3,
           "br'''": Single3, 'br"""': Double3,
           "fr'''": Single3, 'fr"""': Double3,
           "bR'''": Single3, 'bR"""': Double3,
           "Br'''": Single3, 'Br"""': Double3,
           "BR'''": Single3, 'BR"""': Double3,
           "rb'''": Single3, 'rb"""': Double3,
           "rf'''": Single3, 'rf"""': Double3,
           "Rb'''": Single3, 'Rb"""': Double3,
           "Fr'''": Single3, 'Fr"""': Double3,
           "rB'''": Single3, 'rB"""': Double3,
           "rF'''": Single3, 'rF"""': Double3,
           "RB'''": Single3, 'RB"""': Double3,
           "RF'''": Single3, 'RF"""': Double3,
           "u'''": Single3, 'u"""': Double3,
           "U'''": Single3, 'U"""': Double3,
           "p'''": Single3, 'p"""': Double3,
           "pr'''": Single3, 'pr"""': Double3,
           "pR'''": Single3, 'pR"""': Double3,
           "rp'''": Single3, 'rp"""': Double3,
           "Rp'''": Single3, 'Rp"""': Double3,
           'r': None, 'R': None, 'b': None, 'B': None,
           'u': None, 'U': None, 'p': None, 'f': None,
           'F': None}

triple_quoted = {}
for t in ("'''", '"""',
          "r'''", 'r"""', "R'''", 'R"""',
          "b'''", 'b"""', "B'''", 'B"""',
          "f'''", 'f"""', "F'''", 'F"""',
          "br'''", 'br"""', "Br'''", 'Br"""',
          "bR'''", 'bR"""', "BR'''", 'BR"""',
          "rb'''", 'rb"""', "rB'''", 'rB"""',
          "Rb'''", 'Rb"""', "RB'''", 'RB"""',
          "fr'''", 'fr"""', "Fr'''", 'Fr"""',
          "fR'''", 'fR"""', "FR'''", 'FR"""',
          "rf'''", 'rf"""', "rF'''", 'rF"""',
          "Rf'''", 'Rf"""', "RF'''", 'RF"""',
          "u'''", 'u"""', "U'''", 'U"""',
          "p'''", 'p""""', "pr'''", 'pr""""',
          "pR'''", 'pR""""', "rp'''", 'rp""""',
          "Rp'''", 'Rp""""',
          ):
    triple_quoted[t] = t
single_quoted = {}
for t in ("'", '"',
          "r'", 'r"', "R'", 'R"',
          "b'", 'b"', "B'", 'B"',
          "f'", 'f"', "F'", 'F"',
          "br'", 'br"', "Br'", 'Br"',
          "bR'", 'bR"', "BR'", 'BR"',
          "rb'", 'rb"', "rB'", 'rB"',
          "Rb'", 'Rb"', "RB'", 'RB"',
          "fr'", 'fr"', "Fr'", 'Fr"',
          "fR'", 'fR"', "FR'", 'FR"',
          "rf'", 'rf"', "rF'", 'rF"',
          "Rf'", 'Rf"', "RF'", 'RF"',
          "u'", 'u"', "U'", 'U"',
          "p'", 'p"', "pr'", 'pr"',
          "pR'", 'pR"', "rp'", 'rp"',
          "Rp'", 'Rp"',
          ):
    single_quoted[t] = t

tabsize = 8


class TokenError(Exception):
    pass


class StopTokenizing(Exception):
    pass


class Untokenizer:
    def __init__(self):
        self.tokens = []
        self.prev_row = 1
        self.prev_col = 0
        self.encoding = None

    def add_whitespace(self, start):
        row, col = start
        if row < self.prev_row or row == self.prev_row and col < self.prev_col:
            raise ValueError("start ({},{}) precedes previous end ({},{})"
                             .format(row, col, self.prev_row, self.prev_col))
        row_offset = row - self.prev_row
        if row_offset:
            self.tokens.append("\\\n" * row_offset)
            self.prev_col = 0
        col_offset = col - self.prev_col
        if col_offset:
            self.tokens.append(" " * col_offset)

    def untokenize(self, iterable):
        it = iter(iterable)
        indents = []
        startline = False
        for t in it:
            if len(t) == 2:
                self.compat(t, it)
                break
            tok_type, token, start, end, line = t
            if tok_type == ENCODING:
                self.encoding = token
                continue
            if tok_type == ENDMARKER:
                break
            if tok_type == INDENT:
                indents.append(token)
                continue
            elif tok_type == DEDENT:
                indents.pop()
                self.prev_row, self.prev_col = end
                continue
            elif tok_type in (NEWLINE, NL):
                startline = True
            elif startline and indents:
                indent = indents[-1]
                if start[1] >= len(indent):
                    self.tokens.append(indent)
                    self.prev_col = len(indent)
                startline = False
            self.add_whitespace(start)
            self.tokens.append(token)
            self.prev_row, self.prev_col = end
            if tok_type in (NEWLINE, NL):
                self.prev_row += 1
                self.prev_col = 0
        return "".join(self.tokens)

    def compat(self, token, iterable):
        indents = []
        toks_append = self.tokens.append
        startline = token[0] in (NEWLINE, NL)
        prevstring = False

        for tok in itertools.chain([token], iterable):
            toknum, tokval = tok[:2]
            if toknum == ENCODING:
                self.encoding = tokval
                continue

            if toknum in ADDSPACE_TOKS:
                tokval += ' '

            # Insert a space between two consecutive strings
            if toknum == STRING:
                if prevstring:
                    tokval = ' ' + tokval
                prevstring = True
            else:
                prevstring = False

            if toknum == INDENT:
                indents.append(tokval)
                continue
            elif toknum == DEDENT:
                indents.pop()
                continue
            elif toknum in (NEWLINE, NL):
                startline = True
            elif startline and indents:
                toks_append(indents[-1])
                startline = False
            toks_append(tokval)


def untokenize(iterable):
    """Transform tokens back into Python source code.
    It returns a bytes object, encoded using the ENCODING
    token, which is the first token sequence output by tokenize.

    Each element returned by the iterable must be a token sequence
    with at least two elements, a token number and token value.  If
    only two tokens are passed, the resulting output is poor.

    Round-trip invariant for full input:
        Untokenized source will match input source exactly

    Round-trip invariant for limited intput:
        # Output bytes will tokenize the back to the input
        t1 = [tok[:2] for tok in tokenize(f.readline)]
        newcode = untokenize(t1)
        readline = BytesIO(newcode).readline
        t2 = [tok[:2] for tok in tokenize(readline)]
        assert t1 == t2
    """
    ut = Untokenizer()
    out = ut.untokenize(iterable)
    if ut.encoding is not None:
        out = out.encode(ut.encoding)
    return out


def _get_normal_name(orig_enc):
    """Imitates get_normal_name in tokenizer.c."""
    # Only care about the first 12 characters.
    enc = orig_enc[:12].lower().replace("_", "-")
    if enc == "utf-8" or enc.startswith("utf-8-"):
        return "utf-8"
    if enc in ("latin-1", "iso-8859-1", "iso-latin-1") or \
            enc.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
        return "iso-8859-1"
    return orig_enc


def detect_encoding(readline):
    """
    The detect_encoding() function is used to detect the encoding that should
    be used to decode a Python source file.  It requires one argument, readline,
    in the same way as the tokenize() generator.

    It will call readline a maximum of twice, and return the encoding used
    (as a string) and a list of any lines (left as bytes) it has read in.

    It detects the encoding from the presence of a utf-8 bom or an encoding
    cookie as specified in pep-0263.  If both a bom and a cookie are present,
    but disagree, a SyntaxError will be raised.  If the encoding cookie is an
    invalid charset, raise a SyntaxError.  Note that if a utf-8 bom is found,
    'utf-8-sig' is returned.

    If no encoding is specified, then the default of 'utf-8' will be returned.
    """
    try:
        filename = readline.__self__.name
    except AttributeError:
        filename = None
    bom_found = False
    encoding = None
    default = 'utf-8'

    def read_or_stop():
        try:
            return readline()
        except StopIteration:
            return b''

    def find_cookie(line):
        try:
            # Decode as UTF-8. Either the line is an encoding declaration,
            # in which case it should be pure ASCII, or it must be UTF-8
            # per default encoding.
            line_string = line.decode('utf-8')
        except UnicodeDecodeError:
            msg = "invalid or missing encoding declaration"
            if filename is not None:
                msg = '{} for {!r}'.format(msg, filename)
            raise SyntaxError(msg)

        match = cookie_re.match(line_string)
        if not match:
            return None
        encoding = _get_normal_name(match.group(1))
        try:
            codecs.lookup(encoding)
        except LookupError:
            # This behaviour mimics the Python interpreter
            if filename is None:
                msg = "unknown encoding: " + encoding
            else:
                msg = "unknown encoding for {!r}: {}".format(filename,
                                                             encoding)
            raise SyntaxError(msg)

        if bom_found:
            if encoding != 'utf-8':
                # This behaviour mimics the Python interpreter
                if filename is None:
                    msg = 'encoding problem: utf-8'
                else:
                    msg = 'encoding problem for {!r}: utf-8'.format(filename)
                raise SyntaxError(msg)
            encoding += '-sig'
        return encoding

    first = read_or_stop()
    if first.startswith(codecs.BOM_UTF8):
        bom_found = True
        first = first[3:]
        default = 'utf-8-sig'
    if not first:
        return default, []

    encoding = find_cookie(first)
    if encoding:
        return encoding, [first]
    if not blank_re.match(first):
        return default, [first]

    second = read_or_stop()
    if not second:
        return default, [first]

    encoding = find_cookie(second)
    if encoding:
        return encoding, [first, second]

    return default, [first, second]


def tokopen(filename):
    """Open a file in read only mode using the encoding detected by
    detect_encoding().
    """
    buffer = builtins.open(filename, 'rb')
    try:
        encoding, lines = detect_encoding(buffer.readline)
        buffer.seek(0)
        text = io.TextIOWrapper(buffer, encoding, line_buffering=True)
        text.mode = 'r'
        return text
    except Exception:
        buffer.close()
        raise


def _tokenize(readline, encoding):
    lnum = parenlev = continued = 0
    numchars = '0123456789'
    contstr, needcont = '', 0
    contline = None
    indents = [0]

    # 'stashed' and 'async_*' are used for async/await parsing
    stashed = None
    async_def = False
    async_def_indent = 0
    async_def_nl = False

    if encoding is not None:
        if encoding == "utf-8-sig":
            # BOM will already have been stripped.
            encoding = "utf-8"
        yield TokenInfo(ENCODING, encoding, (0, 0), (0, 0), '')
    while True:  # loop over lines in stream
        try:
            line = readline()
        except StopIteration:
            line = b''

        if encoding is not None:
            line = line.decode(encoding)
        lnum += 1
        pos, max = 0, len(line)

        if contstr:  # continued string
            if not line:
                raise TokenError("EOF in multi-line string", strstart)
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                yield TokenInfo(STRING, contstr + line[:end],
                                strstart, (lnum, end), contline + line)
                contstr, needcont = '', 0
                contline = None
            elif needcont and line[-2:] != '\\\n' and line[-3:] != '\\\r\n':
                yield TokenInfo(ERRORTOKEN, contstr + line,
                                strstart, (lnum, len(line)), contline)
                contstr = ''
                contline = None
                continue
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        elif parenlev == 0 and not continued:  # new statement
            if not line:
                break
            column = 0
            while pos < max:  # measure leading whitespace
                if line[pos] == ' ':
                    column += 1
                elif line[pos] == '\t':
                    column = (column // tabsize + 1) * tabsize
                elif line[pos] == '\f':
                    column = 0
                else:
                    break
                pos += 1
            if pos == max:
                break

            if line[pos] in '#\r\n':  # skip comments or blank lines
                if line[pos] == '#':
                    comment_token = line[pos:].rstrip('\r\n')
                    nl_pos = pos + len(comment_token)
                    yield TokenInfo(COMMENT, comment_token,
                                    (lnum, pos), (lnum, pos + len(comment_token)), line)
                    yield TokenInfo(NL, line[nl_pos:],
                                    (lnum, nl_pos), (lnum, len(line)), line)
                else:
                    yield TokenInfo((NL, COMMENT)[line[pos] == '#'], line[pos:],
                                    (lnum, pos), (lnum, len(line)), line)
                continue

            if column > indents[-1]:  # count indents or dedents
                indents.append(column)
                yield TokenInfo(INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
            while column < indents[-1]:
                if column not in indents:
                    raise IndentationError(
                        "unindent does not match any outer indentation level",
                        ("<tokenize>", lnum, pos, line))
                indents = indents[:-1]

                if async_def and async_def_indent >= indents[-1]:
                    async_def = False
                    async_def_nl = False
                    async_def_indent = 0

                yield TokenInfo(DEDENT, '', (lnum, pos), (lnum, pos), line)

            if async_def and async_def_nl and async_def_indent >= indents[-1]:
                async_def = False
                async_def_nl = False
                async_def_indent = 0

        else:  # continued statement
            if not line:
                raise TokenError("EOF in multi-line statement", (lnum, 0))
            continued = 0

        while pos < max:
            pseudomatch = _compile(PseudoToken).match(line, pos)
            if pseudomatch:  # scan for tokens
                start, end = pseudomatch.span(1)
                spos, epos, pos = (lnum, start), (lnum, end), end
                if start == end:
                    continue
                token, initial = line[start:end], line[start]

                if token in _redir_check:
                    yield TokenInfo(IOREDIRECT, token, spos, epos, line)
                elif (initial in numchars or  # ordinary number
                        (initial == '.' and token != '.' and token != '...')):
                    yield TokenInfo(NUMBER, token, spos, epos, line)
                elif initial in '\r\n':
                    if stashed:
                        yield stashed
                        stashed = None
                    if parenlev > 0:
                        yield TokenInfo(NL, token, spos, epos, line)
                    else:
                        yield TokenInfo(NEWLINE, token, spos, epos, line)
                        if async_def:
                            async_def_nl = True

                elif initial == '#':
                    assert not token.endswith("\n")
                    if stashed:
                        yield stashed
                        stashed = None
                    yield TokenInfo(COMMENT, token, spos, epos, line)
                # Xonsh-specific Regex Globbing
                elif re.match(SearchPath, token):
                    yield TokenInfo(SEARCHPATH, token, spos, epos, line)
                elif token in triple_quoted:
                    endprog = _compile(endpats[token])
                    endmatch = endprog.match(line, pos)
                    if endmatch:  # all on one line
                        pos = endmatch.end(0)
                        token = line[start:pos]
                        yield TokenInfo(STRING, token, spos, (lnum, pos), line)
                    else:
                        strstart = (lnum, start)  # multiple lines
                        contstr = line[start:]
                        contline = line
                        break
                elif initial in single_quoted or \
                        token[:2] in single_quoted or \
                        token[:3] in single_quoted:
                    if token[-1] == '\n':  # continued string
                        strstart = (lnum, start)
                        endprog = _compile(endpats[initial] or
                                           endpats[token[1]] or
                                           endpats[token[2]])
                        contstr, needcont = line[start:], 1
                        contline = line
                        break
                    else:  # ordinary string
                        yield TokenInfo(STRING, token, spos, epos, line)
                elif token.startswith('$') and token[1:].isidentifier():
                    yield TokenInfo(DOLLARNAME, token, spos, epos, line)
                elif initial.isidentifier():  # ordinary name
                    if token in ('async', 'await'):
                        if async_def:
                            yield TokenInfo(
                                ASYNC if token == 'async' else AWAIT,
                                token, spos, epos, line)
                            continue

                    tok = TokenInfo(NAME, token, spos, epos, line)
                    if token == 'async' and not stashed:
                        stashed = tok
                        continue

                    if HAS_ASYNC and token == 'def' and \
                            (stashed and stashed.type == NAME and
                             stashed.string == 'async'):
                        async_def = True
                        async_def_indent = indents[-1]

                        yield TokenInfo(ASYNC, stashed.string,
                                        stashed.start, stashed.end,
                                        stashed.line)
                        stashed = None

                    if stashed:
                        yield stashed
                        stashed = None

                    yield tok
                elif token == '\\\n' or token == '\\\r\n':  # continued stmt
                    continued = 1
                    yield TokenInfo(ERRORTOKEN, token, spos, epos, line)
                elif initial == '\\':  # continued stmt
                    # for cases like C:\\path\\to\\file
                    continued = 1
                else:
                    if initial in '([{':
                        parenlev += 1
                    elif initial in ')]}':
                        parenlev -= 1
                    elif token in additional_parenlevs:
                        parenlev += 1
                    if stashed:
                        yield stashed
                        stashed = None
                    yield TokenInfo(OP, token, spos, epos, line)
            else:
                yield TokenInfo(ERRORTOKEN, line[pos],
                                (lnum, pos), (lnum, pos + 1), line)
                pos += 1

    if stashed:
        yield stashed
        stashed = None

    for indent in indents[1:]:  # pop remaining indent levels
        yield TokenInfo(DEDENT, '', (lnum, 0), (lnum, 0), '')
    yield TokenInfo(ENDMARKER, '', (lnum, 0), (lnum, 0), '')


def tokenize(readline):
    """
    The tokenize() generator requires one argument, readline, which
    must be a callable object which provides the same interface as the
    readline() method of built-in file objects.  Each call to the function
    should return one line of input as bytes.  Alternately, readline
    can be a callable function terminating with StopIteration:
        readline = open(myfile, 'rb').__next__  # Example of alternate readline

    The generator produces 5-tuples with these members: the token type; the
    token string; a 2-tuple (srow, scol) of ints specifying the row and
    column where the token begins in the source; a 2-tuple (erow, ecol) of
    ints specifying the row and column where the token ends in the source;
    and the line on which the token was found.  The line passed is the
    logical line; continuation lines are included.

    The first token sequence will always be an ENCODING token
    which tells you which encoding was used to decode the bytes stream.
    """
    encoding, consumed = detect_encoding(readline)
    rl_gen = iter(readline, b"")
    empty = itertools.repeat(b"")
    return _tokenize(itertools.chain(consumed, rl_gen, empty).__next__, encoding)


# An undocumented, backwards compatible, API for all the places in the standard
# library that expect to be able to use tokenize with strings
def generate_tokens(readline):
    return _tokenize(readline, None)


def tokenize_main():
    import argparse

    # Helper error handling routines
    def perror(message):
        print(message, file=sys.stderr)

    def error(message, filename=None, location=None):
        if location:
            args = (filename,) + location + (message,)
            perror("%s:%d:%d: error: %s" % args)
        elif filename:
            perror("%s: error: %s" % (filename, message))
        else:
            perror("error: %s" % message)
        sys.exit(1)

    # Parse the arguments and options
    parser = argparse.ArgumentParser(prog='python -m tokenize')
    parser.add_argument(dest='filename', nargs='?',
                        metavar='filename.py',
                        help='the file to tokenize; defaults to stdin')
    parser.add_argument('-e', '--exact', dest='exact', action='store_true',
                        help='display token names using the exact type')
    args = parser.parse_args()

    try:
        # Tokenize the input
        if args.filename:
            filename = args.filename
            with builtins.open(filename, 'rb') as f:
                tokens = list(tokenize(f.readline))
        else:
            filename = "<stdin>"
            tokens = _tokenize(sys.stdin.readline, None)

        # Output the tokenization
        for token in tokens:
            token_type = token.type
            if args.exact:
                token_type = token.exact_type
            token_range = "%d,%d-%d,%d:" % (token.start + token.end)
            print("%-20s%-15s%-15r" %
                  (token_range, tok_name[token_type], token.string))
    except IndentationError as err:
        line, column = err.args[1][1:3]
        error(err.args[0], filename, (line, column))
    except TokenError as err:
        line, column = err.args[1]
        error(err.args[0], filename, (line, column))
    except SyntaxError as err:
        error(err, filename)
    except OSError as err:
        error(err)
    except KeyboardInterrupt:
        print("interrupted\n")
    except Exception as err:
        perror("unexpected error: %s" % err)
        raise
