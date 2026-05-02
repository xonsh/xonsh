"""Smoke tests for ``xonsh.completers.tools``.

The module backs the public completer-author API: ``RichCompletion``, the
``contextual_*`` decorators, the various filter helpers, and the
``tag_provider`` / ``apply_lprefix`` adapters that fix up completer output
before it reaches the UI.
"""

import pytest

from xonsh.completers.tools import (
    RichCompletion,
    _filter_prefix,
    _filter_substring,
    apply_lprefix,
    completion_from_cmd_output,
    contextual_command_completer,
    contextual_command_completer_for,
    contextual_completer,
    get_filter_function,
    is_contextual_completer,
    is_exclusive_completer,
    justify,
    non_exclusive_completer,
    tag_provider,
)


# --- RichCompletion ---------------------------------------------------------


def test_rich_completion_is_str_subclass():
    rc = RichCompletion("hello")
    assert isinstance(rc, str)
    assert rc == "hello"


def test_rich_completion_default_attrs():
    rc = RichCompletion("hi")
    assert rc.prefix_len is None
    assert rc.display is None
    assert rc.description == ""
    assert rc.style == ""
    assert rc.append_closing_quote is True
    assert rc.append_space is False
    assert rc.provider is None


def test_rich_completion_value_property():
    rc = RichCompletion("xyz")
    assert rc.value == "xyz"


def test_rich_completion_repr_skips_default_attrs():
    rc = RichCompletion("abc")
    assert "abc" in repr(rc)
    # defaults are NOT in the repr
    assert "prefix_len=None" not in repr(rc)
    assert "description=" not in repr(rc)


def test_rich_completion_repr_shows_non_defaults():
    rc = RichCompletion("abc", description="docs")
    assert "description='docs'" in repr(rc)


def test_rich_completion_replace_returns_new_instance():
    rc = RichCompletion("abc", description="old")
    rc2 = rc.replace(description="new")
    assert rc2 is not rc
    assert rc2.description == "new"
    # original is unchanged
    assert rc.description == "old"


def test_rich_completion_replace_preserves_other_attrs():
    rc = RichCompletion("abc", description="d", style="s", provider="p")
    rc2 = rc.replace(prefix_len=3)
    assert rc2.prefix_len == 3
    assert rc2.description == "d"
    assert rc2.style == "s"
    assert rc2.provider == "p"


# --- justify ----------------------------------------------------------------


def test_justify_pads_subsequent_lines():
    s = "one two three four five six seven"
    out = justify(s, max_length=10, left_pad=2)
    lines = out.splitlines()
    # the first line has no padding
    assert not lines[0].startswith(" ")
    # subsequent lines start with 2 spaces
    for line in lines[1:]:
        assert line.startswith("  ")


def test_justify_no_wrap_for_short_text():
    out = justify("short text", max_length=80)
    assert out == "short text"


# --- _filter_substring / _filter_prefix -------------------------------------


def test_filter_substring_matches_anywhere():
    assert _filter_substring("hello", "ell") is True
    assert _filter_substring("hello", "x") is False


def test_filter_substring_is_case_insensitive():
    assert _filter_substring("HELLO", "ell") is True
    assert _filter_substring("hello", "ELL") is True


def test_filter_prefix_only_matches_at_start():
    assert _filter_prefix("hello", "hel") is True
    assert _filter_prefix("hello", "ell") is False


def test_filter_prefix_is_case_insensitive():
    assert _filter_prefix("Hello", "hel") is True


def test_filter_substring_with_rich_completion_display_uses_display():
    """When the completion has a ``display`` attribute, filtering uses it."""
    rc = RichCompletion("abc", display="Apple Banana")
    # 'banana' substring matches the display
    assert _filter_substring(rc, "banana") is True
    # 'abc' substring won't match 'Apple Banana'
    assert _filter_substring(rc, "x") is False


# --- get_filter_function ----------------------------------------------------


def test_get_filter_function_substring_default(xession):
    xession.env.pop("XONSH_COMPLETER_MODE", None)
    assert get_filter_function() is _filter_substring


def test_get_filter_function_prefix_mode(xession):
    xession.env["XONSH_COMPLETER_MODE"] = "prefix"
    assert get_filter_function() is _filter_prefix


def test_get_filter_function_substring_explicit_mode(xession):
    xession.env["XONSH_COMPLETER_MODE"] = "substring_tier"
    assert get_filter_function() is _filter_substring


# --- contextual_completer / decorators --------------------------------------


def test_contextual_completer_marks_function():
    @contextual_completer
    def myc(ctx):
        return None

    assert is_contextual_completer(myc) is True


def test_is_contextual_completer_false_by_default():
    def plain(prefix, line, begidx, endidx, ctx):
        return None

    assert is_contextual_completer(plain) is False


def test_non_exclusive_marks_function():
    @non_exclusive_completer
    def myc(prefix, line, begidx, endidx, ctx):
        return None

    assert is_exclusive_completer(myc) is False


def test_is_exclusive_completer_true_by_default():
    def plain():
        pass

    assert is_exclusive_completer(plain) is True


def test_contextual_command_completer_only_runs_with_command_context():
    """The decorator forwards to inner only when the context has a command."""

    @contextual_command_completer
    def inner(cmd):
        return {"yes"}

    # Build a minimal CompletionContext with a None command
    class FakeCtx:
        command = None

    assert inner(FakeCtx()) is None

    class WithCmd:
        command = "anything"

    assert inner(WithCmd()) == {"yes"}


def test_contextual_command_completer_for_filters_command_name():
    @contextual_command_completer_for("git")
    def inner(cmd):
        return {"matched"}

    class FakeCmdGit:
        completing_command = lambda self, name: name == "git"

    class FakeCmdLs:
        completing_command = lambda self, name: name == "ls"

    class CtxGit:
        command = FakeCmdGit()

    class CtxLs:
        command = FakeCmdLs()

    class CtxNone:
        command = None

    assert inner(CtxGit()) == {"matched"}
    assert inner(CtxLs()) is None
    assert inner(CtxNone()) is None


# --- apply_lprefix ----------------------------------------------------------


def test_apply_lprefix_yields_nothing_for_none_lprefix():
    """``apply_lprefix`` is a generator function — when ``lprefix`` is None
    it ``return``s early, so the generator yields zero items."""
    out = list(apply_lprefix(["a", "b"], None))
    assert out == []


def test_apply_lprefix_wraps_strings_in_richcompletion():
    out = list(apply_lprefix(["a", "b"], 3))
    assert all(isinstance(x, RichCompletion) for x in out)
    assert all(x.prefix_len == 3 for x in out)


def test_apply_lprefix_sets_prefix_len_on_rich_completion_when_none():
    rc = RichCompletion("a")  # prefix_len is None
    out = list(apply_lprefix([rc], 5))
    assert out[0].prefix_len == 5
    # original unchanged
    assert rc.prefix_len is None


def test_apply_lprefix_preserves_existing_prefix_len():
    rc = RichCompletion("a", prefix_len=2)
    out = list(apply_lprefix([rc], 5))
    # the existing prefix_len wins
    assert out[0].prefix_len == 2


# --- tag_provider -----------------------------------------------------------


def test_tag_provider_returns_none_for_none():
    assert tag_provider(None, "alias") is None


def test_tag_provider_handles_two_tuple():
    out = tag_provider(({"a", "b"}, 3), "command")
    comps, extra = out
    materialized = list(comps)
    assert all(isinstance(x, RichCompletion) for x in materialized)
    assert all(x.provider == "command" for x in materialized)
    assert extra == 3


def test_tag_provider_handles_iterable():
    comps = list(tag_provider(["a", "b"], "alias"))
    assert all(isinstance(x, RichCompletion) for x in comps)
    assert all(x.provider == "alias" for x in comps)


def test_tag_provider_preserves_existing_provider():
    rc = RichCompletion("a", provider="path")
    out = list(tag_provider([rc], "alias"))
    # the inner completion's tag wins
    assert out[0].provider == "path"


# --- completion_from_cmd_output ---------------------------------------------


def test_completion_from_cmd_output_no_description():
    rc = completion_from_cmd_output("hello")
    assert rc.value == "hello"
    assert rc.description == ""


def test_completion_from_cmd_output_with_tab_separated_description():
    rc = completion_from_cmd_output("hello\tdocs string")
    assert rc.value == "hello"
    assert rc.description == "docs string"


def test_completion_from_cmd_output_strips_whitespace():
    rc = completion_from_cmd_output("  hello  ")
    assert rc.value == "hello"


def test_completion_from_cmd_output_no_append_space_for_dir_separator():
    """Trailing path separator → no space appended."""
    import os

    rc = completion_from_cmd_output(f"foo{os.sep}", append_space=True)
    assert rc.append_space is False


def test_completion_from_cmd_output_keeps_append_space_for_normal_value():
    rc = completion_from_cmd_output("abc", append_space=True)
    assert rc.append_space is True
