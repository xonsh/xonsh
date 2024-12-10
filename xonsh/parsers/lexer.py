"""Lexer for xonsh code.

Written using a hybrid of ``tokenize`` and PLY.
"""

from __future__ import annotations

import io

# 'keyword' interferes with ast.keyword
import keyword as kwmod

from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers import lexer_consts as lc
from xonsh.parsers.lexer_helpers import (
    _is_not_lparen_and_rparen,
    _offset_from_prev_lines,
    check_bad_str_token,
)
from xonsh.parsers.ply.lex import LexToken
from xonsh.parsers.tokenize import (
    CASE,
    COMMENT,
    DEDENT,
    DOLLARNAME,
    ENCODING,
    ENDMARKER,
    ERRORTOKEN,
    GREATER,
    INDENT,
    IOREDIRECT1,
    IOREDIRECT2,
    LESS,
    MATCH,
    NAME,
    NEWLINE,
    NL,
    NUMBER,
    OP,
    RIGHTSHIFT,
    SEARCHPATH,
    STRING,
    TokenError,
    tokenize,
)
from xonsh.platform import PYTHON_VERSION_INFO


@lazyobject
def token_map():
    """Mapping from ``tokenize`` tokens (or token types) to PLY token types. If
    a simple one-to-one mapping from ``tokenize`` to PLY exists, the lexer will
    look it up here and generate a single PLY token of the given type.
    Otherwise, it will fall back to handling that token using one of the
    handlers in``special_handlers``.
    """
    tm = {}
    # operators
    _op_map = {
        # punctuation
        ",": "COMMA",
        ".": "PERIOD",
        ";": "SEMI",
        ":": "COLON",
        "...": "ELLIPSIS",
        # basic operators
        "+": "PLUS",
        "-": "MINUS",
        "*": "TIMES",
        "@": "AT",
        "/": "DIVIDE",
        "//": "DOUBLEDIV",
        "%": "MOD",
        "**": "POW",
        "|": "PIPE",
        "~": "TILDE",
        "^": "XOR",
        "<<": "LSHIFT",
        ">>": "RSHIFT",
        "<": "LT",
        "<=": "LE",
        ">": "GT",
        ">=": "GE",
        "==": "EQ",
        "!=": "NE",
        "->": "RARROW",
        # assignment operators
        "=": "EQUALS",
        "+=": "PLUSEQUAL",
        "-=": "MINUSEQUAL",
        "*=": "TIMESEQUAL",
        "@=": "ATEQUAL",
        "/=": "DIVEQUAL",
        "%=": "MODEQUAL",
        "**=": "POWEQUAL",
        "<<=": "LSHIFTEQUAL",
        ">>=": "RSHIFTEQUAL",
        "&=": "AMPERSANDEQUAL",
        "^=": "XOREQUAL",
        "|=": "PIPEEQUAL",
        "//=": "DOUBLEDIVEQUAL",
        # extra xonsh operators
        "?": "QUESTION",
        "??": "DOUBLE_QUESTION",
        "@$": "ATDOLLAR",
        "&": "AMPERSAND",
        ":=": "COLONEQUAL",
    }
    for op, typ in _op_map.items():
        tm[(OP, op)] = typ
    tm[IOREDIRECT1] = "IOREDIRECT1"
    tm[IOREDIRECT2] = "IOREDIRECT2"
    tm[STRING] = "STRING"
    tm[DOLLARNAME] = "DOLLAR_NAME"
    tm[NUMBER] = "NUMBER"
    tm[SEARCHPATH] = "SEARCHPATH"
    tm[NEWLINE] = "NEWLINE"
    tm[INDENT] = "INDENT"
    tm[DEDENT] = "DEDENT"
    # python 3.10 (backwards and name token compatible) tokens
    tm[MATCH] = "MATCH"
    tm[CASE] = "CASE"
    return tm


def handle_name(state, token):
    """Function for handling name tokens"""
    typ = "NAME"
    state["last"] = token
    needs_whitespace = token.string in lc.NEED_WHITESPACE
    has_whitespace = needs_whitespace and lc.RE_NEED_WHITESPACE.match(
        token.line[max(0, token.start[1] - 1) :]
    )
    if state["pymode"][-1][0]:
        if needs_whitespace and not has_whitespace:
            pass
        elif token.string in kwmod.kwlist + ["match", "case"]:
            typ = token.string.upper()
        yield _new_token(typ, token.string, token.start)
    else:
        if has_whitespace and token.string == "and":
            yield _new_token("AND", token.string, token.start)
        elif has_whitespace and token.string == "or":
            yield _new_token("OR", token.string, token.start)
        else:
            yield _new_token("NAME", token.string, token.start)


def _end_delimiter(state, token):
    py = state["pymode"]
    s = token.string
    l, c = token.start
    if len(py) > 1:
        mode, orig, match, pos = py.pop()
        if s != match:
            e = '"{}" at {} ends "{}" at {} (expected "{}")'
            return e.format(s, (l, c), orig, pos, match)
    else:
        return f'Unmatched "{s}" at line {l}, column {c}'


def handle_rparen(state, token):
    """
    Function for handling ``)``
    """
    e = _end_delimiter(state, token)
    if e is None or state["tolerant"]:
        state["last"] = token
        yield _new_token("RPAREN", ")", token.start)
    else:
        yield _new_token("ERRORTOKEN", e, token.start)


def handle_rbrace(state, token):
    """Function for handling ``}``"""
    e = _end_delimiter(state, token)
    if e is None or state["tolerant"]:
        state["last"] = token
        yield _new_token("RBRACE", "}", token.start)
    else:
        yield _new_token("ERRORTOKEN", e, token.start)


def handle_rbracket(state, token):
    """
    Function for handling ``]``
    """
    e = _end_delimiter(state, token)
    if e is None or state["tolerant"]:
        state["last"] = token
        yield _new_token("RBRACKET", "]", token.start)
    else:
        yield _new_token("ERRORTOKEN", e, token.start)


def handle_error_space(state, token):
    """
    Function for handling special whitespace characters in subprocess mode
    """
    if not state["pymode"][-1][0]:
        state["last"] = token
        yield _new_token("WS", token.string, token.start)
    else:
        yield from []


def handle_error_linecont(state, token):
    """Function for handling special line continuations as whitespace
    characters in subprocess mode.
    """
    if state["pymode"][-1][0]:
        return
    prev = state["last"]
    if prev.end != token.start:
        return  # previous token is separated by whitespace
    state["last"] = token
    yield _new_token("WS", "\\", token.start)


def handle_error_token(state, token):
    """
    Function for handling error tokens
    """
    state["last"] = token
    if token.string == "!":
        typ = "BANG"
    elif not state["pymode"][-1][0]:
        typ = "NAME"
    else:
        typ = "ERRORTOKEN"
    yield _new_token(typ, token.string, token.start)


def handle_ignore(state, token):
    """Function for handling tokens that should be ignored"""
    yield from []


def handle_double_amps(state, token):
    yield _new_token("AND", "and", token.start)


def handle_double_pipe(state, token):
    yield _new_token("OR", "or", token.start)


def handle_redirect(state, token):
    # The parser expects whitespace after a redirection in subproc mode.
    # If whitespace does not exist, we'll issue an empty whitespace
    # token before proceeding.
    state["last"] = token
    typ = token.type
    st = token.string
    key = (typ, st) if (typ, st) in token_map else typ
    new_tok = _new_token(token_map[key], st, token.start)
    if state["pymode"][-1][0]:
        if typ in (IOREDIRECT1, IOREDIRECT2):
            # Fix Python mode code that was incorrectly recognized as an
            # IOREDIRECT by the tokenizer (see issue #4994).
            # The tokenizer does not know when the code should be tokenized in
            # Python mode. By default, when it sees code like `2>`, it produces
            # an IOREDIRECT token. This call to `get_tokens` makes the
            # tokenizer run over the code again, knowing that it is *not* an
            # IOREDIRECT token.
            lineno, lexpos = token.start
            for tok in get_tokens(
                token.string, state["tolerant"], tokenize_ioredirects=False
            ):
                yield _new_token(tok.type, tok.value, (lineno, lexpos + tok.lexpos))
        else:
            yield new_tok
        return
    yield new_tok
    # add a whitespace token after a redirection, if we need to
    next_tok = next(state["stream"])
    if next_tok.start == token.end:
        yield _new_token("WS", "", token.end)
    yield from handle_token(state, next_tok)


def _make_matcher_handler(tok, typ, pymode, ender, handlers):
    matcher = (
        ")"
        if tok.endswith("(")
        else "}"
        if tok.endswith("{")
        else "]"
        if tok.endswith("[")
        else None
    )

    def _inner_handler(state, token):
        state["pymode"].append((pymode, tok, matcher, token.start))
        state["last"] = token
        yield _new_token(typ, tok, token.start)

    handlers[(OP, tok)] = _inner_handler


@lazyobject
def special_handlers():
    """Mapping from ``tokenize`` tokens (or token types) to the proper
    function for generating PLY tokens from them.  In addition to
    yielding PLY tokens, these functions may manipulate the Lexer's state.
    """
    sh = {
        NL: handle_ignore,
        COMMENT: handle_ignore,
        ENCODING: handle_ignore,
        ENDMARKER: handle_ignore,
        NAME: handle_name,
        ERRORTOKEN: handle_error_token,
        LESS: handle_redirect,
        GREATER: handle_redirect,
        RIGHTSHIFT: handle_redirect,
        IOREDIRECT1: handle_redirect,
        IOREDIRECT2: handle_redirect,
        (OP, "<"): handle_redirect,
        (OP, ">"): handle_redirect,
        (OP, ">>"): handle_redirect,
        (OP, ")"): handle_rparen,
        (OP, "}"): handle_rbrace,
        (OP, "]"): handle_rbracket,
        (OP, "&&"): handle_double_amps,
        (OP, "||"): handle_double_pipe,
        (ERRORTOKEN, " "): handle_error_space,
        (ERRORTOKEN, "\\\n"): handle_error_linecont,
        (ERRORTOKEN, "\\\r\n"): handle_error_linecont,
    }
    _make_matcher_handler("(", "LPAREN", True, ")", sh)
    _make_matcher_handler("[", "LBRACKET", True, "]", sh)
    _make_matcher_handler("{", "LBRACE", True, "}", sh)
    _make_matcher_handler("$(", "DOLLAR_LPAREN", False, ")", sh)
    _make_matcher_handler("$[", "DOLLAR_LBRACKET", False, "]", sh)
    _make_matcher_handler("${", "DOLLAR_LBRACE", True, "}", sh)
    _make_matcher_handler("!(", "BANG_LPAREN", False, ")", sh)
    _make_matcher_handler("![", "BANG_LBRACKET", False, "]", sh)
    _make_matcher_handler("@(", "AT_LPAREN", True, ")", sh)
    _make_matcher_handler("@$(", "ATDOLLAR_LPAREN", False, ")", sh)
    return sh


def handle_token(state, token):
    """
    General-purpose token handler.  Makes use of ``token_map`` or
    ``special_map`` to yield one or more PLY tokens from the given input.

    Parameters
    ----------
    state
        The current state of the lexer, including information about whether
        we are in Python mode or subprocess mode, which changes the lexer's
        behavior.  Also includes the stream of tokens yet to be considered.
    token
        The token (from ``tokenize``) currently under consideration
    """
    typ = token.type
    st = token.string
    pymode = state["pymode"][-1][0]
    if not pymode:
        if state["last"] is not None and state["last"].end != token.start:
            cur = token.start
            old = state["last"].end
            if cur[0] == old[0] and cur[1] > old[1]:
                yield _new_token("WS", token.line[old[1] : cur[1]], old)
    if (typ, st) in special_handlers:
        yield from special_handlers[(typ, st)](state, token)
    elif (typ, st) in token_map:
        state["last"] = token
        yield _new_token(token_map[(typ, st)], st, token.start)
    elif typ in special_handlers:
        yield from special_handlers[typ](state, token)
    elif typ in token_map:
        state["last"] = token
        yield _new_token(token_map[typ], st, token.start)
    else:
        m = f"Unexpected token: {token}"
        yield _new_token("ERRORTOKEN", m, token.start)


def get_tokens(s, tolerant, pymode=True, tokenize_ioredirects=True):
    """
    Given a string containing xonsh code, generates a stream of relevant PLY
    tokens using ``handle_token``.
    """
    state = {
        "indents": [0],
        "last": None,
        "pymode": [(pymode, "", "", (0, 0))],
        "stream": tokenize(
            io.BytesIO(s.encode("utf-8")).readline, tolerant, tokenize_ioredirects
        ),
        "tolerant": tolerant,
    }
    while True:
        try:
            token = next(state["stream"])
            yield from handle_token(state, token)
        except StopIteration:
            if len(state["pymode"]) > 1 and not tolerant:
                pm, o, m, p = state["pymode"][-1]
                l, c = p
                e = 'Unmatched "{}" at line {}, column {}'
                yield _new_token("ERRORTOKEN", e.format(o, l, c), (0, 0))
            break
        except TokenError as e:
            # this is recoverable in single-line mode (from the shell)
            # (e.g., EOF while scanning string literal)
            yield _new_token("ERRORTOKEN", e.args[0], (0, 0))
            break
        except IndentationError as e:
            # this is never recoverable
            yield _new_token("ERRORTOKEN", e, (0, 0))
            break


# synthesize a new PLY token
def _new_token(type, value, pos):
    o = LexToken()
    o.type = type
    o.value = value
    o.lineno, o.lexpos = pos
    return o


class Lexer:
    """Implements a lexer for the xonsh language."""

    _tokens: tuple[str, ...] | None = None

    def __init__(self, tolerant=False, pymode=True):
        """
        Attributes
        ----------
        fname : str
            Filename
        last : token
            The last token seen.
        lineno : int
            The last line number seen.
        tolerant : bool
            Tokenize without extra checks (e.g. paren matching).
            When True, ERRORTOKEN contains the erroneous string instead of an error msg.
        pymode : bool
            Start the lexer in Python mode.

        """
        self.fname = ""
        self.last = None
        self.beforelast = None
        self._tolerant = tolerant
        self._pymode = pymode
        self._token_stream = iter(())

    @property
    def tolerant(self):
        return self._tolerant

    def build(self, **kwargs):
        """Part of the PLY lexer API."""
        pass

    def reset(self):
        self._token_stream = iter(())
        self.last = None
        self.beforelast = None

    def input(self, s):
        """Calls the lexer on the string s."""
        self._token_stream = get_tokens(s, self._tolerant, self._pymode)

    def token(self):
        """Retrieves the next token."""
        self.beforelast, self.last = self.last, next(self._token_stream, None)
        return self.last

    def __iter__(self):
        t = self.token()
        while t is not None:
            yield t
            t = self.token()

    def split(self, s):
        """Splits a string into a list of strings which are whitespace-separated
        tokens.
        """
        self.input(s)
        elements = []
        l = c = -1
        ws = "WS"
        nl = "\n"
        for token in self:
            if token.type == ws:
                continue
            elif l < token.lineno:
                elements.append(token.value)
            elif len(elements) > 0 and c == token.lexpos:
                elements[-1] = elements[-1] + token.value
            else:
                elements.append(token.value)
            nnl = token.value.count(nl)
            if nnl == 0:
                l = token.lineno
                c = token.lexpos + len(token.value)
            else:
                l = token.lineno + nnl
                c = len(token.value.rpartition(nl)[-1])
        return elements

    #
    # All the tokens recognized by the lexer
    #
    @property
    def tokens(self):
        if self._tokens is None:
            kwlist = kwmod.kwlist[:]
            if (3, 9, 0) <= PYTHON_VERSION_INFO < (3, 10):
                kwlist.remove("__peg_parser__")
            t = (
                tuple(token_map.values())
                + (
                    "NAME",  # name tokens
                    "BANG",  # ! tokens
                    "WS",  # whitespace in subprocess mode
                    "LPAREN",
                    "RPAREN",  # ( )
                    "LBRACKET",
                    "RBRACKET",  # [ ]
                    "LBRACE",
                    "RBRACE",  # { }
                    "AT_LPAREN",  # @(
                    "BANG_LPAREN",  # !(
                    "BANG_LBRACKET",  # ![
                    "DOLLAR_LPAREN",  # $(
                    "DOLLAR_LBRACE",  # ${
                    "DOLLAR_LBRACKET",  # $[
                    "ATDOLLAR_LPAREN",  # @$(
                    "ERRORTOKEN",  # whoops!
                )
                + tuple(i.upper() for i in kwlist)
            )
            self._tokens = t
        return self._tokens

    def subproc_toks(
        self, line: str, mincol=-1, maxcol=None, returnline=False, greedy=False
    ) -> str | None:
        self.reset()
        self.input(line)
        toks = []
        lparens = []
        saw_macro = False
        end_offset = 0
        for tok in self:
            pos = tok.lexpos
            if tok.type not in lc.END_TOK_TYPES and pos >= maxcol:
                break
            if tok.type == "BANG":
                saw_macro = True
            if saw_macro and tok.type not in ("NEWLINE", "DEDENT"):
                toks.append(tok)
                continue
            if tok.type in lc.LPARENS:
                lparens.append(tok.type)
            if greedy and len(lparens) > 0 and "LPAREN" in lparens:
                toks.append(tok)
                if tok.type == "RPAREN":
                    lparens.pop()
                continue
            if len(toks) == 0 and tok.type in lc.BEG_TOK_SKIPS:
                continue  # handle indentation
            elif len(toks) > 0 and toks[-1].type in lc.END_TOK_TYPES:
                if _is_not_lparen_and_rparen(lparens, toks[-1]):
                    lparens.pop()  # don't continue or break
                elif pos < maxcol and tok.type not in ("NEWLINE", "DEDENT", "WS"):
                    if not greedy:
                        toks.clear()
                    if tok.type in lc.BEG_TOK_SKIPS:
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
                return None
        else:
            if len(toks) > 0 and toks[-1].type in lc.END_TOK_TYPES:
                if _is_not_lparen_and_rparen(lparens, toks[-1]):
                    pass
                elif greedy and toks[-1].type == "RPAREN":
                    pass
                else:
                    toks.pop()
            if len(toks) == 0:
                return None  # handle comment lines
            tok = toks[-1]
            pos = tok.lexpos
            if isinstance(tok.value, str):
                end_offset = len(tok.value.rstrip())
            else:
                el = line[pos:].split("#")[0].rstrip()
                end_offset = len(el)
        if len(toks) == 0:
            return None  # handle comment lines
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

    def find_next_break(self, line, mincol=0) -> int | None:
        """Finds the next break point in the line.

        This function may be useful in finding the maxcol argument of
        subproc_toks().
        """
        if mincol >= 1:
            line = line[mincol:]
        if lc.RE_END_TOKS.search(line) is None:
            return None
        maxcol = None
        lparens = []
        self.input(line)
        for tok in self:
            if tok.type in lc.LPARENS:
                lparens.append(tok.type)
            elif tok.type in lc.END_TOK_TYPES:
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
