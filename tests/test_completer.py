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
            "test1'",
            "test_no_quote",
            "a",
        ),
        5,
    )

    assert completer.complete(
        "", "", 0, 0, {}, multiline_text="'''test'''", cursor_index=10
    ) == (
        (
            "test1'''",
            "test_no_quote",
            "a",
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


def test_sortkey_tiers(completer, completers_mock):
    """Completions should be ranked by match quality tier.

    Sort order:
      tier 0 — case-sensitive prefix match
      tier 1 — case-insensitive prefix match
      tier 2 — case-sensitive substring match
      tier 3 — case-insensitive substring match
      tier 4 — no match
    Within a tier: _-prefixed last, then by match position, then alphabetically.
    """

    @contextual_command_completer
    def comp(context: CommandContext):
        return {"decoder", "Decoder", "JSONDecoder", "jsondecoder", "foobar"}

    completers_mock["a"] = comp

    comps = completer.complete(
        "dec", "dec", 0, 3, {}, multiline_text="dec", cursor_index=3
    )
    result = comps[0]
    assert result == ("decoder", "Decoder", "jsondecoder", "JSONDecoder", "foobar")


def test_sortkey_substring_position(completer, completers_mock):
    """Within the same tier, earlier substring position sorts first."""

    @contextual_command_completer
    def comp(context: CommandContext):
        return {
            "patch-1",           # tier 0: prefix match, pos 0
            "origin/patch-1",    # tier 2: substring, pos 7
            "anki-code-patch",   # tier 2: substring, pos 10
            "x-patch-2",         # tier 2: substring, pos 2
            "PATCH-3",           # tier 1: case-insensitive prefix, pos 0
            "unrelated",         # tier 4: no match
        }

    completers_mock["a"] = comp

    comps = completer.complete(
        "patch", "patch", 0, 5, {}, multiline_text="patch", cursor_index=5
    )
    result = comps[0]
    assert result == (
        "patch-1",           # tier 0
        "PATCH-3",           # tier 1
        "x-patch-2",         # tier 2, pos 2
        "origin/patch-1",    # tier 2, pos 7
        "anki-code-patch",   # tier 2, pos 10
        "unrelated",         # tier 4
    )


def test_deduplicate_trailing_space(completer, completers_mock):
    """Completions that differ only by a trailing space should be deduplicated.

    When a command like ``_cd`` is completed both as a Python name (no space)
    and as an executable (with ``append_space=True``), only the spaced variant
    should appear in the final results.

    This simulates the real scenario where ``complete_base`` is a single
    generator-completer that yields plain Python-name completions AND
    command completions with ``append_space=True`` for the same name.
    """
    from xonsh.completers.tools import contextual_completer
    from xonsh.parsers.completion_context import CompletionContext

    @contextual_completer
    def comp(context: CompletionContext):
        # Simulates complete_base: first yields python names (no space),
        # then yields command completions (with trailing space)
        yield "_cd"
        yield "cdr"
        yield RichCompletion("_cd", append_space=True)

    completers_mock["a"] = comp

    comps = completer.complete(
        "cd", "cd", 0, 2, {}, multiline_text="cd", cursor_index=2
    )
    result = comps[0]
    result_strs = [str(c) for c in result]
    # Only the spaced "_cd " variant should remain, not bare "_cd"
    assert "_cd " in result_strs
    assert "_cd" not in result_strs
    # Unrelated completions must survive
    assert "cdr" in result_strs


def test_python_only_context(completer, completers_mock):
    assert completer.complete_line("echo @(") != ()
    assert completer.complete("", "echo @(", 0, 0, {}, "echo @(", 7) != ()


def test_trace_completions_is_per_line_with_source(
    completer, completers_mock, xession, monkeypatch, capsys
):
    """``$XONSH_COMPLETER_TRACE`` should print one line per completion,
    each tagged with ``source=<completer-name>`` and non-default
    ``RichCompletion`` attrs. See user request in conversation.
    """
    monkeypatch.setitem(xession.env, "XONSH_COMPLETER_TRACE", True)

    completers_mock["commands"] = lambda *a: {
        RichCompletion("ls", append_space=True),
        "lsof",
    }

    completer.complete("l", "l", 0, 1, {}, multiline_text="l", cursor_index=1)
    captured = capsys.readouterr().out

    # Header still present — now compact form with prefix echoed back.
    assert "Got 2 from exclusive 'commands' for 'l':" in captured
    # Per-line source for every completion (shortened label ``src``).
    assert captured.count("src=commands") == 2
    # type= tag on every line.
    assert captured.count("type=exclusive") == 2
    # RichCompletion attribute shown.
    assert "append_space=True" in captured
    # Plain str shows the pipeline lprefix after ``type=``.
    assert "'lsof': src=commands, type=exclusive, prefix_len=1" in captured
    # No pprint-style dump of a set/list object.
    assert "RichCompletion(" not in captured
    # No two-space indent before completion lines.
    assert "\n  'ls " not in captured and "\n  'lsof'" not in captured


def test_trace_completions_non_exclusive_type(
    completer, completers_mock, xession, monkeypatch, capsys
):
    """Trace lines from a non-exclusive completer must show ``type=non-exclusive``."""
    monkeypatch.setitem(xession.env, "XONSH_COMPLETER_TRACE", True)

    completers_mock["env"] = non_exclusive_completer(lambda *a: {"$FOO"})
    completers_mock["cmd"] = lambda *a: {"ls"}

    completer.complete("", "", 0, 0, {}, multiline_text="", cursor_index=0)
    captured = capsys.readouterr().out

    assert "'$FOO': src=env, type=non-exclusive" in captured
    assert "'ls': src=cmd, type=exclusive" in captured


def test_trace_completions_shows_provider(
    completer, completers_mock, xession, monkeypatch, capsys
):
    """Completions with a ``provider`` tag must surface it in trace output.

    Verifies the user-facing goal: telling that ``qwe-xonsh`` from the
    ``base`` completer came from aliases rather than $PATH. We mock the
    ``base`` completer directly so the test doesn't depend on the real
    commands_cache/filesystem.
    """
    monkeypatch.setitem(xession.env, "XONSH_COMPLETER_TRACE", True)

    completers_mock["base"] = lambda *a: {
        RichCompletion("qwe-xonsh ", append_space=True, provider="alias"),
        RichCompletion("xonsh-real ", append_space=True, provider="command"),
    }

    completer.complete(
        "xonsh", "xonsh", 0, 5, {}, multiline_text="xonsh", cursor_index=5
    )
    captured = capsys.readouterr().out

    # pvd sits immediately after src, before type.
    assert "src=base, pvd='alias', type=exclusive" in captured
    assert "src=base, pvd='command', type=exclusive" in captured


def test_tag_provider_preserves_return_shapes():
    """``tag_provider`` must accept None / iterable / (iter, extra) tuple."""
    from xonsh.completers.tools import tag_provider

    # None passthrough
    assert tag_provider(None, "x") is None

    # bare iterable
    out = list(tag_provider(["a", RichCompletion("b")], "pip"))
    assert all(c.provider == "pip" for c in out)
    assert [str(c) for c in out] == ["a", "b"]

    # (iterable, extra) tuple — extra preserved, comps tagged
    gen, extra = tag_provider((["a"], 3), "gh")
    assert extra == 3
    assert [c.provider for c in gen] == ["gh"]


def test_tag_provider_does_not_overwrite_existing():
    """A completion with an existing ``provider`` keeps its own tag."""
    from xonsh.completers.tools import tag_provider

    out = list(tag_provider([RichCompletion("x", provider="inner"), "y"], "outer"))
    assert out[0].provider == "inner"
    assert out[1].provider == "outer"


def test_xompleter_tags_with_module_basename():
    """``CommandCompleter`` must tag xompletion results with module basename.

    Verifies that ``xompletions.<name>.xonsh_complete`` output is wrapped
    so the trace shows ``provider=<name>`` — the ``xompleter`` bridging
    layer discussed in the user conversation.
    """
    from types import SimpleNamespace

    from xonsh.completers.commands import CommandCompleter
    from xonsh.parsers.completion_context import (
        CommandArg,
        CommandContext,
        CompletionContext,
    )

    fake_module = SimpleNamespace(
        __name__="xompletions.fake_pip",
        xonsh_complete=lambda ctx: {RichCompletion("install"), "freeze"},
    )
    cc = CommandCompleter()
    cc._matcher = SimpleNamespace(
        get_module=lambda name: fake_module,
        search_completer=lambda name, cleaned=False: None,
    )

    full_ctx = CompletionContext(
        command=CommandContext(args=(CommandArg("fake_pip"),), arg_index=1, prefix="")
    )
    result = list(cc(full_ctx))
    assert {str(c) for c in result} == {"install", "freeze"}
    assert all(c.provider == "fake_pip" for c in result)


def test_xompleter_passes_through_none():
    """If the xompletion module returns ``None`` (no match), ``CommandCompleter``
    must still pass ``None`` through so the pipeline falls to the next completer.
    """
    from types import SimpleNamespace

    from xonsh.completers.commands import CommandCompleter
    from xonsh.parsers.completion_context import (
        CommandArg,
        CommandContext,
        CompletionContext,
    )

    fake_module = SimpleNamespace(
        __name__="xompletions.fake_pip",
        xonsh_complete=lambda ctx: None,
    )
    cc = CommandCompleter()
    cc._matcher = SimpleNamespace(
        get_module=lambda name: fake_module,
        search_completer=lambda name, cleaned=False: None,
    )

    full_ctx = CompletionContext(
        command=CommandContext(args=(CommandArg("fake_pip"),), arg_index=1, prefix="")
    )
    assert cc(full_ctx) is None


def test_trace_completions_uses_close_quote_alias(
    completer, completers_mock, xession, monkeypatch, capsys
):
    """``append_closing_quote=False`` should surface as ``close_quote=False``."""
    monkeypatch.setitem(xession.env, "XONSH_COMPLETER_TRACE", True)

    completers_mock["a"] = lambda *a: {
        RichCompletion("foo", append_closing_quote=False)
    }

    completer.complete("f", "f", 0, 1, {}, multiline_text="f", cursor_index=1)
    captured = capsys.readouterr().out

    assert "close_quote=False" in captured
    assert "append_closing_quote" not in captured


def test_trace_completions_reports_zero_results(
    completer, completers_mock, xession, monkeypatch, capsys
):
    """A completer that is invoked but returns nothing still gets a header.

    Lets the user see which completers ran even when they produce no
    matches. Non-exclusive completers with 0 results must also be shown.
    """
    monkeypatch.setitem(xession.env, "XONSH_COMPLETER_TRACE", True)

    completers_mock["first"] = non_exclusive_completer(lambda *a: None)
    completers_mock["second"] = lambda *a: set()
    completers_mock["third"] = lambda *a: {"real"}

    completer.complete("pre", "", 0, 0)
    captured = capsys.readouterr().out

    assert "TRACE COMPLETIONS: Got 0 from non-exclusive 'first' for 'pre'." in captured
    assert "TRACE COMPLETIONS: Got 0 from exclusive 'second' for 'pre'." in captured
    assert "TRACE COMPLETIONS: Got 1 from exclusive 'third' for 'pre':" in captured
    # 0-result header ends with "." and has no body lines.
    assert "from non-exclusive 'first' for 'pre'.\n" in captured
