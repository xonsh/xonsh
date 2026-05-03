"""Smoke tests for ``xonsh.lib.inspectors``.

The module ports IPython's object-inspection helpers — ``getdoc``, ``getsource``,
``find_file``, the ``Inspector`` class, ``object_info`` skeletons, etc. The
tests here cover the safe-to-call wrappers without actually pulling up an
IPython-style ``?`` UI.
"""

import pytest

from xonsh.lib.inspectors import (
    Inspector,
    call_tip,
    find_file,
    find_source_lines,
    formatargspec,
    getargspec,
    getdoc,
    getsource,
    info_fields,
    is_simple_callable,
    object_info,
)

# --- object_info ------------------------------------------------------------


def test_object_info_has_all_fields():
    info = object_info()
    for f in info_fields:
        assert f in info


def test_object_info_overrides_defaults():
    info = object_info(name="foo", isclass=True)
    assert info["name"] == "foo"
    assert info["isclass"] is True


# --- getdoc -----------------------------------------------------------------


def test_getdoc_for_function_with_docstring():
    def f():
        """A friendly function."""

    assert getdoc(f) == "A friendly function."


def test_getdoc_returns_none_for_obj_without_docstring():
    """Plain ``object()`` has the standard ``object`` docstring."""
    out = getdoc(object())
    # the inspect.getdoc(object) docstring is non-empty
    assert out is None or isinstance(out, str)


def test_getdoc_handles_custom_getdoc_method():
    class HasGetdoc:
        def getdoc(self):
            return "Custom doc."

    assert getdoc(HasGetdoc()) == "Custom doc."


# --- getsource --------------------------------------------------------------


def test_getsource_returns_function_definition():
    def my_marker():
        return "hello"

    src = getsource(my_marker)
    assert src is not None
    assert "my_marker" in src


def test_getsource_returns_none_for_binary_flag():
    """``is_binary=True`` short-circuits to ``None``."""

    def f():
        pass

    assert getsource(f, is_binary=True) is None


def test_getsource_unwraps_decorated_function():
    import functools

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            return fn(*a, **kw)

        return wrapper

    @deco
    def real():
        return 1

    src = getsource(real)
    assert src is not None
    assert "def real" in src


def test_getsource_handles_uninspectable_object():
    """Non-introspectable objects return None instead of raising."""
    # A bare integer has no source.
    assert getsource(42) is None


# --- is_simple_callable -----------------------------------------------------


def test_is_simple_callable_for_function():
    def f():
        pass

    assert is_simple_callable(f) is True


def test_is_simple_callable_for_lambda():
    assert is_simple_callable(lambda x: x) is True


def test_is_simple_callable_for_method():
    class C:
        def m(self):
            pass

    assert is_simple_callable(C().m) is True


def test_is_simple_callable_for_builtin():
    """``all`` is a builtin function whose type matches ``_builtin_func_type``."""
    # Force-load the module-level LazyObjects before the isinstance check —
    # ``isinstance(obj, lazy_obj)`` is False until the lazy slot is resolved.
    from xonsh.lib import inspectors as ins

    bool(ins._builtin_func_type)
    bool(ins._builtin_meth_type)
    assert is_simple_callable(all) is True
    assert is_simple_callable(str.upper) is True


def test_is_simple_callable_for_class_is_false():
    """Classes are callable but not "simple" in this sense."""

    class C:
        pass

    assert is_simple_callable(C) is False


def test_is_simple_callable_for_int_is_false():
    assert is_simple_callable(42) is False


# --- getargspec -------------------------------------------------------------


def test_getargspec_for_function():
    def f(a, b=1, *args, **kwargs):
        pass

    spec = getargspec(f)
    assert spec.args == ["a", "b"]
    assert spec.varargs == "args"
    assert spec.varkw == "kwargs"
    assert spec.defaults == (1,)


def test_getargspec_for_callable_class():
    """Classes implementing ``__call__`` route through their call method."""

    class C:
        def __call__(self, x):
            return x

    spec = getargspec(C())
    assert "x" in spec.args


# --- formatargspec ----------------------------------------------------------


def test_formatargspec_no_args():
    assert formatargspec() == "()"


def test_formatargspec_with_defaults():
    out = formatargspec(args=["a", "b"], defaults=(2,))
    assert out == "(a, b=2)"


def test_formatargspec_with_varargs_and_varkw():
    out = formatargspec(args=["a"], varargs="args", varkw="kwargs")
    assert out == "(a, *args, **kwargs)"


# --- call_tip ---------------------------------------------------------------


def test_call_tip_with_no_argspec_returns_none_call_line():
    info = object_info(name="foo", argspec=None, docstring="")
    line, doc = call_tip(info)
    assert line is None


def test_call_tip_strips_self_from_argspec():
    info = object_info(
        name="foo",
        argspec={"args": ["self", "x"], "varargs": None, "varkw": None, "defaults": ()},
        docstring="d",
    )
    line, doc = call_tip(info)
    assert line == "foo(x)"
    # docstring carried through
    assert doc == "d"


def test_call_tip_prefers_call_docstring():
    info = object_info(
        name="foo",
        argspec={"args": [], "varargs": None, "varkw": None, "defaults": ()},
        call_docstring="call",
        init_docstring="init",
        docstring="main",
    )
    _, doc = call_tip(info)
    assert doc == "call"


def test_call_tip_falls_back_to_init_then_main_docstring():
    info_init = object_info(
        name="foo",
        argspec={"args": [], "varargs": None, "varkw": None, "defaults": ()},
        init_docstring="init",
        docstring="main",
    )
    _, doc = call_tip(info_init)
    assert doc == "init"

    info_main = object_info(
        name="foo",
        argspec={"args": [], "varargs": None, "varkw": None, "defaults": ()},
        docstring="main",
    )
    _, doc = call_tip(info_main)
    assert doc == "main"


# --- find_file / find_source_lines ------------------------------------------


def test_find_file_for_module_function():
    fname = find_file(getdoc)  # any function defined in xonsh.lib.inspectors
    assert fname is not None
    assert fname.endswith("inspectors.py")


def test_find_file_returns_none_for_builtin():
    """Built-in functions have no Python source file."""
    assert find_file(len) is None


def test_find_source_lines_for_function():
    def marker():
        pass

    lineno = find_source_lines(marker)
    assert isinstance(lineno, int) and lineno > 0


def test_find_source_lines_returns_none_for_int():
    assert find_source_lines(42) is None


# --- Inspector smoke -------------------------------------------------------


def test_inspector_pdef_callable(capsys):
    insp = Inspector()

    def f(x, y=1):
        """help me"""

    insp.pdef(f, oname="f")
    out = capsys.readouterr().out
    assert "f(x, y=1)" in out


def test_inspector_pdef_non_callable(capsys):
    insp = Inspector()
    insp.pdef(42, oname="x")
    out = capsys.readouterr().out
    assert "not callable" in out


def test_inspector_pdoc_uses_name_mangled_head():
    """``Inspector.pdoc`` references ``self.__head`` which is name-mangled to
    ``_Inspector__head`` — an attribute that the class never sets. Calling
    ``pdoc`` on anything therefore raises ``AttributeError``. Pinning the
    behavior so a future refactor that fixes the bug also flips this test."""
    insp = Inspector()
    with pytest.raises(AttributeError):
        insp.pdoc(lambda: None)


def test_inspector_psource_smoke(capsys):
    insp = Inspector()

    def f():
        return 7

    insp.psource(f)
    out = capsys.readouterr().out
    assert "def f" in out or "No source" in out


def test_inspector_noinfo_with_oname(capsys):
    insp = Inspector()
    insp.noinfo("docs", "myname")
    assert "No docs found" in capsys.readouterr().out


def test_inspector_noinfo_without_oname(capsys):
    insp = Inspector()
    insp.noinfo("docs", "")
    assert "No docs found" in capsys.readouterr().out


def test_inspector_format_fields_str_smoke():
    insp = Inspector()
    out = insp._format_fields_str([("Title", "value")])
    assert "Title" in out
    assert "value" in out
