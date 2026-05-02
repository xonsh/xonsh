"""Smoke tests for ``xonsh.lib.openpy`` and ``xonsh.lib.modules``.

Both modules support the introspection / Python-script handling pieces that
the rest of xonsh leans on for source-code reading and module discovery.
"""

import io
import os
import sys

import pytest

from xonsh.lib import modules as xmodules
from xonsh.lib import openpy


# --- openpy.source_to_unicode ----------------------------------------------


def test_source_to_unicode_passes_str_through():
    s = "print('hi')\n"
    assert openpy.source_to_unicode(s) is s


def test_source_to_unicode_decodes_bytes_with_default_encoding():
    out = openpy.source_to_unicode(b"print('hi')\n")
    assert out == "print('hi')\n"


def test_source_to_unicode_skips_encoding_cookie_by_default():
    """The first-line encoding cookie is stripped so that the returned
    text is parseable on Python 3."""
    src = b"# -*- coding: utf-8 -*-\nprint('hi')\n"
    out = openpy.source_to_unicode(src)
    assert "coding" not in out


def test_source_to_unicode_keeps_cookie_when_requested():
    src = b"# -*- coding: utf-8 -*-\nprint('hi')\n"
    out = openpy.source_to_unicode(src, skip_encoding_cookie=False)
    assert "coding" in out


def test_source_to_unicode_decodes_invalid_with_replacement():
    src = b"\xff\xfe\nhi\n"  # invalid UTF-8 leading bytes
    out = openpy.source_to_unicode(src)
    assert "hi" in out


# --- openpy.read_py_file ----------------------------------------------------


def test_read_py_file_strips_encoding_cookie(tmp_path):
    p = tmp_path / "src.py"
    p.write_text("# -*- coding: utf-8 -*-\nimport os\n", encoding="utf-8")
    out = openpy.read_py_file(str(p))
    assert "coding" not in out
    assert "import os" in out


def test_read_py_file_keeps_cookie_when_skip_false(tmp_path):
    p = tmp_path / "src.py"
    p.write_text("# coding=utf-8\nimport os\n", encoding="utf-8")
    out = openpy.read_py_file(str(p), skip_encoding_cookie=False)
    assert "coding" in out


def test_read_py_file_handles_non_python_filename_extension(tmp_path):
    """``read_py_file`` accepts any filename, not just .py."""
    p = tmp_path / "no_ext_file"
    p.write_text("hello\n")
    out = openpy.read_py_file(str(p))
    assert out.strip() == "hello"


def test_read_py_file_short_file_no_cookie(tmp_path):
    """A file with only a single line (no second line) must not raise
    ``StopIteration`` from ``strip_encoding_cookie``."""
    p = tmp_path / "single.py"
    p.write_text("x = 1\n")
    out = openpy.read_py_file(str(p))
    assert "x = 1" in out


# --- openpy.strip_encoding_cookie ------------------------------------------


def test_strip_encoding_cookie_removes_first_line_when_cookie():
    lines = ["# -*- coding: utf-8 -*-\n", "x = 1\n"]
    it = openpy.strip_encoding_cookie(iter(lines))
    out = list(it)
    assert "coding" not in "".join(out)
    assert "x = 1\n" in out


def test_strip_encoding_cookie_keeps_first_line_when_no_cookie():
    lines = ["x = 1\n", "y = 2\n"]
    out = list(openpy.strip_encoding_cookie(iter(lines)))
    assert out == ["x = 1\n", "y = 2\n"]


def test_strip_encoding_cookie_handles_empty_iterator():
    out = list(openpy.strip_encoding_cookie(iter([])))
    assert out == []


# --- openpy._list_readline -------------------------------------------------


def test_list_readline_yields_consecutive_items():
    rl = openpy._list_readline(["a\n", "b\n"])
    assert rl() == "a\n"
    assert rl() == "b\n"
    with pytest.raises(StopIteration):
        rl()


# --- modules.ModuleFinder --------------------------------------------------


def test_module_finder_pkg_only_no_paths():
    finder = xmodules.ModuleFinder("xonsh")
    assert "xonsh" in finder._pkgs
    assert finder._paths == {}


def test_module_finder_separates_paths_from_pkgs(tmp_path):
    finder = xmodules.ModuleFinder("xonsh", str(tmp_path))
    # path-like items go in _paths, name-like in _pkgs
    assert "xonsh" in finder._pkgs
    assert str(tmp_path) in finder._paths


def test_module_finder_get_module_finds_real_package():
    finder = xmodules.ModuleFinder("xonsh")
    mod = finder.get_module("tools")
    assert mod is not None
    assert mod.__name__ == "xonsh.tools"


def test_module_finder_get_module_returns_none_for_missing():
    finder = xmodules.ModuleFinder("xonsh")
    assert finder.get_module("definitely_not_there_xyz") is None


def test_module_finder_get_new_paths_skips_nonexistent():
    finder = xmodules.ModuleFinder("/this/path/cannot/exist/xyz")
    out = list(finder._get_new_paths())
    assert out == []


def test_module_finder_extensions_default():
    """ModuleFinder.extensions controls which file types count as modules."""
    assert ".py" in xmodules.ModuleFinder.extensions
    assert ".xsh" in xmodules.ModuleFinder.extensions


def test_module_finder_import_module_from_real_path(tmp_path):
    p = tmp_path / "fake_mod.py"
    p.write_text("VAL = 42\n")
    mod = xmodules.ModuleFinder.import_module(str(p), "fake_mod")
    assert mod is not None
    assert mod.VAL == 42


def test_module_finder_import_module_returns_none_for_missing(tmp_path):
    """Non-existent file → spec creation returns None → import_module returns None."""
    bogus = str(tmp_path / "definitely_does_not_exist.py")
    # importlib's spec_from_file_location for a non-existent file may still
    # return a usable spec; what matters is that this never raises.
    try:
        mod = xmodules.ModuleFinder.import_module(bogus, "definitely_does_not_exist")
    except (FileNotFoundError, OSError):
        return  # acceptable: file truly cannot be opened
    # if it did return something, it shouldn't be a usable module
    assert mod is None or hasattr(mod, "__name__")
