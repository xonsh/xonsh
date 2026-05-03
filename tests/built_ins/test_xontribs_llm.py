"""Tests for ``xonsh.xontribs.find_xontrib`` lookup pipeline.

Regression coverage for the ``--no-rc`` / ``$XONTRIBS_AUTOLOAD_DISABLED``
case: a xontrib whose only Python-visible mapping is a setuptools
entry point in the ``xonsh.xontribs`` group (the wheel ships **no**
``xontrib/<name>.py`` and no top-level ``<name>._load_xontrib_``) used
to be unreachable from ``xontrib load <name>`` whenever autoload had
not populated ``XSH.builtins.autoloaded_xontribs``.  The canonical
example is the ``coconut`` xontrib whose loader lives in
``coconut.integrations``.

These tests pin the corrected lookup order without depending on
coconut: a fake entry point is monkeypatched into
``_get_xontrib_entrypoints`` and points at a temp module on
``sys.path``.
"""

import sys

import pytest

from xonsh import xontribs
from xonsh.xontribs import find_xontrib, xontribs_load


@pytest.fixture
def tmpmod(tmpdir):
    """Fresh ``sys.path`` entry + module-cache cleanup, mirroring the
    fixture in ``test_xontribs.py`` so tests don't leak modules."""
    sys.path.insert(0, str(tmpdir))
    loadedmods = set(sys.modules.keys())
    try:
        yield tmpdir
    finally:
        del sys.path[0]
        newmods = set(sys.modules.keys()) - loadedmods
        for m in newmods:
            del sys.modules[m]


class _FakeEntry:
    """Minimal stand-in for ``importlib.metadata.EntryPoint``.  Only
    the attributes ``find_xontrib``/``xontribs_load`` actually read
    are populated.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.dist = None


def _patch_entries(monkeypatch, entries):
    """Replace the live entry-point iterator with ``entries``."""
    monkeypatch.setattr(xontribs, "_get_xontrib_entrypoints", lambda: iter(entries))


def test_find_xontrib_via_entry_point_without_autoload(tmpmod, monkeypatch):
    """``find_xontrib`` must consult the entry-point registry, not just
    the ``autoloaded_xontribs`` cache.  Mirrors the ``--no-rc`` /
    ``$XONTRIBS_AUTOLOAD_DISABLED`` path where the cache is empty.
    """
    # Module the entry point points at — anywhere on sys.path is fine
    # provided the dotted name resolves.
    tmpmod.mkdir("ep_pkg").join("loader.py").write(
        "def _load_xontrib_(xsh): return {'flag': 1}\n"
    )
    tmpmod.join("ep_pkg").join("__init__.py").write("")
    _patch_entries(monkeypatch, [_FakeEntry("ep_pkg_xontrib", "ep_pkg.loader")])
    spec = find_xontrib("ep_pkg_xontrib")
    assert spec is not None, "entry-point lookup must succeed"
    assert spec.name == "ep_pkg.loader"


def test_find_xontrib_autoloaded_takes_priority(tmpmod, monkeypatch):
    """When the same name is both in ``autoloaded_xontribs`` and the
    entry-point list, the cached value wins (the cache is the primary
    path during interactive sessions).
    """
    tmpmod.mkdir("auto_pkg").join("__init__.py").write("")
    tmpmod.join("auto_pkg").join("real.py").write(
        "def _load_xontrib_(xsh): return {}\n"
    )
    tmpmod.mkdir("ep_pkg").join("__init__.py").write("")
    tmpmod.join("ep_pkg").join("other.py").write("def _load_xontrib_(xsh): return {}\n")
    monkeypatch.setattr(
        xontribs.XSH.builtins,
        "autoloaded_xontribs",
        {"shared_name": "auto_pkg.real"},
        raising=False,
    )
    _patch_entries(monkeypatch, [_FakeEntry("shared_name", "ep_pkg.other")])
    spec = find_xontrib("shared_name")
    assert spec.name == "auto_pkg.real"


def test_find_xontrib_falls_through_namespace_to_toplevel(tmpmod, monkeypatch):
    """Pre-fix ``with contextlib.suppress(ValueError): return …`` returned
    ``None`` from the namespace step and never reached the top-level
    fallback.  Verify the corrected pass-through.
    """
    # No entry point and no ``xontrib.never_in_xontrib_ns`` submodule —
    # but a top-level ``never_in_xontrib_ns`` module does exist.
    tmpmod.join("never_in_xontrib_ns.py").write(
        "def _load_xontrib_(xsh): return {'top_level': True}\n"
    )
    _patch_entries(monkeypatch, [])
    monkeypatch.setattr(xontribs.XSH.builtins, "autoloaded_xontribs", {}, raising=False)
    spec = find_xontrib("never_in_xontrib_ns")
    assert spec is not None
    assert spec.name == "never_in_xontrib_ns"


def test_find_xontrib_namespace_package_still_wins(tmpmod, monkeypatch):
    """A name available as ``xontrib.<name>`` (legacy layout) must still
    resolve to that namespace submodule, taking priority over a
    same-named top-level module.
    """
    tmpmod.mkdir("xontrib").join("ns_only.py").write(
        "def _load_xontrib_(xsh): return {'ns': True}\n"
    )
    tmpmod.join("ns_only.py").write("def _load_xontrib_(xsh): return {'top': True}\n")
    _patch_entries(monkeypatch, [])
    monkeypatch.setattr(xontribs.XSH.builtins, "autoloaded_xontribs", {}, raising=False)
    spec = find_xontrib("ns_only")
    assert spec is not None
    assert spec.name == "xontrib.ns_only"


def test_find_xontrib_missing_returns_none(tmpmod, monkeypatch):
    """A name that exists nowhere must still surface as ``None`` so the
    ``XontribNotInstalled`` warning fires correctly.
    """
    _patch_entries(monkeypatch, [])
    monkeypatch.setattr(xontribs.XSH.builtins, "autoloaded_xontribs", {}, raising=False)
    assert find_xontrib("absolutely_no_such_xontrib_xyz") is None


def test_xontribs_load_via_entry_point_without_autoload(tmpmod, monkeypatch):
    """End-to-end: ``xontrib load <name>`` succeeds even when autoload
    did not run, provided the name has an entry point.  This is the
    exact symptom from the GH-6386 follow-up: ``xonsh --no-rc`` +
    ``xontrib load coconut`` used to fail with «not installed» despite
    coconut being correctly installed.
    """
    tmpmod.mkdir("ext_pkg").join("__init__.py").write("")
    tmpmod.join("ext_pkg").join("xontrib_loader.py").write(
        "def _load_xontrib_(xsh):\n"
        "    xsh.ctx['ext_pkg_loaded'] = True\n"
        "    return {'ext_pkg_loaded': True}\n"
    )
    _patch_entries(monkeypatch, [_FakeEntry("ext_xontrib", "ext_pkg.xontrib_loader")])
    monkeypatch.setattr(xontribs.XSH.builtins, "autoloaded_xontribs", {}, raising=False)
    stdout, stderr, rc = xontribs_load(["ext_xontrib"])
    assert rc == xontribs.ExitCode.OK
    assert stderr is None, f"unexpected stderr: {stderr!r}"
    assert "ext_pkg.xontrib_loader" in sys.modules
