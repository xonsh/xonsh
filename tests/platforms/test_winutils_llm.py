"""Tests for :mod:`xonsh.platforms.winutils`.

The console-history wrappers (``CONSOLE_HISTORY_INFO`` and friends) are defined
with ``ctypes`` lazy objects, so the structure layout and the public Python
signatures can be checked on any platform; only the round-trip against a live
console is Windows-only.
"""

import ctypes
import inspect

import pytest

from xonsh.environ import WindowsSetting
from xonsh.platforms import winutils
from xonsh.pytest.tools import skip_if_on_unix


@skip_if_on_unix
def test_console_history_info_struct_size():
    # On Windows DWORD/UINT are both 4 bytes, so cbSize + HistoryBufferSize +
    # NumberOfHistoryBuffers + dwFlags == 16. SetConsoleHistoryInfo rejects a
    # wrong cbSize, so this layout must hold on the platform that uses it.
    # (On LP64 unixes wintypes.DWORD is 8 bytes, so the check only applies here.)
    assert ctypes.sizeof(winutils.CONSOLE_HISTORY_INFO) == 16


def test_console_history_info_field_order():
    names = [name for name, _ in winutils.CONSOLE_HISTORY_INFO._fields_]
    assert names == [
        "cbSize",
        "HistoryBufferSize",
        "NumberOfHistoryBuffers",
        "dwFlags",
    ]


def test_history_no_dup_flag_value():
    assert winutils.HISTORY_NO_DUP == 0x1


def test_set_console_history_info_defaults():
    # The defaults are the values that restore child-REPL history; nbuf in
    # particular must match the env-var default so the automatic call and a
    # manual call agree.
    params = inspect.signature(winutils.set_console_history_info).parameters
    assert params["nbuf"].default == 32
    assert params["bufsize"].default == 512
    assert params["flags"].default == 0


def test_env_default_buffers():
    assert WindowsSetting.XONSH_WIN_CONSOLE_HISTORY_BUFFERS.default == 32


def test_env_default_resolves(xession):
    assert xession.env.get("XONSH_WIN_CONSOLE_HISTORY_BUFFERS") == 32


@skip_if_on_unix
def test_set_console_history_info_roundtrip():
    try:
        original = winutils.get_console_history_info()
    except OSError as exc:  # pragma: no cover - depends on CI console
        pytest.skip(f"process not attached to a console: {exc}")
    try:
        winutils.set_console_history_info(nbuf=24, bufsize=256, flags=0)
        info = winutils.get_console_history_info()
        assert info.NumberOfHistoryBuffers == 24
        assert info.HistoryBufferSize == 256
        assert info.dwFlags == 0
    finally:
        winutils.set_console_history_info(
            nbuf=original.NumberOfHistoryBuffers,
            bufsize=original.HistoryBufferSize,
            flags=original.dwFlags,
        )
