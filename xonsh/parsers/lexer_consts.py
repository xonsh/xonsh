"""Lazy objects used by the lexer and xonsh.tools"""

import re

from xonsh.lib.lazyasd import LazyObject, lazyobject

NEED_WHITESPACE = frozenset(["and", "or"])


@lazyobject
def RE_NEED_WHITESPACE():
    pattern = r"\s?(" + "|".join(NEED_WHITESPACE) + r")(\s|[\\]$)"
    return re.compile(pattern)


@lazyobject
def END_TOK_TYPES():
    return frozenset(["SEMI", "AND", "OR", "RPAREN"])


@lazyobject
def BEG_TOK_SKIPS():
    return frozenset(["WS", "INDENT", "NOT", "LPAREN"])


@lazyobject
def LPARENS():
    return frozenset(
        ["LPAREN", "AT_LPAREN", "BANG_LPAREN", "DOLLAR_LPAREN", "ATDOLLAR_LPAREN"]
    )


RE_END_TOKS = LazyObject(
    lambda: re.compile(r"(;|and|\&\&|or|\|\||\))"), globals(), "RE_END_TOKS"
)
