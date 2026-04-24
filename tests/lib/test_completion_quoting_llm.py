"""Tests for :func:`xonsh.lib.completion_quoting.name_needs_quotes`.

Pins down *which* characters force quoting in completions, verified
against the xonsh completion-context parser (i.e. "does feeding
``ls fi<ch>le`` through the parser keep the token whole?"). Regressions
here mean broken completions for files whose names contain shell
metacharacters.
"""

import os

import pytest

from xonsh.lib.completion_quoting import name_needs_quotes


@pytest.mark.parametrize(
    "ch",
    [
        " ",  # whitespace — splits tokens
        "\t",  # whitespace
        "|",  # pipe
        ";",  # statement separator
        "<",  # redirect
        ">",  # redirect
        "&",  # async / &&
        "`",  # command substitution
        "$",  # variable expansion
        "*",  # glob star
        "?",  # glob question
        "(",  # subproc paren
        ")",
        "[",  # glob bracket
        "]",
        "{",  # glob brace
        "}",
        ",",  # brace-list sep
        '"',  # string boundary
        "'",  # string boundary
        "#",  # comment
    ],
    ids=lambda c: f"char={c!r}",
)
def test_special_char_forces_quoting(ch):
    """Every xonsh metacharacter must force quoting when present in a
    completion candidate, otherwise the parser will split the token.
    """
    assert name_needs_quotes(f"fi{ch}le") is True


@pytest.mark.parametrize("word", ["and", "or"])
def test_xonsh_keywords_force_quoting(word):
    """``and`` / ``or`` are xonsh operator keywords — a bare ``name and
    other`` would be parsed as a boolean expression, not two args.
    """
    assert name_needs_quotes(word) is True
    # as a whole sub-token, still quoting (e.g. ``foo and``)
    assert name_needs_quotes(f"foo {word}") is True


@pytest.mark.parametrize(
    "name",
    [
        "file",
        "file.txt",
        "README.md",
        "and_more",  # 'and' as substring, not whole word — fine
        "notfile",  # 'not' as substring — fine
        "or_else",  # 'or' as substring — fine
        "~file",  # tilde/at/bang/etc. at token boundaries are OK
        "@file",
        "!file",
        "=file",
        ":file",
        "^file",
        "file!",
        "file=",
        "file~",
        "fi!le",  # mid-token
        "fi@le",
        "fi:le",
        "fi^le",
    ],
    ids=lambda n: f"name={n!r}",
)
def test_plain_names_do_not_force_quoting(name):
    """Names whose characters are all safe in xonsh's subprocess-arg
    context must NOT be quoted — otherwise every completion ends up
    wrapped in quotes for no reason.
    """
    assert name_needs_quotes(name) is False


def test_backslash_requires_mismatched_sep():
    """A backslash is a metachar only when it isn't the platform
    separator. On POSIX (``sep='/'``), ``C:\\path`` needs quoting; on
    Windows (``sep='\\'``), a bare backslash in a path is fine.
    """
    # POSIX: backslash is a shell escape char.
    assert name_needs_quotes(r"a\b", sep="/") is True
    # Windows: backslash IS the separator.
    assert name_needs_quotes(r"a\b", sep="\\") is False


def test_default_sep_is_os_sep():
    """When ``sep`` is omitted the helper falls back to ``os.sep`` —
    callers that don't know the xonsh-configured separator still get
    sensible answers for the current platform.
    """
    # Use a name that's backslash-only-special, so the answer depends
    # entirely on the sep.
    if os.sep == "/":
        assert name_needs_quotes(r"a\b") is True
    else:
        assert name_needs_quotes(r"a\b") is False
