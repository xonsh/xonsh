"""Smoke tests for the ``xonsh.webconfig`` package.

The webconfig module powers the browser-based "xonfig web" UI. These tests
exercise the pure parts that don't need an HTTP server:

* ``tags`` — the tiny element-tree wrapper used to render snippets.
* ``file_writes`` — the helper that injects a config dict into ``xonshrc``.
* ``xonsh_data`` — the data-collectors used by the UI's color/prompt previews.
"""

import pytest

from xonsh.webconfig import file_writes, tags, xonsh_data


# --- tags.Elem --------------------------------------------------------------


def test_elem_basic_rendering():
    e = tags.Elem("span", "highlight", id="x")
    out = tags.to_str(e)
    assert "highlight" in out
    assert 'id="x"' in out
    assert "<span" in out


def test_elem_multiple_classes_merged():
    e = tags.Elem("div", "a", "b", **{"data-x": "1"})
    out = tags.to_str(e)
    assert 'class="a b"' in out
    assert 'data-x="1"' in out


def test_elem_set_attrib_appends_classes():
    """``Elem.set_attrib`` accumulates classes across calls."""
    e = tags.div("x")
    e.set_attrib("y")
    out = tags.to_str(e)
    # both classes present, order not strictly defined
    assert "x" in out and "y" in out


def test_elem_callable_alias_for_set_attrib():
    e = tags.div()
    e("foo", id="x")
    out = tags.to_str(e)
    assert 'class="foo"' in out
    assert 'id="x"' in out


def test_elem_getitem_str_appends_to_text():
    e = tags.p()["hello"]
    out = tags.to_str(e)
    assert ">hello<" in out


def test_elem_getitem_string_concatenates():
    e = tags.p()
    e["a"]
    e["b"]
    out = tags.to_str(e)
    assert ">ab<" in out


def test_elem_getitem_appends_child_elem():
    parent = tags.div()
    child = tags.p()["text"]
    parent[child]
    out = tags.to_str(parent)
    assert "<div" in out
    assert ">text<" in out


def test_elem_getitem_iterable_appends_children():
    parent = tags.div()
    parent[(tags.p()["a"], tags.p()["b"])]
    out = tags.to_str(parent)
    assert ">a<" in out
    assert ">b<" in out


def test_elem_getitem_int_returns_indexed_child():
    parent = tags.div()
    a = tags.p()["a"]
    b = tags.p()["b"]
    parent.append(a)
    parent.append(b)
    assert parent[0] is a
    assert parent[1] is b


# --- tags.to_str / to_pretty -----------------------------------------------


def test_to_str_iterable_of_elems():
    elems = [tags.p()["one"], tags.p()["two"]]
    out = tags.to_str(elems)
    assert ">one<" in out
    assert ">two<" in out


def test_to_str_debug_pretty_prints():
    e = tags.div(id="x")[tags.p()["hi"]]
    out = tags.to_str(e, debug=True)
    # pretty XML inserts newlines between tags
    assert "\n" in out
    assert "<div" in out


def test_to_pretty_smoke():
    raw = "<div><p>hi</p></div>"
    out = tags.to_pretty(raw)
    assert "div" in out
    assert "p" in out


# --- tags partial helpers ---------------------------------------------------


def test_partial_helpers_render_correct_tag_and_class():
    """``row`` is just ``div`` with class ``row``; verify a few helpers."""
    assert tags.to_str(tags.row()).startswith('<div class="row"')
    assert tags.to_str(tags.col()).startswith('<div class="col"')
    assert tags.to_str(tags.alert()).startswith('<div class="alert"')
    assert 'role="alert"' in tags.to_str(tags.alert())


def test_card_helpers_render_card_classes():
    assert "card" in tags.to_str(tags.card())
    assert "card-body" in tags.to_str(tags.card_body())
    assert "card-header" in tags.to_str(tags.card_header())


def test_btn_primary_has_btn_classes():
    out = tags.to_str(tags.btn_primary())
    assert "btn" in out
    assert "btn-primary" in out
    assert 'type="button"' in out


# --- file_writes ------------------------------------------------------------


def test_write_value_quotes_string():
    assert file_writes.write_value("hello", "") == "'hello'"


def test_append_to_list_with_no_existing():
    out = file_writes.append_to_list(["a", "b"], "")
    assert set(out.split()) == {"a", "b"}


def test_append_to_list_with_existing_dedupes():
    out = file_writes.append_to_list(["a", "b"], "a c")
    assert set(out.split()) == {"a", "b", "c"}


def test_config_to_xonsh_emits_prefix_and_suffix():
    lines = list(
        file_writes.config_to_xonsh(
            {"prompt": "@ "},
            prefix="# START",
            suffix="# END",
        )
    )
    assert lines[0] == "# START"
    assert lines[-1] == "# END"
    assert any("$PROMPT" in line for line in lines)


def test_config_to_xonsh_preserves_unmatched_existing_lines():
    """Lines that don't match any RENDERER are passed through verbatim."""
    out = list(
        file_writes.config_to_xonsh(
            {},
            prefix="# S",
            suffix="# E",
            current_lines=["# random comment"],
        )
    )
    assert "# random comment" in out


def test_config_to_xonsh_replaces_existing_prompt_line():
    out = list(
        file_writes.config_to_xonsh(
            {"prompt": "$ "},
            prefix="# S",
            suffix="# E",
            current_lines=["$PROMPT = 'old'"],
        )
    )
    # the new value replaces the old line — the literal new prompt is in output
    assert any("$PROMPT" in line and "$ " in line for line in out)
    # the literal old value is no longer present
    assert not any("'old'" in line for line in out)


def test_insert_into_xonshrc_writes_new_file(tmp_path):
    rc = tmp_path / "test_xonshrc"
    fname = file_writes.insert_into_xonshrc(
        {"prompt": "@ "}, xonshrc=str(rc), prefix="# S", suffix="# E"
    )
    assert fname == str(rc)
    text = rc.read_text()
    assert "# S" in text
    assert "# E" in text
    assert "$PROMPT" in text


def test_insert_into_xonshrc_preserves_outer_content(tmp_path):
    """Content outside the prefix..suffix block survives the rewrite."""
    rc = tmp_path / "rcfile"
    rc.write_text("before-the-block\n# S\n$PROMPT = 'old'\n# E\nafter-the-block\n")
    file_writes.insert_into_xonshrc(
        {"prompt": "@ "}, xonshrc=str(rc), prefix="# S", suffix="# E"
    )
    text = rc.read_text()
    assert "before-the-block" in text
    assert "after-the-block" in text
    # the new prompt value replaces the old one
    assert "@ " in text
    assert "'old'" not in text


# --- xonsh_data -------------------------------------------------------------


def test_invert_color_round_trips_extreme_values():
    # 000000 inverts to ffffff and vice versa
    assert xonsh_data.invert_color("000000").lower() == "ffffff"
    assert xonsh_data.invert_color("ffffff").lower() == "000000"


def test_invert_color_pads_short_components():
    """Hex components < 16 must be left-padded with a leading zero."""
    inv = xonsh_data.invert_color("ffff01")  # last byte = 0xfe
    assert inv.lower().endswith("fe")


def test_escape_replaces_newlines_with_br():
    assert xonsh_data.escape("a\nb") == "a<br/>b"


def test_get_named_prompts_returns_iterable_of_pairs():
    prompts = list(xonsh_data.get_named_prompts())
    assert prompts
    assert all(isinstance(p, tuple) and len(p) == 2 for p in prompts)
    # the first one is the canonical default prompt
    assert prompts[0][0] == "default"


def test_format_xontrib_returns_dict_with_expected_keys():
    from xonsh.xontribs import Xontrib

    out = xonsh_data.format_xontrib(Xontrib(module="xontrib.does_not_exist"))
    assert set(out.keys()) == {"url", "license", "display"}


def test_render_xontribs_yields_pairs():
    iter_ = xonsh_data.render_xontribs()
    pair = next(iter_, None)
    if pair is None:
        pytest.skip("no xontribs discovered in this environment")
    name, payload = pair
    assert isinstance(name, str)
    assert "display" in payload


def test_html_format_returns_html_string(xession):
    """``html_format`` produces inline-styled HTML for a color template."""
    out = xonsh_data.html_format("hello world")
    assert "<" in out and ">" in out


def test_rst_to_html_smoke():
    out = xonsh_data.rst_to_html("Hello *world*")
    assert isinstance(out, str)
    assert "world" in out
