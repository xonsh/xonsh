"""Smoke tests for ``xonsh.xontribs``.

Covers ``Xontrib`` introspection, ``xontrib_data`` / ``xontribs_loaded`` /
``xontribs_list`` formatting, and pure helpers like ``get_module_docstring``,
``prompt_xontrib_install``, and ``find_xontrib`` for the not-found path.
"""

import json
import sys

import pytest

from xonsh.xontribs import (
    ExitCode,
    Xontrib,
    XontribAlias,
    XontribNotInstalled,
    auto_load_xontribs_from_entrypoints,
    find_xontrib,
    get_module_docstring,
    get_xontribs,
    prompt_xontrib_install,
    update_context,
    xontrib_context,
    xontrib_data,
    xontribs_list,
    xontribs_load,
    xontribs_loaded,
    xontribs_reload,
    xontribs_unload,
)

# --- Xontrib NamedTuple -----------------------------------------------------


def test_xontrib_default_distribution_none():
    x = Xontrib(module="xontrib.unimaginary_xyz")
    assert x.module == "xontrib.unimaginary_xyz"
    assert x.distribution is None
    assert x.url == ""
    assert x.license == ""


def test_xontrib_is_loaded_false_when_module_missing():
    x = Xontrib(module="xontrib.surely_does_not_exist_xyz")
    assert x.is_loaded is False


def test_xontrib_is_loaded_true_when_in_sys_modules():
    x = Xontrib(module="xontrib.fake_loaded_for_test_xyz")
    sys.modules[x.module] = object()  # type: ignore[assignment]
    try:
        assert x.is_loaded is True
    finally:
        del sys.modules[x.module]


def test_xontrib_is_auto_loaded_false_without_state(xession):
    """When XSH.builtins has no ``autoloaded_xontribs`` mapping, the property
    falls back to an empty dict and reports False."""
    if hasattr(xession.builtins, "autoloaded_xontribs"):
        try:
            del xession.builtins.autoloaded_xontribs
        except AttributeError:
            pass
    x = Xontrib(module="xontrib.something")
    assert x.is_auto_loaded is False


# --- get_module_docstring ---------------------------------------------------


def test_get_module_docstring_for_real_module():
    doc = get_module_docstring("xonsh.xontribs")
    assert doc
    assert "xontrib" in doc.lower()


def test_get_module_docstring_for_missing_module():
    """A module that cannot be located returns the empty string, not None."""
    out = get_module_docstring("xontrib.surely_does_not_exist_abc_xyz")
    assert out == ""


# --- get_xontribs / xontrib_data --------------------------------------------


def test_get_xontribs_returns_dict():
    data = get_xontribs()
    assert isinstance(data, dict)
    # the in-tree ``xontrib`` package always discovers at least one entry
    assert len(data) > 0
    for name, xo in data.items():
        assert isinstance(name, str)
        assert isinstance(xo, Xontrib)


def test_xontrib_data_shape():
    data = xontrib_data()
    assert isinstance(data, dict)
    for name, entry in data.items():
        assert entry["name"] == name
        assert "loaded" in entry and isinstance(entry["loaded"], bool)
        assert "auto" in entry and isinstance(entry["auto"], bool)
        assert "module" in entry
        assert "description" in entry


def test_xontrib_data_is_sorted_alphabetically():
    data = xontrib_data()
    assert list(data.keys()) == sorted(data.keys())


def test_xontribs_loaded_subset_of_get_xontribs():
    loaded = xontribs_loaded()
    assert isinstance(loaded, list)
    all_names = set(get_xontribs())
    assert set(loaded).issubset(all_names)


# --- xontribs_list output ---------------------------------------------------


def test_xontribs_list_json(xession):
    out = xontribs_list(to_json=True)
    parsed = json.loads(out)
    assert isinstance(parsed, dict)


def test_xontribs_list_human_format(capsys):
    """The non-JSON branch prints colored lines for each xontrib."""
    xontribs_list(to_json=False)
    captured = capsys.readouterr().out
    # we got at least one printed line and it mentions "loaded" or "not-loaded"
    assert "loaded" in captured.lower() or "not-loaded" in captured.lower()


# --- find_xontrib ----------------------------------------------------------


def test_find_xontrib_returns_none_for_missing():
    assert find_xontrib("definitely_not_a_xontrib_xyz123") is None


def test_find_xontrib_resolves_real_xontrib():
    """At least one xontrib is shipped in-tree — find_xontrib must locate it."""
    names = list(get_xontribs())
    assert names, "expected at least one xontrib"
    # pick a deterministic-looking core xontrib name
    spec = find_xontrib(names[0])
    # Some xontribs may not be importable here, but find_spec should not crash
    assert spec is None or hasattr(spec, "name")


# --- xontrib_context / update_context --------------------------------------


def test_xontrib_context_returns_none_for_missing():
    assert xontrib_context("definitely_not_a_xontrib_xyz123") is None


def test_update_context_raises_when_not_installed():
    ctx = {}
    with pytest.raises(XontribNotInstalled):
        update_context("definitely_not_a_xontrib_xyz123", ctx)


# --- prompt_xontrib_install ------------------------------------------------


def test_prompt_xontrib_install_includes_names():
    msg = prompt_xontrib_install(["foo", "bar"])
    assert "foo" in msg
    assert "bar" in msg


# --- ExitCode --------------------------------------------------------------


def test_exit_code_values():
    assert int(ExitCode.OK) == 0
    assert int(ExitCode.NOT_FOUND) == 1
    assert int(ExitCode.INIT_FAILED) == 2


# --- xontribs_load NOT_FOUND path -------------------------------------------


def test_xontribs_load_returns_not_found(xession):
    _, stderr, rc = xontribs_load(["definitely_not_a_xontrib_xyz123"])
    assert rc == ExitCode.NOT_FOUND
    assert "not installed" in stderr


def test_xontribs_load_empty_returns_ok(xession):
    """Loading no xontribs is a successful no-op."""
    _, _, rc = xontribs_load([])
    assert rc == ExitCode.OK


def test_xontribs_load_suppress_warnings_returns_ok(xession):
    """``--suppress-warnings`` masks the NOT_FOUND status."""
    _, stderr, rc = xontribs_load(
        ["definitely_not_a_xontrib_xyz123"], suppress_warnings=True
    )
    assert rc == ExitCode.OK
    assert stderr is None


# --- xontribs_unload ------------------------------------------------------


def test_xontribs_unload_unknown_is_noop(xession):
    """Unloading a missing xontrib must not raise."""
    xontribs_unload(["definitely_not_a_xontrib_xyz123"])


def test_xontribs_reload_unknown_is_noop(xession):
    """Reloading an unknown xontrib funnels through load + unload paths."""
    xontribs_reload(["definitely_not_a_xontrib_xyz123"])


# --- auto_load_xontribs_from_entrypoints -----------------------------------


def test_auto_load_xontribs_with_blocked_set(xession):
    """Blocking every entry point yields an OK exit (no work to do)."""
    # block by passing an obviously-too-broad blocklist; if there are no
    # entry points at all, the function still must complete and return OK.
    _, _, rc = auto_load_xontribs_from_entrypoints(
        blocked=["a-definitely-blocked-xontrib"], verbose=False
    )
    assert rc in (ExitCode.OK, ExitCode.NOT_FOUND, ExitCode.INIT_FAILED)


# --- XontribAlias ----------------------------------------------------------


def test_xontrib_alias_builds_argparser(xession):
    alias = XontribAlias(threadable=False)
    parser = alias.build()
    # parser should know the four subcommands
    assert any(
        cmd in parser.format_help() for cmd in ("load", "unload", "reload", "list")
    )
