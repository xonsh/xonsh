"""Tests for the ``@xml`` command decorator.

The ``@xml`` decorator captures subprocess output and parses it with
``xml.etree.ElementTree.fromstring`` so that ``$(@xml cmd)`` yields an
``Element`` instance ready for ``.find()`` / ``.findall()`` traversal.
"""

from xml.etree.ElementTree import Element

from xonsh.aliases import make_default_aliases
from xonsh.procs.specs import SpecAttrDecoratorAlias


def _xml_output_format():
    return make_default_aliases()["@xml"].set_attributes["output_format"]


def test_xml_decorator_registered(xession):
    aliases = make_default_aliases()
    assert "@xml" in aliases
    assert isinstance(aliases["@xml"], SpecAttrDecoratorAlias)


def test_xml_decorator_parses_element_tree(xession):
    output_format = _xml_output_format()
    root = output_format(
        ['<root attr="v">', "  <item>1</item>", "  <item>2</item>", "</root>"]
    )

    assert isinstance(root, Element)
    assert root.tag == "root"
    assert root.attrib == {"attr": "v"}
    assert [item.text for item in root.findall("item")] == ["1", "2"]


def test_xml_decorator_invalid_input_raises(xession):
    import xml.etree.ElementTree as ET

    output_format = _xml_output_format()
    try:
        output_format(["not xml"])
    except ET.ParseError:
        return
    raise AssertionError("expected ParseError on non-XML input")
