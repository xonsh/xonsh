"""Tests for the base completer's logic (xonsh/completer.py)"""

import pytest

from xonsh.completer import Completer
from xonsh.completers.tools import (
    RichCompletion,
    contextual_command_completer,
    non_exclusive_completer,
)
from xonsh.parsers.completion_context import CommandContext


@pytest.fixture(scope="session")
def completer():
    return Completer()


@pytest.fixture
def completers_mock(xession, monkeypatch):
    completers = {}
    monkeypatch.setattr(xession, "_completers", completers)
    return completers


def test_sanity(completer, completers_mock):
    # no completions:
    completers_mock["a"] = lambda *a: None
    assert completer.complete("", "", 0, 0) == ((), 0)
    # simple completion:
    completers_mock["a"] = lambda *a: {"comp"}
    assert completer.complete("pre", "", 0, 0) == (("comp",), 3)
    # multiple completions:
    completers_mock["a"] = lambda *a: {"comp1", "comp2"}
    assert completer.complete("pre", "", 0, 0) == (("comp1", "comp2"), 3)
    # custom lprefix:
    completers_mock["a"] = lambda *a: ({"comp"}, 2)
    assert completer.complete("pre", "", 0, 0) == (("comp",), 2)
    # RichCompletion:
    completers_mock["a"] = lambda *a: {RichCompletion("comp", prefix_len=5)}
    assert completer.complete("pre", "", 0, 0) == (
        (RichCompletion("comp", prefix_len=5),),
        3,
    )


def test_cursor_after_closing_quote(completer, completers_mock):
    """See ``Completer.complete`` in ``xonsh/completer.py``"""

    @contextual_command_completer
    def comp(context: CommandContext):
        return {context.prefix + "1", context.prefix + "2"}

    completers_mock["a"] = comp

    assert completer.complete(
        "", "", 0, 0, {}, multiline_text="'test'", cursor_index=6
    ) == (("test1'", "test2'"), 5)

    assert completer.complete(
        "", "", 0, 0, {}, multiline_text="'''test'''", cursor_index=10
    ) == (("test1'''", "test2'''"), 7)


def test_cursor_after_closing_quote_override(completer, completers_mock):
    """Test overriding the default values"""

    @contextual_command_completer
    def comp(context: CommandContext):
        return {
            # replace the closing quote with "a"
            RichCompletion(
                "a", prefix_len=len(context.closing_quote), append_closing_quote=False
            ),
            # add text after the closing quote
            RichCompletion(context.prefix + "_no_quote", append_closing_quote=False),
            # sanity
            RichCompletion(context.prefix + "1"),
        }

    completers_mock["a"] = comp

    assert completer.complete(
        "", "", 0, 0, {}, multiline_text="'test'", cursor_index=6
    ) == (
        (
            "a",
            "test1'",
            "test_no_quote",
        ),
        5,
    )

    assert completer.complete(
        "", "", 0, 0, {}, multiline_text="'''test'''", cursor_index=10
    ) == (
        (
            "a",
            "test1'''",
            "test_no_quote",
        ),
        7,
    )


def test_append_space(completer, completers_mock):
    @contextual_command_completer
    def comp(context: CommandContext):
        return {
            RichCompletion(context.prefix + "a", append_space=True),
            RichCompletion(context.prefix + " ", append_space=False),  # bad usage
            RichCompletion(
                context.prefix + "b", append_space=True, append_closing_quote=False
            ),
        }

    completers_mock["a"] = comp

    assert completer.complete(
        "", "", 0, 0, {}, multiline_text="'test'", cursor_index=6
    ) == (
        (
            "test '",
            "testa' ",
            "testb ",
        ),
        5,
    )


@pytest.mark.parametrize(
    "middle_result, exp",
    (
        (
            # stop at the first exclusive result
            ({"b1", "b2"}, ("a1", "a2", "b1", "b2")),
            # pass empty exclusive results
            ({}, ("a1", "a2", "c1", "c2")),
            # pass empty exclusive results
            (None, ("a1", "a2", "c1", "c2")),
            # stop at StopIteration
            (StopIteration, ("a1", "a2")),
        )
    ),
)
def test_non_exclusive(completer, completers_mock, middle_result, exp):
    completers_mock["a"] = non_exclusive_completer(lambda *a: {"a1", "a2"})

    def middle(*a):
        if middle_result is StopIteration:
            raise StopIteration()
        return middle_result

    completers_mock["b"] = middle
    completers_mock["c"] = non_exclusive_completer(lambda *a: {"c1", "c2"})

    assert completer.complete("", "", 0, 0, {})[0] == exp


def test_env_completer_sort(completer, completers_mock):
    @contextual_command_completer
    def comp(context: CommandContext):
        return {"$SUPER_WOW", "$WOW1", "$WOW0", "$MID_WOW"}

    completers_mock["a"] = comp

    comps = completer.complete(
        "$WOW", "$WOW", 4, 0, {}, multiline_text="'$WOW'", cursor_index=4
    )
    assert set(comps[0]) == {"$WOW0", "$WOW1", "$MID_WOW", "$SUPER_WOW"}


def test_python_only_context(completer, completers_mock):
    assert completer.complete_line("echo @(") != ()
    assert completer.complete("", "echo @(", 0, 0, {}, "echo @(", 7) != ()
