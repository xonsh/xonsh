"""Smoke tests for ``xonsh.wizard``.

The wizard machinery is a tree of ``Node`` subclasses plus a couple of
``Visitor``s that walk the tree. These tests cover:

* node-tree construction and ``__repr__`` (via ``PrettyFormatter``)
* the ``StateVisitor`` storage / flattening machinery
* the ``FileInserter`` rule-matching logic
* the helper utilities ``ensure_str_or_int`` / ``canon_path`` / ``Unstorable``
"""

import re

import pytest

from xonsh.wizard import (
    FileInserter,
    Input,
    LoadJSON,
    Message,
    Node,
    Pass,
    PrettyFormatter,
    Question,
    SaveJSON,
    StateVisitor,
    StoreNonEmpty,
    TrueFalse,
    TrueFalseBreak,
    Unstorable,
    UnstorableType,
    Visitor,
    While,
    Wizard,
    YesNo,
    canon_path,
    create_truefalse_cond,
    ensure_str_or_int,
)


# --- Node tree construction -------------------------------------------------


def test_node_attrs_default_empty():
    n = Node()
    assert n.attrs == ()


def test_pass_has_empty_attrs():
    p = Pass()
    assert p.attrs == ()


def test_message_stores_text():
    m = Message("hello")
    assert m.message == "hello"


def test_question_holds_responses():
    q = Question("Q?", responses={"a": Pass(), "b": Pass()}, path="/p")
    assert q.question == "Q?"
    assert set(q.responses) == {"a", "b"}
    assert q.path == "/p"


def test_input_default_prompt_and_attrs():
    i = Input()
    assert i.prompt == ">>> "
    assert i.confirm is False
    assert i.retry is False
    assert i.path is None


def test_yesno_responses_are_bool_keyed():
    y = YesNo("ok?", yes=Pass(), no=Pass())
    assert set(y.responses) == {True, False}


def test_truefalse_uses_to_bool_converter():
    tf = TrueFalse()
    # the converter is xonsh.tools.to_bool
    assert callable(tf.converter)
    assert tf.converter("yes") is True
    assert tf.converter("no") is False


def test_truefalsebreak_handles_break():
    tfb = TrueFalseBreak()
    assert tfb.converter("break") == "break"


def test_storenonempty_returns_unstorable_for_empty_input():
    s = StoreNonEmpty()
    assert s.converter("") is Unstorable
    assert s.converter("nonempty") == "nonempty"


def test_storenonempty_with_explicit_converter():
    s = StoreNonEmpty(converter=int)
    assert s.converter("42") == 42
    assert s.converter("") is Unstorable


def test_while_node_attrs():
    body = [Pass()]
    w = While(cond=lambda **kw: False, body=body, idxname="i", beg=10)
    assert w.body is body
    assert w.idxname == "i"
    assert w.beg == 10


# --- StateFile family -------------------------------------------------------


def test_savejson_default_filename_prompt():
    s = SaveJSON()
    assert s.prompt == "filename: "
    s.default_file = "/tmp/x.json"
    assert "/tmp/x.json" in s.prompt


def test_loadjson_inherits_from_statefile():
    f = LoadJSON()
    assert hasattr(f, "default_file")
    assert hasattr(f, "ask_filename")


def test_fileinserter_compiles_dump_rules():
    fi = FileInserter(
        prefix="# START",
        suffix="# END",
        dump_rules={"/path/to/exact": lambda p, x: str(x), "/other/*": None},
    )
    assert fi.prefix == "# START"
    # dump_rules now hold compiled regex objects as keys
    assert all(isinstance(k, re.Pattern) for k in fi.dump_rules.keys())


def test_fileinserter_find_rule_exact_match():
    fi = FileInserter(
        prefix="",
        suffix="",
        dump_rules={"/a/b": lambda p, x: f"line:{x}"},
    )
    rule, func = fi.find_rule("/a/b")
    assert callable(func)
    assert func("/a/b", 5) == "line:5"


def test_fileinserter_find_rule_no_match_returns_path_and_none():
    fi = FileInserter(prefix="", suffix="", dump_rules={"/a/b": None})
    _, func = fi.find_rule("/c/d")
    assert func is None


def test_fileinserter_dumps_skips_none_funcs():
    fi = FileInserter(
        prefix="START",
        suffix="END",
        dump_rules={"/x": None, "/y": lambda p, v: f"y={v}"},
    )
    out = fi.dumps({"/x": 1, "/y": 2})
    assert "x=" not in out
    assert "y=2" in out
    assert out.startswith("START")
    assert out.rstrip().endswith("END")


# --- ensure_str_or_int ------------------------------------------------------


@pytest.mark.parametrize("v,expected", [(1, 1), (-3, -3), ("5", 5), ("foo", "foo")])
def test_ensure_str_or_int_passes(v, expected):
    assert ensure_str_or_int(v) == expected


def test_ensure_str_or_int_rejects_dicts():
    with pytest.raises(ValueError):
        ensure_str_or_int({"a": 1})


def test_ensure_str_or_int_rejects_floats():
    with pytest.raises(ValueError):
        ensure_str_or_int("1.5")


# --- canon_path -------------------------------------------------------------


def test_canon_path_string_strips_slashes():
    assert canon_path("/a/b/") == ("a", "b")


def test_canon_path_root_is_empty_tuple():
    assert canon_path("/") == ()


def test_canon_path_with_format_indices():
    assert canon_path("/a/{i}", indices={"i": 3}) == ("a", 3)


def test_canon_path_passthrough_for_tuple():
    assert canon_path(("a", 1, "b")) == ("a", 1, "b")


# --- Unstorable / UnstorableType -------------------------------------------


def test_unstorable_is_singleton():
    assert UnstorableType() is Unstorable


# --- Visitor + StateVisitor -------------------------------------------------


def test_visitor_raises_when_no_tree_or_node():
    v = Visitor()
    with pytest.raises(RuntimeError):
        v.visit()


def test_visitor_missing_method_raises_attribute_error():
    """Visitor that has no ``visit_<typename>`` for the node must raise."""

    class _Bare(Visitor):
        pass

    v = _Bare()
    with pytest.raises(AttributeError):
        v.visit(Pass())


def test_state_visitor_store_creates_nested_dicts():
    sv = StateVisitor()
    sv.store("/a/b/c", 42)
    assert sv.state == {"a": {"b": {"c": 42}}}


def test_state_visitor_store_creates_list_when_int_path_segment():
    sv = StateVisitor()
    sv.store(("xs", 0), "first")
    sv.store(("xs", 1), "second")
    assert sv.state == {"xs": ["first", "second"]}


def test_state_visitor_flatten_round_trip():
    sv = StateVisitor(state={"a": {"b": 1}})
    flat = sv.flatten()
    assert flat["/"] == {"a": {"b": 1}}
    assert flat["/a/"] == {"b": 1}
    assert flat["/a/b"] == 1


# --- create_truefalse_cond --------------------------------------------------


def test_create_truefalse_cond_returns_callable():
    cond = create_truefalse_cond(prompt="ok? ", path=None)
    assert callable(cond)


# --- PrettyFormatter -------------------------------------------------------


def test_pretty_formatter_handles_message():
    out = PrettyFormatter(Message("hi")).visit()
    assert out == "Message('hi')"


def test_pretty_formatter_handles_empty_wizard():
    out = PrettyFormatter(Wizard(children=[])).visit()
    assert out.startswith("Wizard(")
    assert "children=[" in out


def test_pretty_formatter_handles_input():
    out = PrettyFormatter(Input(prompt="? ")).visit()
    assert out.startswith("Input(prompt='? '")


def test_pretty_formatter_handles_question():
    q = Question("Q?", responses={"y": Pass()})
    out = PrettyFormatter(q).visit()
    assert "Question(" in out
    assert "'Q?'" in out


def test_pretty_formatter_handles_while():
    w = While(cond=lambda **kw: False, body=[Pass()])
    out = PrettyFormatter(w).visit()
    assert "While(" in out
    assert "body=[" in out


def test_node_str_uses_pretty_formatter():
    """``Node.__str__`` runs through PrettyFormatter."""
    assert str(Message("hi")) == "Message('hi')"


def test_node_repr_strips_newlines():
    """``Node.__repr__`` collapses the multi-line ``__str__`` to one line."""
    rep = repr(Wizard(children=[Pass()]))
    assert "\n" not in rep
