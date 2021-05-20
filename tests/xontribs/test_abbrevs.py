"""test xontrib.abbrevs"""

import importlib
import sys

from prompt_toolkit.buffer import Buffer
from pytest import fixture, mark
from xonsh.xontribs import find_xontrib


@fixture
def _buffer():
    def _wrapper(text):
        buf = Buffer()
        buf.insert_text(text)
        return buf

    return _wrapper


@fixture
def abbrevs_xontrib(monkeypatch, source_path):
    monkeypatch.syspath_prepend(source_path)
    spec = find_xontrib("abbrevs")
    yield importlib.import_module(spec.name)
    del sys.modules[spec.name]


ps_special_expand = (
    lambda buffer, word: "procs" if buffer.text.startswith(word) else word
)


@mark.parametrize(
    "abbr,val,expanded,cur",
    [
        ("ps", "procs", "procs", None),
        ("ps", ps_special_expand, "procs", None),
        ("docker ps", ps_special_expand, "docker ps", None),
        ("kill", "kill <edit> -9", "kill  -9", 5),
        ("pt", "poe<edit>try", "poetry", 3),
    ],
)
def test_gets_expanded(abbr, val, expanded, cur, abbrevs_xontrib, _buffer):
    from xontrib import abbrevs

    abbrevs.abbrevs[abbr] = val

    abbrev = abbrevs.Abbreviation()
    buf = _buffer(abbr)
    abbrev.expand(buf)
    assert buf.text == expanded
    if cur is not None:
        assert buf.cursor_position == cur
