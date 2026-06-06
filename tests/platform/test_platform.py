import builtins
import os
from unittest.mock import mock_open

import pytest

import xonsh.platform as xp


def test_githash_value_error(monkeypatch):
    mocked_open = mock_open(read_data="abc123")
    monkeypatch.setattr(builtins, "open", mocked_open)

    xp.githash.cache_clear()  # githash has lru_cache
    sha, date_ = xp.githash()
    assert date_ is None
    assert sha is None


def test_pathsplit_empty_path():
    assert xp.pathsplit("") == ("", "")


def test_path_default_non_empty_on_supported_platforms():
    """``PATH_DEFAULT`` must not be empty on any platform xonsh ships
    binaries to find. An empty default leaves :class:`xonsh.environ.Env`
    with no PATH when ``UPDATE_OS_ENVIRON`` is off (test sessions, embedded
    use), so ``commands_cache`` finds nothing and every ``subprocess.Popen``
    invocation built from ``XSH.env.detype()`` raises ``FileNotFoundError``.
    """
    if not (xp.ON_LINUX or xp.ON_DARWIN or xp.ON_BSD or xp.ON_WINDOWS):
        pytest.skip("PATH_DEFAULT is intentionally empty on this platform")
    assert tuple(xp.PATH_DEFAULT)


def test_path_bshell_posix_default(monkeypatch):
    monkeypatch.setattr(xp, "ON_TERMUX", False)
    monkeypatch.setattr(xp, "ON_ANDROID", False)
    monkeypatch.setattr(os, "access", lambda p, m: p == "/bin/sh")
    assert xp.path_bshell() == "/bin/sh"


def test_path_bshell_termux(monkeypatch, tmp_path):
    sh = tmp_path / "usr" / "bin" / "sh"
    sh.parent.mkdir(parents=True)
    sh.touch()
    sh.chmod(0o755)
    monkeypatch.setattr(xp, "ON_TERMUX", True)
    monkeypatch.setattr(xp, "ON_ANDROID", True)
    monkeypatch.setenv("PREFIX", str(tmp_path / "usr"))
    assert xp.path_bshell() == str(sh)


def test_path_bshell_android_stock(monkeypatch):
    monkeypatch.setattr(xp, "ON_TERMUX", False)
    monkeypatch.setattr(xp, "ON_ANDROID", True)
    monkeypatch.setattr(os, "access", lambda p, m: p == "/system/bin/sh")
    assert xp.path_bshell() == "/system/bin/sh"


def test_path_bshell_android_proot_prefers_fhs(monkeypatch):
    # FHS userland on top of Android (proot-distro, UserLAnd, ...): its
    # own /bin/sh wins over the bionic /system/bin/sh.
    monkeypatch.setattr(xp, "ON_TERMUX", False)
    monkeypatch.setattr(xp, "ON_ANDROID", True)
    monkeypatch.setattr(os, "access", lambda p, m: p in ("/bin/sh", "/system/bin/sh"))
    assert xp.path_bshell() == "/bin/sh"


def test_path_bshell_path_fallback(monkeypatch):
    # No candidate exists: fall back to ``sh`` from $PATH.
    monkeypatch.setattr(xp, "ON_TERMUX", False)
    monkeypatch.setattr(xp, "ON_ANDROID", False)
    monkeypatch.setattr(os, "access", lambda p, m: False)
    monkeypatch.setattr(
        xp.shutil, "which", lambda cmd: "/opt/bin/sh" if cmd == "sh" else None
    )
    assert xp.path_bshell() == "/opt/bin/sh"


def test_path_bshell_last_resort(monkeypatch):
    monkeypatch.setattr(xp, "ON_TERMUX", False)
    monkeypatch.setattr(xp, "ON_ANDROID", False)
    monkeypatch.setattr(os, "access", lambda p, m: False)
    monkeypatch.setattr(xp.shutil, "which", lambda cmd: None)
    assert xp.path_bshell() == "/bin/sh"


def test_path_default_freebsd_covers_system_and_ports():
    """FreeBSD's PATH must include both the base-system bin/sbin and the
    ports/pkg ``/usr/local`` prefix. Without ``/usr/local/{s,}bin`` xonsh
    can't see anything installed via pkg (git, bash, etc.), which broke
    every subprocess-based test in the suite when running on FreeBSD."""
    if not xp.ON_FREEBSD:
        pytest.skip("FreeBSD-only assertion")
    paths = tuple(xp.PATH_DEFAULT)
    for required in (
        "/sbin",
        "/bin",
        "/usr/sbin",
        "/usr/bin",
        "/usr/local/sbin",
        "/usr/local/bin",
    ):
        assert required in paths
