"""Alias docstring shows up as the completion-dropdown description.

Both ``@aliases.register`` and ``@aliases.return_command`` produce
``FuncAlias`` instances; the wrapped function's docstring is preserved on
the alias object, and ``complete_command`` surfaces it as the
``RichCompletion.description``.
"""

import pytest

from xonsh.aliases import Aliases
from xonsh.completers.commands import (
    _alias_completion_description,
    complete_command,
)


def _completion(comps, value):
    """Return the single RichCompletion for ``value`` (assert it's there)."""
    matches = [c for c in comps if str(c) == value]
    assert len(matches) == 1, (
        f"expected exactly one completion for {value!r}, got {matches!r}"
    )
    return matches[0]


def test_register_with_docstring_shows_description(xession, completion_context_parse):
    """``@aliases.register("qwe")`` with a docstring → description is the doc."""

    @xession.aliases.register("qwe")
    def _qwe():
        """qwe asd ad"""
        pass

    comps = list(complete_command(completion_context_parse("qw", 2).command))
    completion = _completion(comps, "qwe")
    assert completion.description == "qwe asd ad"
    assert completion.provider == "alias"


def test_register_with_trailing_whitespace_in_docstring(
    xession, completion_context_parse
):
    """Trailing whitespace from a single-line docstring is stripped."""

    @xession.aliases.register("foo")
    def _foo():
        """foo description here"""
        pass

    completion = _completion(
        list(complete_command(completion_context_parse("fo", 2).command)), "foo"
    )
    assert completion.description == "foo description here"


def test_return_command_alias_with_docstring(xession, completion_context_parse):
    """``@aliases.return_command`` is a thin marker — the docstring still flows
    through ``FuncAlias`` to the completion description."""

    @Aliases.return_command
    def _bar(args):
        """bar redirects somewhere"""
        return ["echo", "redirected"] + list(args)

    xession.aliases["bar"] = _bar

    completion = _completion(
        list(complete_command(completion_context_parse("ba", 2).command)), "bar"
    )
    assert completion.description == "bar redirects somewhere"
    assert completion.provider == "alias"


def test_register_then_return_command_combined(xession, completion_context_parse):
    """Stacking ``@aliases.register`` on top of ``@aliases.return_command``
    is the canonical way to register a return-command alias — the
    docstring still surfaces."""

    @xession.aliases.register("baz")
    @Aliases.return_command
    def _baz(args):
        """baz hands off the command"""
        return ["echo", "hi"]

    completion = _completion(
        list(complete_command(completion_context_parse("ba", 2).command)), "baz"
    )
    assert completion.description == "baz hands off the command"


def test_multiline_docstring_uses_first_nonempty_line(
    xession, completion_context_parse
):
    """A PEP 257-style multi-line docstring contributes only the summary
    line to the dropdown description (which is single-line)."""

    @xession.aliases.register("multi")
    def _multi():
        """Summary line.

        Body paragraph that should not appear in the dropdown.
        """
        pass

    completion = _completion(
        list(complete_command(completion_context_parse("mu", 2).command)), "multi"
    )
    assert completion.description == "Summary line."


def test_indented_first_line_is_dedented(xession, completion_context_parse):
    """First non-empty line of an indented docstring still produces a
    clean, unindented summary."""

    @xession.aliases.register("dent")
    def _dent():
        """
        First real line, indented in source.
        """
        pass

    completion = _completion(
        list(complete_command(completion_context_parse("de", 2).command)), "dent"
    )
    assert completion.description == "First real line, indented in source."


def test_no_docstring_falls_back_to_alias_label_only_when_show_desc(
    xession, completion_context_parse
):
    """Without a docstring: empty description by default; ``"Alias"`` only
    when ``$CMD_COMPLETIONS_SHOW_DESC`` is on."""

    @xession.aliases.register("nodoc")
    def _nodoc():
        pass

    # Default: no docstring, no description.
    xession.env["CMD_COMPLETIONS_SHOW_DESC"] = False
    completion = _completion(
        list(complete_command(completion_context_parse("no", 2).command)), "nodoc"
    )
    assert completion.description == ""

    # Opted in: legacy "Alias" placeholder.
    xession.env["CMD_COMPLETIONS_SHOW_DESC"] = True
    completion = _completion(
        list(complete_command(completion_context_parse("no", 2).command)), "nodoc"
    )
    assert completion.description == "Alias"


def test_docstring_shows_regardless_of_show_desc(xession, completion_context_parse):
    """Writing a docstring is an explicit opt-in; surface it whether or not
    ``$CMD_COMPLETIONS_SHOW_DESC`` is enabled."""

    @xession.aliases.register("docalways")
    def _docalways():
        """always shown"""
        pass

    for show_desc in (False, True):
        xession.env["CMD_COMPLETIONS_SHOW_DESC"] = show_desc
        completion = _completion(
            list(complete_command(completion_context_parse("doc", 3).command)),
            "docalways",
        )
        assert completion.description == "always shown"


def test_string_and_list_aliases_have_no_description(xession, completion_context_parse):
    """Plain string and list aliases carry no docstring; description falls
    back to the legacy behaviour."""

    xession.aliases["lsx"] = ["ls", "-G"]
    xession.aliases["greppy"] = "echo hi"

    xession.env["CMD_COMPLETIONS_SHOW_DESC"] = True
    comps = list(complete_command(completion_context_parse("ls", 2).command))
    assert _completion(comps, "lsx").description == "Alias"
    comps = list(complete_command(completion_context_parse("gre", 3).command))
    assert _completion(comps, "greppy").description == "Alias"


def test_alias_completion_description_helper_handles_missing_aliases():
    """The helper tolerates ``aliases=None`` and unknown names."""
    assert _alias_completion_description(None, "anything") == ""

    aliases = Aliases()
    assert _alias_completion_description(aliases, "absent") == ""


# ---------------------------------------------------------------------------
# Aliases.get_doc — the underlying API the completer (and ``cmd?``) consume.
# ---------------------------------------------------------------------------


def test_get_doc_funcalias_with_docstring():
    aliases = Aliases()

    @aliases.register("hello")
    def _hello():
        """Greet the world."""
        pass

    assert aliases.get_doc("hello") == "Greet the world."


def test_get_doc_funcalias_without_docstring_returns_empty():
    """Critical: must NOT leak ``FuncAlias.__doc__`` (the class docstring)."""
    aliases = Aliases()

    @aliases.register("plain")
    def _plain():
        pass

    assert aliases.get_doc("plain") == ""


def test_get_doc_string_alias_returns_empty():
    aliases = Aliases()
    aliases["echohi"] = "echo hi"
    assert aliases.get_doc("echohi") == ""


def test_get_doc_list_alias_returns_empty():
    aliases = Aliases()
    aliases["lsg"] = ["ls", "-G"]
    assert aliases.get_doc("lsg") == ""


def test_get_doc_missing_alias_returns_empty():
    aliases = Aliases()
    assert aliases.get_doc("does-not-exist") == ""


def test_get_doc_multiline_is_dedented():
    aliases = Aliases()

    @aliases.register("ml")
    def _ml():
        """First line.

        Second paragraph that
        spans multiple lines.
        """
        pass

    expected = "First line.\n\nSecond paragraph that\nspans multiple lines."
    assert aliases.get_doc("ml") == expected


@pytest.mark.parametrize(
    "decorator_factory",
    [
        # @aliases.register("name")
        lambda aliases: aliases.register("decorated"),
        # @Aliases.return_command followed by aliases.register
        lambda aliases: (
            lambda f: aliases.register("decorated")(Aliases.return_command(f))
        ),
    ],
    ids=["register", "register+return_command"],
)
def test_get_doc_works_for_register_and_return_command(decorator_factory):
    """Single source of truth for both decorator forms — the docstring
    is preserved through ``FuncAlias`` regardless of ``return_what``."""
    aliases = Aliases()

    @decorator_factory(aliases)
    def _decorated(args=None):
        """decorated alias docstring"""
        return ["true"]

    assert aliases.get_doc("decorated") == "decorated alias docstring"


# ---------------------------------------------------------------------------
# Click integration — ``@aliases.register_click_command`` flows the user's
# docstring through ``functools.update_wrapper`` to the wrapper that
# ``register()`` ultimately wraps in ``FuncAlias``.
# ---------------------------------------------------------------------------


def test_register_click_command_surfaces_docstring(xession, completion_context_parse):
    """Bare ``@aliases.register_click_command`` (no parens, plain function)."""
    pytest.importorskip("click")

    @xession.aliases.register_click_command
    def my_click(ctx):
        """My click command summary"""
        pass

    completion = _completion(
        list(complete_command(completion_context_parse("my", 2).command)), "my-click"
    )
    assert completion.description == "My click command summary"
    assert completion.provider == "alias"


def test_register_click_command_with_explicit_name(xession, completion_context_parse):
    """``@aliases.register_click_command("custom-name")``."""
    pytest.importorskip("click")

    @xession.aliases.register_click_command("renamed-cmd")
    def _renamed(ctx):
        """Renamed click cmd"""
        pass

    completion = _completion(
        list(complete_command(completion_context_parse("ren", 3).command)),
        "renamed-cmd",
    )
    assert completion.description == "Renamed click cmd"


def test_register_click_command_on_predecorated_click_command(
    xession, completion_context_parse
):
    """Stacking ``@aliases.register_click_command`` on top of an existing
    ``@click.command()`` chain — the docstring still travels via
    ``functools.update_wrapper`` and surfaces in the dropdown."""
    click = pytest.importorskip("click")

    @xession.aliases.register_click_command
    @click.command()
    @click.argument("name")
    def predecorated(ctx, name):
        """Pre-decorated click command"""
        pass

    completion = _completion(
        list(complete_command(completion_context_parse("pre", 3).command)),
        "predecorated",
    )
    assert completion.description == "Pre-decorated click command"


def test_register_click_command_get_doc_directly():
    """Same flow at the ``Aliases.get_doc`` level — independent of the
    completer pipeline."""
    pytest.importorskip("click")
    aliases = Aliases()

    @aliases.register_click_command
    def hello(ctx):
        """Hello click cmd"""
        pass

    assert aliases.get_doc("hello") == "Hello click cmd"


# ---------------------------------------------------------------------------
# Dict-form setter — ``aliases[k] = {"alias": ..., "doc": "..."}``.
#
# Lets list/string aliases (which have no ``__doc__`` slot) carry a
# description, and lets callable aliases override their function's docstring
# with a different one-line summary. ``__ior__`` / ``|=`` flow through
# ``__setitem__`` so the same form works for bulk merging.
# ---------------------------------------------------------------------------


def test_dict_form_string_alias_carries_doc():
    aliases = Aliases()
    aliases["qwe"] = {"alias": "ls -la", "doc": "All files"}
    assert aliases.get_doc("qwe") == "All files"


def test_dict_form_list_alias_carries_doc():
    aliases = Aliases()
    aliases["lsg"] = {"alias": ["ls", "-G"], "doc": "Coloured ls"}
    assert aliases.get_doc("lsg") == "Coloured ls"
    assert aliases["lsg"] == ["ls", "-G"]


def test_dict_form_overrides_funcalias_docstring():
    """Explicit ``doc`` wins over the wrapped function's ``__doc__`` —
    it's the user's one-line summary, takes priority."""
    aliases = Aliases()

    def _bar():
        """from docstring"""
        pass

    aliases["bar"] = {"alias": _bar, "doc": "OVERRIDE"}
    assert aliases.get_doc("bar") == "OVERRIDE"


def test_dict_form_without_doc_falls_back_to_funcalias_docstring():
    """If ``doc`` is omitted, the alias's own ``__doc__`` is still used —
    dict-form is purely additive."""
    aliases = Aliases()

    def _bar():
        """from docstring"""
        pass

    aliases["bar"] = {"alias": _bar}
    assert aliases.get_doc("bar") == "from docstring"


def test_dict_form_empty_doc_string_is_treated_as_no_doc():
    """``"doc": ""`` does not register a description (so a later non-empty
    function docstring still wins)."""
    aliases = Aliases()

    def _bar():
        """from docstring"""
        pass

    aliases["bar"] = {"alias": _bar, "doc": ""}
    assert aliases.get_doc("bar") == "from docstring"


def test_rewrite_without_doc_clears_stale_doc():
    """Reassigning a key without an explicit doc must drop the previous
    dict-form description so it doesn't stick to a different value."""
    aliases = Aliases()
    aliases["qwe"] = {"alias": "ls -la", "doc": "All files"}
    assert aliases.get_doc("qwe") == "All files"

    aliases["qwe"] = "ls"
    assert aliases.get_doc("qwe") == ""


def test_delete_clears_doc():
    aliases = Aliases()
    aliases["baz"] = {"alias": "echo hi", "doc": "Greet"}
    assert aliases.get_doc("baz") == "Greet"

    del aliases["baz"]
    assert aliases.get_doc("baz") == ""
    assert "baz" not in aliases._docs


def test_ior_propagates_dict_form_doc():
    """``aliases |= {"k": {"alias": ..., "doc": ...}}`` flows through
    ``__setitem__`` and ends up in the doc registry."""
    aliases = Aliases()
    aliases |= {"foo": {"alias": "ps aux", "doc": "Process list"}}
    assert aliases.get_doc("foo") == "Process list"


def test_or_with_plain_dict_preserves_self_docs_and_applies_other_docs():
    """``a | {"k": dict-form}`` — produces a new Aliases with self's
    docs preserved (for non-overridden keys) and other's docs applied."""
    a = Aliases()
    a["a"] = {"alias": "ls", "doc": "self-A"}
    a["b"] = {"alias": "ps", "doc": "self-B"}

    merged = a | {"b": {"alias": "ps -ef", "doc": "other-B"}, "c": "echo"}

    assert merged.get_doc("a") == "self-A"
    assert merged.get_doc("b") == "other-B"
    assert merged.get_doc("c") == ""


def test_or_with_other_aliases_propagates_other_docs():
    """When the right operand is itself an ``Aliases`` instance, its docs
    travel through too — even though ``Aliases.__getitem__`` returns raw
    values without dict-form wrapping."""
    a = Aliases()
    a["a"] = {"alias": "ls", "doc": "self-A"}

    b = Aliases()
    b["b"] = {"alias": "ps", "doc": "other-B"}

    merged = a | b
    assert merged.get_doc("a") == "self-A"
    assert merged.get_doc("b") == "other-B"


def test_or_other_overrides_without_doc_drops_self_doc():
    """If ``other`` overrides a key without supplying a doc, ``self``'s old
    doc is dropped — it described the previous value, not the name."""
    a = Aliases()
    a["k"] = {"alias": "ls", "doc": "self-K"}

    merged = a | {"k": "echo"}
    assert merged.get_doc("k") == ""


def test_ior_with_other_aliases_propagates_docs():
    a = Aliases()
    a["a"] = {"alias": "ls", "doc": "self-A"}

    b = Aliases()
    b["b"] = {"alias": "ps", "doc": "other-B"}

    a |= b
    assert a.get_doc("a") == "self-A"
    assert a.get_doc("b") == "other-B"


def test_dict_form_completion_description():
    """End-to-end through the completer: dict-form doc shows up as the
    ``RichCompletion.description``."""
    # Use a fresh Aliases instance via xession monkeypatch indirectly —
    # this test goes straight through ``Aliases.get_doc``, which the
    # completer helper also calls.
    aliases = Aliases()
    aliases["foo"] = {"alias": "ps aux", "doc": "Process list"}
    assert _alias_completion_description(aliases, "foo") == "Process list"


def test_dict_form_extra_keys_ignored():
    """Unknown keys in the dict-form value are silently ignored — this
    leaves room for future extensions (e.g. ``"category"``) without
    breaking existing rc files."""
    aliases = Aliases()
    aliases["k"] = {
        "alias": "ls",
        "doc": "Listing",
        "category": "fs",  # not yet meaningful, must not raise
    }
    assert aliases.get_doc("k") == "Listing"


def test_dict_form_multiline_doc_is_dedented():
    aliases = Aliases()
    aliases["k"] = {
        "alias": "ls",
        "doc": "Summary line.\n\n    Body paragraph indented in source.",
    }
    expected = "Summary line.\n\nBody paragraph indented in source."
    assert aliases.get_doc("k") == expected
