"""Tests the xonsh lexer."""
import os
import sys
from collections.abc import Sequence

sys.path.insert(0, os.path.abspath(".."))  # FIXME
from pprint import pformat

import pytest

from xonsh.lexer import Lexer
from xonsh.ply.ply.lex import LexToken

LEXER_ARGS = {"lextab": "lexer_test_table", "debug": 0}


def ensure_tuple(x):
    if isinstance(x, LexToken):
        # line numbers can no longer be solely determined from the lexer
        # x = (x.type, x.value, x.lineno, x.lexpos)
        x = (x.type, x.value, x.lexpos)
    elif isinstance(x, tuple):
        pass
    elif isinstance(x, Sequence):
        x = tuple(x)
    else:
        raise TypeError(f"{x} is not a sequence")
    return x


def tokens_equal(x, y):
    """Tests whether two token are equal."""
    xtup = ensure_tuple(x)
    ytup = ensure_tuple(y)
    return xtup == ytup


def assert_token_equal(x, y):
    """Asserts that two tokens are equal."""
    if not tokens_equal(x, y):
        msg = f"The tokens differ: {x!r} != {y!r}"
        pytest.fail(msg)
    return True


def assert_tokens_equal(x, y):
    """Asserts that two token sequences are equal."""
    if len(x) != len(y):
        msg = "The tokens sequences have different lengths: {0!r} != {1!r}\n"
        msg += "# x\n{2}\n\n# y\n{3}"
        pytest.fail(msg.format(len(x), len(y), pformat(x), pformat(y)))
    diffs = [(a, b) for a, b in zip(x, y) if not tokens_equal(a, b)]
    if len(diffs) > 0:
        msg = ["The token sequences differ: "]
        for a, b in diffs:
            msg += ["", "- " + repr(a), "+ " + repr(b)]
        msg = "\n".join(msg)
        pytest.fail(msg)
    return True


def lex_input(inp: str):
    lex = Lexer()
    lex.input(inp)
    return list(lex)


def check_token(inp, exp):
    obs = lex_input(inp)
    if len(obs) != 1:
        msg = "The observed sequence does not have length-1: {0!r} != 1\n"
        msg += "# obs\n{1}"
        pytest.fail(msg.format(len(obs), pformat(obs)))
    return assert_token_equal(exp, obs[0])


def check_tokens(inp, exp):
    obs = lex_input(inp)
    return assert_tokens_equal(exp, obs)


def check_tokens_subproc(inp, exp, stop=-1):
    obs = lex_input(f"$[{inp}]")[1:stop]
    return assert_tokens_equal(exp, obs)


def test_int_literal():
    assert check_token("42", ["NUMBER", "42", 0])
    assert check_token("4_2", ["NUMBER", "4_2", 0])


def test_hex_literal():
    assert check_token("0x42", ["NUMBER", "0x42", 0])
    assert check_token("0x4_2", ["NUMBER", "0x4_2", 0])


def test_oct_o_literal():
    assert check_token("0o42", ["NUMBER", "0o42", 0])
    assert check_token("0o4_2", ["NUMBER", "0o4_2", 0])


def test_bin_literal():
    assert check_token("0b101010", ["NUMBER", "0b101010", 0])
    assert check_token("0b10_10_10", ["NUMBER", "0b10_10_10", 0])


def test_indent():
    exp = [("INDENT", "  \t  ", 0), ("NUMBER", "42", 5), ("DEDENT", "", 0)]
    assert check_tokens("  \t  42", exp)


def test_post_whitespace():
    inp = "42  \t  "
    exp = [("NUMBER", "42", 0)]
    assert check_tokens(inp, exp)


def test_internal_whitespace():
    inp = "42  +\t65"
    exp = [("NUMBER", "42", 0), ("PLUS", "+", 4), ("NUMBER", "65", 6)]
    assert check_tokens(inp, exp)


def test_indent_internal_whitespace():
    inp = " 42  +\t65"
    exp = [
        ("INDENT", " ", 0),
        ("NUMBER", "42", 1),
        ("PLUS", "+", 5),
        ("NUMBER", "65", 7),
        ("DEDENT", "", 0),
    ]
    assert check_tokens(inp, exp)


def test_assignment():
    inp = "x = 42"
    exp = [("NAME", "x", 0), ("EQUALS", "=", 2), ("NUMBER", "42", 4)]
    assert check_tokens(inp, exp)


def test_multiline():
    inp = "x\ny"
    exp = [("NAME", "x", 0), ("NEWLINE", "\n", 1), ("NAME", "y", 0)]
    assert check_tokens(inp, exp)


def test_atdollar_expression():
    inp = "@$(which python)"
    exp = [
        ("ATDOLLAR_LPAREN", "@$(", 0),
        ("NAME", "which", 3),
        ("WS", " ", 8),
        ("NAME", "python", 9),
        ("RPAREN", ")", 15),
    ]
    assert check_tokens(inp, exp)


def test_and():
    # no preceding whitespace or other tokens, so this
    # resolves to NAME, since it doesn't make sense for
    # Python code to start with "and"
    assert check_token("and", ["NAME", "and", 0])


def test_ampersand():
    assert check_token("&", ["AMPERSAND", "&", 0])


def test_not_really_and_pre():
    inp = "![foo-and]"
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "foo", 2),
        ("MINUS", "-", 5),
        ("NAME", "and", 6),
        ("RBRACKET", "]", 9),
    ]
    assert check_tokens(inp, exp)


def test_not_really_and_post():
    inp = "![and-bar]"
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "and", 2),
        ("MINUS", "-", 5),
        ("NAME", "bar", 6),
        ("RBRACKET", "]", 9),
    ]
    assert check_tokens(inp, exp)


def test_not_really_and_pre_post():
    inp = "![foo-and-bar]"
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "foo", 2),
        ("MINUS", "-", 5),
        ("NAME", "and", 6),
        ("MINUS", "-", 9),
        ("NAME", "bar", 10),
        ("RBRACKET", "]", 13),
    ]
    assert check_tokens(inp, exp)


def test_not_really_or_pre():
    inp = "![foo-or]"
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "foo", 2),
        ("MINUS", "-", 5),
        ("NAME", "or", 6),
        ("RBRACKET", "]", 8),
    ]
    assert check_tokens(inp, exp)


def test_not_really_or_post():
    inp = "![or-bar]"
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "or", 2),
        ("MINUS", "-", 4),
        ("NAME", "bar", 5),
        ("RBRACKET", "]", 8),
    ]
    assert check_tokens(inp, exp)


def test_not_really_or_pre_post():
    inp = "![foo-or-bar]"
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "foo", 2),
        ("MINUS", "-", 5),
        ("NAME", "or", 6),
        ("MINUS", "-", 8),
        ("NAME", "bar", 9),
        ("RBRACKET", "]", 12),
    ]
    assert check_tokens(inp, exp)


def test_subproc_line_cont_space():
    inp = (
        "![echo --option1 value1 \\\n"
        "     --option2 value2 \\\n"
        "     --optionZ valueZ]"
    )
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "echo", 2),
        ("WS", " ", 6),
        ("MINUS", "-", 7),
        ("MINUS", "-", 8),
        ("NAME", "option1", 9),
        ("WS", " ", 16),
        ("NAME", "value1", 17),
        ("WS", " ", 23),
        ("MINUS", "-", 5),
        ("MINUS", "-", 6),
        ("NAME", "option2", 7),
        ("WS", " ", 14),
        ("NAME", "value2", 15),
        ("WS", " ", 21),
        ("MINUS", "-", 5),
        ("MINUS", "-", 6),
        ("NAME", "optionZ", 7),
        ("WS", " ", 14),
        ("NAME", "valueZ", 15),
        ("RBRACKET", "]", 21),
    ]
    assert check_tokens(inp, exp)


def test_subproc_line_cont_nospace():
    inp = (
        "![echo --option1 value1\\\n"
        "     --option2 value2\\\n"
        "     --optionZ valueZ]"
    )
    exp = [
        ("BANG_LBRACKET", "![", 0),
        ("NAME", "echo", 2),
        ("WS", " ", 6),
        ("MINUS", "-", 7),
        ("MINUS", "-", 8),
        ("NAME", "option1", 9),
        ("WS", " ", 16),
        ("NAME", "value1", 17),
        ("WS", "\\", 23),
        ("MINUS", "-", 5),
        ("MINUS", "-", 6),
        ("NAME", "option2", 7),
        ("WS", " ", 14),
        ("NAME", "value2", 15),
        ("WS", "\\", 21),
        ("MINUS", "-", 5),
        ("MINUS", "-", 6),
        ("NAME", "optionZ", 7),
        ("WS", " ", 14),
        ("NAME", "valueZ", 15),
        ("RBRACKET", "]", 21),
    ]
    assert check_tokens(inp, exp)


def test_atdollar():
    assert check_token("@$", ["ATDOLLAR", "@$", 0])


def test_doubleamp():
    assert check_token("&&", ["AND", "and", 0])


def test_pipe():
    assert check_token("|", ["PIPE", "|", 0])


def test_doublepipe():
    assert check_token("||", ["OR", "or", 0])


def test_single_quote_literal():
    assert check_token("'yo'", ["STRING", "'yo'", 0])


def test_double_quote_literal():
    assert check_token('"yo"', ["STRING", '"yo"', 0])


def test_triple_single_quote_literal():
    assert check_token("'''yo'''", ["STRING", "'''yo'''", 0])


def test_triple_double_quote_literal():
    assert check_token('"""yo"""', ["STRING", '"""yo"""', 0])


def test_single_raw_string_literal():
    assert check_token("r'yo'", ["STRING", "r'yo'", 0])


def test_double_raw_string_literal():
    assert check_token('r"yo"', ["STRING", 'r"yo"', 0])


def test_single_f_string_literal():
    assert check_token("f'{yo}'", ["STRING", "f'{yo}'", 0])


def test_double_f_string_literal():
    assert check_token('f"{yo}"', ["STRING", 'f"{yo}"', 0])


def test_single_unicode_literal():
    assert check_token("u'yo'", ["STRING", "u'yo'", 0])


def test_double_unicode_literal():
    assert check_token('u"yo"', ["STRING", 'u"yo"', 0])


def test_single_bytes_literal():
    assert check_token("b'yo'", ["STRING", "b'yo'", 0])


def test_path_string_literal():
    assert check_token("p'/foo'", ["STRING", "p'/foo'", 0])
    assert check_token('p"/foo"', ["STRING", 'p"/foo"', 0])
    assert check_token("pr'/foo'", ["STRING", "pr'/foo'", 0])
    assert check_token('pr"/foo"', ["STRING", 'pr"/foo"', 0])
    assert check_token("rp'/foo'", ["STRING", "rp'/foo'", 0])
    assert check_token('rp"/foo"', ["STRING", 'rp"/foo"', 0])


def test_path_fstring_literal():
    assert check_token("pf'/foo'", ["STRING", "pf'/foo'", 0])
    assert check_token('pf"/foo"', ["STRING", 'pf"/foo"', 0])
    assert check_token("fp'/foo'", ["STRING", "fp'/foo'", 0])
    assert check_token('fp"/foo"', ["STRING", 'fp"/foo"', 0])
    assert check_token("pF'/foo'", ["STRING", "pF'/foo'", 0])
    assert check_token('pF"/foo"', ["STRING", 'pF"/foo"', 0])
    assert check_token("Fp'/foo'", ["STRING", "Fp'/foo'", 0])
    assert check_token('Fp"/foo"', ["STRING", 'Fp"/foo"', 0])


def test_regex_globs():
    for i in (".*", r"\d*", ".*#{1,2}"):
        for p in ("", "r", "g", "@somethingelse", "p", "pg"):
            c = f"{p}`{i}`"
            assert check_token(c, ["SEARCHPATH", c, 0])


@pytest.mark.parametrize(
    "case",
    [
        "0.0",
        ".0",
        "0.",
        "1e10",
        "1.e42",
        "0.1e42",
        "0.5e-42",
        "5E10",
        "5e+42",
        "1_0e1_0",
    ],
)
def test_float_literals(case):
    assert check_token(case, ["NUMBER", case, 0])


@pytest.mark.parametrize(
    "case", ["2>1", "err>out", "o>", "all>", "e>o", "e>", "out>", "2>&1"]
)
def test_ioredir(case):
    assert check_tokens_subproc(case, [("IOREDIRECT", case, 2)], stop=-2)


@pytest.mark.parametrize("case", [">", ">>", "<", "e>", "> ", ">>   ", "<  ", "e> "])
def test_redir_whitespace(case):
    inp = f"![{case}/path/to/file]"
    obs = lex_input(inp)
    assert obs[2].type == "WS"


@pytest.mark.parametrize(
    "s, exp",
    [
        ("", []),
        ("   \t   \n \t  ", []),
        ("echo hello", ["echo", "hello"]),
        ('echo "hello"', ["echo", '"hello"']),
        ('![echo "hello"]', ["![echo", '"hello"]']),
        ("/usr/bin/echo hello", ["/usr/bin/echo", "hello"]),
        ("$(/usr/bin/echo hello)", ["$(/usr/bin/echo", "hello)"]),
        ("C:\\Python\\python.exe -m xonsh", ["C:\\Python\\python.exe", "-m", "xonsh"]),
        ('print("""I am a triple string""")', ['print("""I am a triple string""")']),
        (
            'print("""I am a \ntriple string""")',
            ['print("""I am a \ntriple string""")'],
        ),
        ("echo $HOME", ["echo", "$HOME"]),
        ("echo -n $HOME", ["echo", "-n", "$HOME"]),
        ("echo --go=away", ["echo", "--go=away"]),
        ("echo --go=$HOME", ["echo", "--go=$HOME"]),
    ],
)
def test_lexer_split(s, exp):
    lexer = Lexer()
    obs = lexer.split(s)
    assert exp == obs


@pytest.mark.parametrize(
    "s",
    (
        "()",  # sanity
        "(",
        ")",
        "))",
        "'string\nliteral",
        "'''string\nliteral",
        "string\nliteral'",
        '"',
        "'",
        '"""',
    ),
)
def test_tolerant_lexer(s):
    lexer = Lexer(tolerant=True)
    lexer.input(s)
    error_tokens = list(tok for tok in lexer if tok.type == "ERRORTOKEN")
    assert all(tok.value in s for tok in error_tokens)  # no error messages
