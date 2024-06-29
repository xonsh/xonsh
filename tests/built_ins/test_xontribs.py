"""xontrib tests, such as they are"""

import sys

import pytest

from xonsh.xontribs import (
    xontrib_context,
    xontribs_load,
    xontribs_loaded,
    xontribs_main,
    xontribs_reload,
    xontribs_unload,
)


@pytest.fixture
def tmpmod(tmpdir):
    """
    Same as tmpdir but also adds/removes it to the front of sys.path.

    Also cleans out any modules loaded as part of the test.
    """
    sys.path.insert(0, str(tmpdir))
    loadedmods = set(sys.modules.keys())
    try:
        yield tmpdir
    finally:
        del sys.path[0]
        newmods = set(sys.modules.keys()) - loadedmods
        for m in newmods:
            del sys.modules[m]


def test_noall(tmpmod):
    """
    Tests what get's exported from a module without __all__
    """

    with tmpmod.mkdir("xontrib").join("spameggs.py").open("w") as x:
        x.write(
            """
spam = 1
eggs = 2
_foobar = 3
"""
        )

    ctx = xontrib_context("spameggs")
    assert ctx == {"spam": 1, "eggs": 2}


def test_withall(tmpmod):
    """
    Tests what get's exported from a module with __all__
    """

    with tmpmod.mkdir("xontrib").join("spameggs.py").open("w") as x:
        x.write(
            """
__all__ = 'spam', '_foobar'
spam = 1
eggs = 2
_foobar = 3
"""
        )

    ctx = xontrib_context("spameggs")
    assert ctx == {"spam": 1, "_foobar": 3}


def test_xshxontrib(tmpmod):
    """
    Test that .xsh xontribs are loadable
    """
    with tmpmod.mkdir("xontrib").join("script.xsh").open("w") as x:
        x.write(
            """
hello = 'world'
"""
        )

    ctx = xontrib_context("script")
    assert ctx == {"hello": "world"}


def test_xontrib_load(tmpmod):
    """
    Test that .xsh xontribs are loadable
    """
    with tmpmod.mkdir("xontrib").join("script.xsh").open("w") as x:
        x.write(
            """
hello = 'world'
"""
        )

    xontribs_load(["script"])
    assert "script" in xontribs_loaded()


def test_xontrib_unload(tmpmod, xession):
    with tmpmod.mkdir("xontrib").join("script.py").open("w") as x:
        x.write(
            """
hello = 'world'

def _unload_xontrib_(xsh): del xsh.ctx['hello']
"""
        )

    xontribs_load(["script"])
    assert "script" in xontribs_loaded()
    assert "hello" in xession.ctx
    xontribs_unload(["script"])
    assert "script" not in xontribs_loaded()
    assert "hello" not in xession.ctx


def test_xontrib_reload(tmpmod, xession):
    with tmpmod.mkdir("xontrib").join("script.py").open("w") as x:
        x.write(
            """
hello = 'world'

def _unload_xontrib_(xsh): del xsh.ctx['hello']
"""
        )

    xontribs_load(["script"])
    assert "script" in xontribs_loaded()
    assert xession.ctx["hello"] == "world"

    with tmpmod.join("xontrib").join("script.py").open("w") as x:
        x.write(
            """
hello = 'world1'

def _unload_xontrib_(xsh): del xsh.ctx['hello']
"""
        )
    xontribs_reload(["script"])
    assert "script" in xontribs_loaded()
    assert xession.ctx["hello"] == "world1"


def test_xontrib_load_dashed(tmpmod):
    """
    Test that .xsh xontribs are loadable
    """
    with tmpmod.mkdir("xontrib").join("scri-pt.xsh").open("w") as x:
        x.write(
            """
hello = 'world'
"""
        )

    xontribs_load(["scri-pt"])
    assert "scri-pt" in xontribs_loaded()


def test_xontrib_list(xession, capsys):
    xontribs_main(["list"])
    out, err = capsys.readouterr()
    assert "coreutils" in out
