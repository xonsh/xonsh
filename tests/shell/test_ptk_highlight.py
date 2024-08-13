"""Test XonshLexer for pygments"""

import pytest
from pygments.token import (
    Error,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
)

from xonsh.environ import LsColors
from xonsh.events import EventManager, events
from xonsh.pyghooks import Color, XonshLexer, XonshStyle, on_lscolors_change
from xonsh.pytest.tools import DummyShell, skip_if_on_windows


@pytest.fixture
def xsh(xession, monkeypatch):
    for key in ("cd", "bash"):
        monkeypatch.setitem(xession.aliases, key, lambda *args, **kwargs: None)


@pytest.fixture()
def check_token(xsh):
    def factory(code, tokens):
        """Make sure that all tokens appears in code in order"""
        lx = XonshLexer()
        tks = list(lx.get_tokens(code))

        for tk in tokens:
            while tks:
                if tk == tks[0]:
                    break
                tks = tks[1:]
            else:
                msg = f"Token {tk!r} missing: {list(lx.get_tokens(code))!r}"
                pytest.fail(msg)
                break

    return factory


_cases = {
    "print": {
        'print("hello")': [
            (Name.Builtin, "print"),
            (Punctuation, "("),
            (Literal.String.Double, '"'),
            (Literal.String.Double, "hello"),
            (Literal.String.Double, '"'),
            (Punctuation, ")"),
            (Text.Whitespace, "\n"),
        ]
    },
    "invalid-cmd": {
        "non-existance-cmd -al": [
            (Name, "non"),
        ],
        "![non-existance-cmd -al]": [
            (Error, "non-existance-cmd"),
        ],
        "for i in range(10):": [
            (Keyword, "for"),
        ],
        "(1, )": [
            (Punctuation, "("),
            (Number.Integer, "1"),
        ],
    },
    "multi-cmd": {
        "cd && cd": [
            (Name.Builtin, "cd"),
            (Operator, "&&"),
            (Name.Builtin, "cd"),
        ],
        "cd || non-existance-cmd": [
            (Name.Builtin, "cd"),
            (Operator, "||"),
            (Error, "non-existance-cmd"),
        ],
    },
    "nested": {
        "print($(cd))": [
            (Name.Builtin, "print"),
            (Punctuation, "("),
            (Keyword, "$"),
            (Punctuation, "("),
            (Name.Builtin, "cd"),
            (Punctuation, ")"),
            (Punctuation, ")"),
            (Text.Whitespace, "\n"),
        ],
    },
    "subproc-args": {
        "cd 192.168.0.1": [
            (Text, "192.168.0.1"),
        ],
    },
    "backtick": {
        r"echo g`.*\w+`": [
            (String.Affix, "g"),
            (String.Backtick, "`"),
            (String.Regex, "."),
            (String.Regex, "*"),
            (String.Escape, r"\w"),
        ],
    },
    "macro": {
        r"g!(42, *, 65)": [
            (Name, "g"),
            (Keyword, "!"),
            (Punctuation, "("),
            (Number.Integer, "42"),
        ],
        r"bash -c ! export var=42; echo $var": [
            (Name.Builtin, "bash"),
            (Text, "-c"),
            (Keyword, "!"),
            (String, "export var=42; echo $var"),
        ],
    },
}
_cases_no_win = {
    "ls": {
        "ls -al": [
            (Name.Builtin, "ls"),
        ],
    },
    "ls-bin": {
        "/bin/ls -al": [
            (Name.Builtin, "/bin/ls"),
        ],
    },
    "print": {
        'print("hello")': [
            (Name.Builtin, "print"),
            (Punctuation, "("),
            (Literal.String.Double, '"'),
            (Literal.String.Double, "hello"),
            (Literal.String.Double, '"'),
            (Punctuation, ")"),
            (Text.Whitespace, "\n"),
        ]
    },
    "nested": {
        'echo @("hello")': [
            (Name.Builtin, "echo"),
            (Keyword, "@"),
            (Punctuation, "("),
            (String.Double, "hello"),
            (Punctuation, ")"),
        ],
        "print($(cd))": [
            (Name.Builtin, "print"),
            (Punctuation, "("),
            (Keyword, "$"),
            (Punctuation, "("),
            (Name.Builtin, "cd"),
            (Punctuation, ")"),
            (Punctuation, ")"),
            (Text.Whitespace, "\n"),
        ],
        r'print(![echo "])\""])': [
            (Name.Builtin, "print"),
            (Punctuation, "("),
            (Keyword, "!"),
            (Punctuation, "["),
            (Name.Builtin, "echo"),
            (Text, " "),
            (Literal.String.Double, '"])\\""'),
            (Punctuation, "]"),
            (Punctuation, ")"),
            (Text.Whitespace, "\n"),
        ],
    },
    "macro": {
        r"g!(42, *, 65)": [
            (Name, "g"),
            (Keyword, "!"),
            (Punctuation, "("),
            (Number.Integer, "42"),
        ],
        r"echo! hello world": [
            (Name.Builtin, "echo"),
            (Keyword, "!"),
            (String, "hello world"),
        ],
        r"bash -c ! export var=42; echo $var": [
            (Name.Builtin, "bash"),
            (Text, "-c"),
            (Keyword, "!"),
            (String, "export var=42; echo $var"),
        ],
    },
}


def _convert_cases():
    for title, input_dict in _cases.items():
        for idx, item in enumerate(input_dict.items()):
            yield pytest.param(*item, id=f"{title}-{idx}")


def _convert_cases_no_win():
    for title, input_dict in _cases_no_win.items():
        for idx, item in enumerate(input_dict.items()):
            yield pytest.param(*item, id=f"{title}-{idx}")


@pytest.mark.parametrize("inp, expected", list(_convert_cases()))
def test_xonsh_lexer(inp, expected, check_token):
    check_token(inp, expected)


@pytest.mark.parametrize("inp, expected", list(_convert_cases_no_win()))
@skip_if_on_windows
def test_xonsh_lexer_no_win(inp, expected, check_token):
    check_token(inp, expected)


# can't seem to get thie test to import pyghooks and define on_lscolors_change handler like live code does.
# so we declare the event handler directly here.
@pytest.fixture
def events_fxt():
    return EventManager()


@pytest.fixture
def xonsh_builtins_ls_colors(xession, events_fxt):
    xession.shell = DummyShell()  # because load_command_cache zaps it.
    xession.shell.shell_type = "prompt_toolkit"
    lsc = LsColors(LsColors.default_settings)
    xession.env["LS_COLORS"] = lsc  # establish LS_COLORS before style.
    xession.shell.shell.styler = XonshStyle()  # default style

    events.on_lscolors_change(on_lscolors_change)

    yield xession


@skip_if_on_windows
def test_path(tmpdir, xonsh_builtins_ls_colors, check_token):
    test_dir = str(tmpdir.mkdir("xonsh-test-highlight-path"))
    check_token(f"cd {test_dir}", [(Name.Builtin, "cd"), (Color.BOLD_BLUE, test_dir)])
    check_token(
        f"cd {test_dir}-xxx",
        [(Name.Builtin, "cd"), (Text, f"{test_dir}-xxx")],
    )
    check_token(f"cd X={test_dir}", [(Color.BOLD_BLUE, test_dir)])

    with xonsh_builtins_ls_colors.env.swap(AUTO_CD=True):
        check_token(test_dir, [(Name.Constant, test_dir)])


@skip_if_on_windows
def test_color_on_lscolors_change(tmpdir, xonsh_builtins_ls_colors, check_token):
    """Verify colorizer returns Token.Text if file type not defined in LS_COLORS"""

    lsc = xonsh_builtins_ls_colors.env["LS_COLORS"]
    test_dir = str(tmpdir.mkdir("xonsh-test-highlight-path"))

    lsc["di"] = ("GREEN",)

    check_token(f"cd {test_dir}", [(Name.Builtin, "cd"), (Color.GREEN, test_dir)])

    del lsc["di"]

    check_token(f"cd {test_dir}", [(Name.Builtin, "cd"), (Text, test_dir)])
