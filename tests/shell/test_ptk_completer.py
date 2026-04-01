from inspect import signature
from unittest.mock import MagicMock

import pytest
from prompt_toolkit.completion import Completion as PTKCompletion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText

from xonsh.aliases import Aliases
from xonsh.completer import Completer
from xonsh.completers.tools import RichCompletion
from xonsh.shells.ptk_shell.completer import PromptToolkitCompleter, _highlight_match


@pytest.mark.parametrize(
    "completion, lprefix, ptk_completion",
    [
        (RichCompletion("x", 0, "x()", "func"), 0, None),
        (RichCompletion("x", 1, "xx", "instance"), 0, None),
        (
            RichCompletion("x", description="wow"),
            5,
            PTKCompletion(RichCompletion("x"), -5, "x", "wow"),
        ),
        (RichCompletion("x"), 5, PTKCompletion(RichCompletion("x"), -5, "x")),
        ("x", 5, PTKCompletion("x", -5, "x")),
    ],
)
def test_rich_completion(completion, lprefix, ptk_completion, monkeypatch, xession):
    xonsh_completer_mock = MagicMock()
    xonsh_completer_mock.complete.return_value = {completion}, lprefix

    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, None)
    ptk_completer.reserve_space = lambda: None
    ptk_completer.suggestion_completion = lambda _, __: None

    document_mock = MagicMock()
    document_mock.text = ""
    document_mock.current_line = ""
    document_mock.cursor_position_col = 0

    monkeypatch.setattr(xession.commands_cache, "aliases", Aliases())

    completions = list(ptk_completer.get_completions(document_mock, MagicMock()))
    if isinstance(completion, RichCompletion) and not ptk_completion:
        assert completions == [
            PTKCompletion(
                completion,
                -completion.prefix_len,
                completion.display,
                completion.description,
            )
        ]
    else:
        assert completions == [ptk_completion]


@pytest.mark.parametrize(
    "completions, document_text, ptk_completion",
    [
        (set(), "", "test_completion"),
        (set(), "test_", "test_completion"),
        ({RichCompletion("test", 4, "test()", "func")}, "test", "test_completion"),
    ],
)
def test_auto_suggest_completion(completions, document_text, ptk_completion, xession):
    lprefix = len(document_text)

    xonsh_completer_mock = MagicMock()
    xonsh_completer_mock.complete.return_value = completions, lprefix

    xession.env["AUTO_SUGGEST_IN_COMPLETIONS"] = True

    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, None)
    ptk_completer.reserve_space = lambda: None
    ptk_completer.suggestion_completion = lambda _, __: ptk_completion

    document_mock = MagicMock()
    document_mock.text = document_text
    document_mock.current_line = document_text
    document_mock.cursor_position_col = lprefix

    auto_suggested = list(ptk_completer.get_completions(document_mock, MagicMock()))
    assert PTKCompletion(ptk_completion, -lprefix) in auto_suggested


EXPANSION_CASES = (
    (
        "sanity",
        6,
        dict(
            prefix="sanity",
            line="sanity",
            begidx=0,
            endidx=6,
            multiline_text="sanity",
            cursor_index=6,
        ),
    ),
    (
        "gb ",
        3,
        dict(
            prefix="",
            line="git branch ",
            begidx=11,
            endidx=11,
            multiline_text="git branch ",
            cursor_index=11,
        ),
    ),
    (
        "gb ",
        1,
        dict(
            prefix="g",
            line="gb ",
            begidx=0,
            endidx=1,
            multiline_text="gb ",
            cursor_index=1,
        ),
    ),
    (
        "gb",
        0,
        dict(
            prefix="",
            line="gb",
            begidx=0,
            endidx=0,
            multiline_text="gb",
            cursor_index=0,
        ),
    ),
    (
        " gb ",
        0,
        dict(
            prefix="",
            line=" gb ",  # the PTK completer `lstrip`s the line
            begidx=0,
            endidx=0,
            multiline_text=" gb ",
            cursor_index=0,
        ),
    ),
    (
        "gb --",
        5,
        dict(
            prefix="--",
            line="git branch --",
            begidx=11,
            endidx=13,
            multiline_text="git branch --",
            cursor_index=13,
        ),
    ),
    (
        "nice\ngb --",
        10,
        dict(
            prefix="--",
            line="git branch --",
            begidx=11,
            endidx=13,
            multiline_text="nice\ngit branch --",
            cursor_index=18,
        ),
    ),
    (
        "nice\n gb --",
        11,
        dict(
            prefix="--",
            line=" git branch --",
            begidx=12,
            endidx=14,
            multiline_text="nice\n git branch --",
            cursor_index=19,
        ),
    ),
    (
        "gb -- wow",
        5,
        dict(
            prefix="--",
            line="git branch -- wow",
            begidx=11,
            endidx=13,
            multiline_text="git branch -- wow",
            cursor_index=13,
        ),
    ),
    (
        "gb --wow",
        5,
        dict(
            prefix="--",
            line="git branch --wow",
            begidx=11,
            endidx=13,
            multiline_text="git branch --wow",
            cursor_index=13,
        ),
    ),
)


@pytest.mark.parametrize("code, index, expected_args", EXPANSION_CASES)
def test_alias_expansion(code, index, expected_args, monkeypatch, xession):
    xonsh_completer_mock = MagicMock(spec=Completer)
    xonsh_completer_mock.complete.return_value = set(), 0

    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, None)
    ptk_completer.reserve_space = lambda: None
    ptk_completer.suggestion_completion = lambda _, __: None

    monkeypatch.setattr(xession.commands_cache, "aliases", Aliases(gb=["git branch"]))

    list(ptk_completer.get_completions(Document(code, index), MagicMock()))
    mock_call = xonsh_completer_mock.complete.call_args
    args, kwargs = mock_call
    expected_args["self"] = None
    expected_args["ctx"] = None
    assert (
        signature(Completer.complete).bind(None, *args, **kwargs).arguments
        == expected_args
    )


def test_auto_suggest_completion_with_spaces(xession):
    """Test that auto-suggestion includes spaces (full line) instead of truncating at first space."""
    xession.env["AUTO_SUGGEST_IN_COMPLETIONS"] = True
    xonsh_completer_mock = MagicMock()
    xonsh_completer_mock.complete.return_value = set(), 0
    shell_mock = MagicMock()
    shell_mock.prompter.app = MagicMock()
    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, shell_mock)
    ptk_completer.reserve_space = lambda: None
    suggestion_mock = MagicMock()
    suggestion_mock.text = "ho hello world"
    ptk_completer.hist_suggester = MagicMock()
    ptk_completer.hist_suggester.get_suggestion.return_value = suggestion_mock
    document_mock = MagicMock()
    document_mock.text = "ec"
    document_mock.current_line = "ec"
    document_mock.cursor_position_col = 2
    completion_item = ptk_completer.suggestion_completion(document_mock, "ec")
    assert completion_item == "echo hello world"
    long_cmd = "echo " + "a" * 100
    suggestion_mock.text = "o " + "a" * 100
    document_mock.text = "ech"
    document_mock.current_line = "ech"
    res = ptk_completer.suggestion_completion(document_mock, "ech")
    assert isinstance(res, RichCompletion)
    assert res == long_cmd
    assert len(res.display) < len(res)
    assert res.display.endswith("...")


@pytest.mark.parametrize(
    "current_line, completions, lprefix, displays",
    [
        ("./", ["'./abc'"], 3, ["abc"]),  # trim prefix path and unquoting
        (  # raw string unquoting
            "./ab",
            [r"r'./ab\c'", "r'./abc'"],  # avoid trimming c_prefix at backslash
            6,
            [r"ab\c", "abc"],
        ),
        ("./r", ["./result"], 3, ["result"]),  # start with r
        ("./t", ["./tester"], 3, ["tester"]),  # end with r
        ("./", ["./'''"], 2, ["'''"]),  # file name contains quotes
        ("./", ["\"./r'abc'\""], 3, ["r'abc'"]),  # file name mimicing raw string syntax
        ('"""/pr', ['"""/proc"""'], 6, ["proc"]),  # triple quotes unquoting
        (  # file name containing ' " \
            "./",
            ["'./r\\'\\\\\"'", "./abc"],
            3,
            ["r'\\\"", "abc"],
        ),
    ],
)
def test_completion_display(
    current_line, completions, lprefix, displays, monkeypatch, xession
):
    xonsh_completer_mock = MagicMock()
    xonsh_completer_mock.complete.return_value = completions, lprefix

    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, None)
    ptk_completer.reserve_space = lambda: None
    ptk_completer.suggestion_completion = lambda _, __: None

    document_mock = MagicMock()
    document_mock.text = ""
    document_mock.current_line = current_line
    document_mock.cursor_position_col = len(current_line)

    monkeypatch.setattr(xession.commands_cache, "aliases", Aliases())

    ptk_completions = list(ptk_completer.get_completions(document_mock, MagicMock()))
    assert ptk_completions == [
        PTKCompletion(completion, -lprefix, display)
        for completion, display in zip(completions, displays, strict=True)
    ]


def test_highlight_match_empty_prefix():
    assert _highlight_match("foobar", "foobar", "", 0) == "foobar"


def test_highlight_match_no_match():
    assert _highlight_match("foobar", "foobar", "xyz", 0) == "foobar"


def test_highlight_match_prefix_no_underline():
    """Prefix matches should not be underlined — they are visually obvious."""
    assert _highlight_match("foobar", "foobar", "foo", 0) == "foobar"


def test_highlight_match_substring_underline():
    """Substring matches in the middle should be underlined."""
    result = _highlight_match("foobar", "foobar", "oba", 0)
    assert result == FormattedText([("", "fo"), ("underline", "oba"), ("", "r")])


def test_highlight_match_substring_at_end():
    result = _highlight_match("foobar", "foobar", "bar", 0)
    assert result == FormattedText([("", "foo"), ("underline", "bar")])


def test_highlight_match_case_insensitive():
    result = _highlight_match("FooBar", "FooBar", "oba", 0)
    assert result == FormattedText([("", "Fo"), ("underline", "oBa"), ("", "r")])


def test_highlight_match_pre_offset_hides_prefix():
    """When pre strips the common prefix, a match at position 0 in the
    full text falls before the displayed text — no underline."""
    assert _highlight_match("bar", "foobar", "foo", 3) == "bar"


def test_highlight_match_pre_offset_substring_visible():
    """When pre strips a common prefix and the match lands at position 0
    in the displayed text, it's treated as a prefix match — no underline."""
    result = _highlight_match("bar_baz", "foo/bar_baz", "bar", 4)
    assert result == "bar_baz"


def test_highlight_match_pre_offset_true_substring():
    """Substring match after the common prefix strip point."""
    result = _highlight_match("baz_bar_qux", "foo/baz_bar_qux", "bar", 4)
    assert result == FormattedText([("", "baz_"), ("underline", "bar"), ("", "_qux")])


def test_highlight_match_import_substring():
    """Import completions: 'de' should be underlined in 'JSONDecoder'."""
    result = _highlight_match("JSONDecoder", "JSONDecoder", "de", 0)
    assert result == FormattedText([("", "JSON"), ("underline", "De"), ("", "coder")])


def test_highlight_match_import_prefix():
    """Import completions: 'de' at the start of 'decoder' is a prefix — no underline."""
    assert _highlight_match("decoder", "decoder", "de", 0) == "decoder"


def test_highlight_match_dotted_prefix_substring():
    """Dotted completions: 'json.de' prefix with 'json.' stripped — 'De' in
    'JSONDecoder' should be underlined via visible prefix fallback."""
    result = _highlight_match("JSONDecoder", "json.JSONDecoder", "json.de", 5)
    assert result == FormattedText([("", "JSON"), ("underline", "De"), ("", "coder")])


def test_highlight_match_dotted_prefix_no_underline():
    """Dotted completions: 'de' at the start of display 'decoder' is a
    prefix match — no underline."""
    assert _highlight_match("decoder", "json.decoder", "json.de", 5) == "decoder"


def test_highlight_match_dotted_prefix_encoder():
    """Dotted completions: 'de' in 'encoder' at position 4 should be underlined."""
    result = _highlight_match("encoder", "json.encoder", "json.de", 5)
    assert result == FormattedText([("", "enco"), ("underline", "de"), ("", "r")])


def test_completion_substring_highlight(monkeypatch, xession):
    """Integration test: substring completions get underline styling."""
    xonsh_completer_mock = MagicMock()
    xonsh_completer_mock.complete.return_value = (
        ["prefix_match", "has_bar_suffix"],
        3,
    )

    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, None)
    ptk_completer.reserve_space = lambda: None
    ptk_completer.suggestion_completion = lambda _, __: None

    document_mock = MagicMock()
    document_mock.text = "bar"
    document_mock.current_line = "bar"
    document_mock.cursor_position_col = 3

    monkeypatch.setattr(xession.commands_cache, "aliases", Aliases())

    completions = list(ptk_completer.get_completions(document_mock, MagicMock()))

    # "prefix_match" does not contain "bar" → no underline, plain display
    # "has_bar_suffix" contains "bar" at position 4 → underline
    assert len(completions) == 2

    # prefix_match: "bar" not found in "prefix_match" → plain display
    assert completions[0].display == FormattedText([("", "prefix_match")])

    # has_bar_suffix: "bar" found at position 4, pre=0, disp_start=4
    assert completions[1].display == FormattedText(
        [("", "has_"), ("underline", "bar"), ("", "_suffix")]
    )
