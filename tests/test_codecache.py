"""Tests for xonsh code caching."""

import marshal
import os

import pytest

from xonsh import __version__ as XONSH_VERSION
from xonsh.codecache import (
    _check_cache_versions,
    _splitpath,
    code_cache_check,
    code_cache_name,
    compile_code,
    get_cache_filename,
    run_code_with_cache,
    run_compiled_code,
    run_script_with_cache,
    script_cache_check,
    should_use_cache,
    update_cache,
)
from xonsh.platform import PYTHON_VERSION_INFO_BYTES


@pytest.fixture(autouse=True)
def cache_env(xession, tmp_path):
    xession.env.update(
        {
            "XONSH_DATA_DIR": str(tmp_path),
            "XONSH_CACHE_SCRIPTS": True,
            "XONSH_CACHE_EVERYTHING": False,
            "XONSH_DEBUG": False,
        }
    )
    yield xession


def test_splitpath_simple():
    assert _splitpath(os.path.join("a", "b", "c")) == ("a", "b", "c")


def test_splitpath_absolute(tmp_path):
    parts = _splitpath(str(tmp_path / "a" / "b"))
    assert "a" in parts
    assert parts[-1] == "b"


def test_splitpath_single():
    assert _splitpath("file.py") == ("file.py",)


def test_should_use_cache_exec_mode(cache_env):
    execer = cache_env.execer
    execer.scriptcache = True
    cache_env.env["XONSH_CACHE_SCRIPTS"] = True
    assert should_use_cache(execer, "exec") is True


def test_should_use_cache_exec_mode_no_execer_flag(cache_env):
    execer = cache_env.execer
    execer.scriptcache = False
    execer.cacheall = False
    cache_env.env["XONSH_CACHE_SCRIPTS"] = True
    assert should_use_cache(execer, "exec") is False


def test_should_use_cache_exec_mode_env_disabled(cache_env):
    execer = cache_env.execer
    execer.scriptcache = True
    cache_env.env["XONSH_CACHE_SCRIPTS"] = False
    cache_env.env["XONSH_CACHE_EVERYTHING"] = False
    assert should_use_cache(execer, "exec") is False


def test_should_use_cache_single_mode_cacheall(cache_env):
    execer = cache_env.execer
    execer.cacheall = True
    assert should_use_cache(execer, "single") is True


def test_should_use_cache_single_mode_no_cacheall(cache_env):
    execer = cache_env.execer
    execer.cacheall = False
    cache_env.env["XONSH_CACHE_EVERYTHING"] = False
    assert should_use_cache(execer, "single") is False


def test_should_use_cache_everything_overrides(cache_env):
    execer = cache_env.execer
    execer.cacheall = False
    cache_env.env["XONSH_CACHE_EVERYTHING"] = True
    assert should_use_cache(execer, "single") is True


def test_run_compiled_code_exec():
    code = compile("x = 42", "<test>", "exec")
    glb = {}
    result = run_compiled_code(code, glb, None, "exec")
    assert result == (None, None, None)
    assert glb["x"] == 42


def test_run_compiled_code_eval():
    code = compile("1 + 2", "<test>", "eval")
    result = run_compiled_code(code, {}, None, "eval")
    assert result == (None, None, None)


def test_run_compiled_code_none():
    assert run_compiled_code(None, {}, None, "exec") is None


def test_run_compiled_code_exception():
    code = compile("1/0", "<test>", "exec")
    exc_type, exc_val, exc_tb = run_compiled_code(code, {}, None, "exec")
    assert exc_type is ZeroDivisionError


def test_get_cache_filename_code(cache_env):
    fname = get_cache_filename("abc123", code=True)
    assert "xonsh_code_cache" in fname


def test_get_cache_filename_script(cache_env):
    fname = get_cache_filename("/some/script.xsh", code=False)
    assert "xonsh_script_cache" in fname


def test_update_cache_roundtrip(cache_env, tmp_path):
    code = compile("x = 1", "<test>", "exec")
    cache_file = os.path.join(str(tmp_path), "test_cache", "test.cache")
    update_cache(code, cache_file)
    assert os.path.isfile(cache_file)

    with open(cache_file, "rb") as f:
        assert _check_cache_versions(f) is True
        loaded = marshal.load(f)
    assert loaded == code


def test_update_cache_none_file():
    update_cache(compile("x=1", "<t>", "exec"), None)


def test_check_cache_versions_xonsh_mismatch(tmp_path):
    cache_file = os.path.join(str(tmp_path), "bad.cache")
    with open(cache_file, "wb") as f:
        f.write(b"0.0.0\n")
        f.write(bytes(PYTHON_VERSION_INFO_BYTES) + b"\n")
        marshal.dump(compile("x=1", "<t>", "exec"), f)

    with open(cache_file, "rb") as f:
        assert _check_cache_versions(f) is False


def test_check_cache_versions_python_mismatch(tmp_path):
    cache_file = os.path.join(str(tmp_path), "bad2.cache")
    with open(cache_file, "wb") as f:
        f.write(XONSH_VERSION.encode() + b"\n")
        f.write(b"99.99\n")
        marshal.dump(compile("x=1", "<t>", "exec"), f)

    with open(cache_file, "rb") as f:
        assert _check_cache_versions(f) is False


def test_compile_code_py_file(cache_env):
    code = compile_code("test.py", "x = 1\n", cache_env.execer, {}, {}, "exec")
    glb = {}
    exec(code, glb)
    assert glb["x"] == 1


def test_compile_code_xsh_file(cache_env):
    code = compile_code("test.xsh", "x = 1\n", cache_env.execer, {}, {}, "exec")
    glb = {}
    exec(code, glb)
    assert glb["x"] == 1


def test_compile_code_adds_trailing_newline(cache_env):
    code = compile_code("test.xsh", "x = 1", cache_env.execer, {}, {}, "exec")
    assert code is not None


def test_compile_code_restores_execer_filename(cache_env):
    execer = cache_env.execer
    execer.filename = "<original>"
    compile_code("test.xsh", "x = 1\n", execer, {}, {}, "exec")
    assert execer.filename == "<original>"


def test_script_cache_check_no_file(tmp_path):
    valid, code = script_cache_check(
        str(tmp_path / "file.xsh"), str(tmp_path / "nonexistent.cache")
    )
    assert valid is False
    assert code is None


def test_script_cache_check_valid(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "src.xsh")
    with open(src_file, "w") as f:
        f.write("x = 1\n")

    code = compile("x = 1\n", src_file, "exec")
    cache_file = os.path.join(str(tmp_path), "src.cache")
    update_cache(code, cache_file)

    valid, cached = script_cache_check(src_file, cache_file)
    assert valid is True
    assert cached == code


def test_script_cache_check_stale(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "src.xsh")
    cache_file = os.path.join(str(tmp_path), "src.cache")

    code = compile("x = 1\n", src_file, "exec")
    update_cache(code, cache_file)

    with open(src_file, "w") as f:
        f.write("x = 2\n")
    # Ensure source is newer than cache
    future = os.stat(cache_file).st_mtime + 2
    os.utime(src_file, (future, future))

    valid, cached = script_cache_check(src_file, cache_file)
    assert valid is False
    assert cached is None


def test_code_cache_name_str():
    name = code_cache_name("x = 1")
    assert isinstance(name, str)
    assert len(name) == 32  # md5 hex


def test_code_cache_name_bytes():
    assert isinstance(code_cache_name(b"x = 1"), str)


def test_code_cache_name_deterministic():
    assert code_cache_name("x = 1") == code_cache_name("x = 1")


def test_code_cache_name_unique():
    assert code_cache_name("x = 1") != code_cache_name("x = 2")


def test_code_cache_check_no_file(tmp_path):
    valid, code = code_cache_check(str(tmp_path / "nonexistent.cache"))
    assert valid is False
    assert code is None


def test_code_cache_check_valid(cache_env, tmp_path):
    code = compile("x = 1\n", "<test>", "exec")
    cache_file = os.path.join(str(tmp_path), "code.cache")
    update_cache(code, cache_file)

    valid, cached = code_cache_check(cache_file)
    assert valid is True
    assert cached == code


def test_run_script_with_cache(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "test.py")
    with open(src_file, "w") as f:
        f.write("x = 42\n")

    glb = {}
    result = run_script_with_cache(src_file, cache_env.execer, glb)
    assert result == (None, None, None)
    assert glb["x"] == 42


def test_run_script_with_cache_creates_file_py(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "cached.py")
    with open(src_file, "w") as f:
        f.write("y = 99\n")

    execer = cache_env.execer
    execer.scriptcache = True
    cache_env.env["XONSH_CACHE_SCRIPTS"] = True

    glb = {}
    run_script_with_cache(src_file, execer, glb)
    assert glb["y"] == 99

    cachefname = get_cache_filename(src_file, code=False)
    assert os.path.isfile(cachefname)


def test_run_script_with_cache_creates_file_xsh(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "cached.xsh")
    with open(src_file, "w") as f:
        f.write("y = 99\n")

    execer = cache_env.execer
    execer.scriptcache = True
    cache_env.env["XONSH_CACHE_SCRIPTS"] = True

    glb = {}
    run_script_with_cache(src_file, execer, glb)
    assert glb["y"] == 99

    cachefname = get_cache_filename(src_file, code=False)
    assert os.path.isfile(cachefname)


def test_run_script_with_cache_second_run(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "twice.py")
    with open(src_file, "w") as f:
        f.write("z = 10\n")

    execer = cache_env.execer
    execer.scriptcache = True
    cache_env.env["XONSH_CACHE_SCRIPTS"] = True

    glb1 = {}
    run_script_with_cache(src_file, execer, glb1)
    assert glb1["z"] == 10

    glb2 = {}
    run_script_with_cache(src_file, execer, glb2)
    assert glb2["z"] == 10


def test_run_script_with_cache_disabled(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "nocache.py")
    with open(src_file, "w") as f:
        f.write("a = 5\n")

    execer = cache_env.execer
    execer.scriptcache = False
    execer.cacheall = False
    cache_env.env["XONSH_CACHE_SCRIPTS"] = False

    glb = {}
    run_script_with_cache(src_file, execer, glb)
    assert glb["a"] == 5

    cachefname = get_cache_filename(src_file, code=False)
    assert not os.path.isfile(cachefname)


def test_run_script_with_cache_exception(cache_env, tmp_path):
    src_file = os.path.join(str(tmp_path), "err.py")
    with open(src_file, "w") as f:
        f.write("1/0\n")

    exc_type, exc_val, exc_tb = run_script_with_cache(
        src_file, cache_env.execer, {}
    )
    assert exc_type is ZeroDivisionError


def test_run_code_with_cache(cache_env):
    glb = {}
    result = run_code_with_cache("x = 7\n", "<test>", cache_env.execer, glb)
    assert result == (None, None, None)
    assert glb["x"] == 7


def test_run_code_with_cache_creates_file(cache_env, tmp_path):
    execer = cache_env.execer
    execer.cacheall = True
    cache_env.env["XONSH_CACHE_EVERYTHING"] = True

    code_str = "cached_val = 123\n"

    glb = {}
    run_code_with_cache(code_str, "<test>", execer, glb)
    assert glb["cached_val"] == 123

    fname = code_cache_name(code_str)
    cachefname = get_cache_filename(fname, code=True)
    assert os.path.isfile(cachefname)


def test_run_code_with_cache_second_run(cache_env, tmp_path):
    execer = cache_env.execer
    execer.cacheall = True
    cache_env.env["XONSH_CACHE_EVERYTHING"] = True

    code_str = "reused = 77\n"

    glb1 = {}
    run_code_with_cache(code_str, "<test>", execer, glb1)

    glb2 = {}
    run_code_with_cache(code_str, "<test>", execer, glb2)
    assert glb2["reused"] == 77


def test_run_code_with_cache_exception(cache_env):
    exc_type, exc_val, exc_tb = run_code_with_cache(
        "1/0\n", "<test>", cache_env.execer, {}
    )
    assert exc_type is ZeroDivisionError
