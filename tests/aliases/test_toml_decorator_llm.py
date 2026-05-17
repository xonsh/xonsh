"""Tests for the ``@toml`` command decorator.

The ``@toml`` decorator is the TOML counterpart of ``@json``/``@yaml`` —
it captures subprocess output and pipes it through ``tomllib.loads`` so
that ``$(@toml cmd)`` yields a parsed ``dict`` instead of raw text.
"""

from xonsh.aliases import make_default_aliases
from xonsh.procs.specs import SpecAttrDecoratorAlias


def test_toml_decorator_registered(xession):
    aliases = make_default_aliases()
    assert "@toml" in aliases
    assert isinstance(aliases["@toml"], SpecAttrDecoratorAlias)


def test_toml_decorator_parses_lines(xession):
    aliases = make_default_aliases()
    output_format = aliases["@toml"].set_attributes["output_format"]

    lines = [
        'title = "demo"',
        "",
        "[section]",
        "key = 42",
        'name = "x"',
    ]
    parsed = output_format(lines)

    assert parsed == {"title": "demo", "section": {"key": 42, "name": "x"}}


def test_toml_decorator_empty_input(xession):
    aliases = make_default_aliases()
    output_format = aliases["@toml"].set_attributes["output_format"]

    assert output_format([]) == {}
