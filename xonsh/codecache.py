"""Tools for caching xonsh code."""

import hashlib
import marshal
import os
import sys

from xonsh import __version__ as XONSH_VERSION
from xonsh.built_ins import XSH
from xonsh.lib.lazyasd import lazyobject
from xonsh.platform import PYTHON_VERSION_INFO_BYTES
from xonsh.tools import is_writable_file, print_warning


def _splitpath(path, sofar=()):
    folder, path = os.path.split(path)
    if path == "":
        return sofar[::-1]
    elif folder == "":
        return (sofar + (path,))[::-1]
    else:
        return _splitpath(folder, sofar + (path,))


@lazyobject
def _CHARACTER_MAP():
    cmap = {chr(o): "_" + chr(o + 32) for o in range(65, 91)}
    cmap.update({".": "_.", "_": "__"})
    return cmap


def _cache_renamer(path, code=False):
    if not code:
        path = os.path.realpath(path)
    o = ["".join(_CHARACTER_MAP.get(i, i) for i in w) for w in _splitpath(path)]
    o[-1] = f"{o[-1]}.{sys.implementation.cache_tag}"
    return o


def should_use_cache(execer, mode):
    """
    Return ``True`` if caching has been enabled for this mode (through command
    line flags or environment variables)
    """
    if mode == "exec":
        return (execer.scriptcache or execer.cacheall) and (
            XSH.env["XONSH_CACHE_SCRIPTS"] or XSH.env["XONSH_CACHE_EVERYTHING"]
        )
    else:
        return execer.cacheall or XSH.env["XONSH_CACHE_EVERYTHING"]


def run_compiled_code(code, glb, loc, mode):
    """
    Helper to run code in a given mode and context.
    Returns a sys.exc_info() triplet in case the code raises an exception, or (None, None, None) otherwise.
    """
    if code is None:
        return
    if mode in {"exec", "single"}:
        func = exec
    else:
        func = eval
    try:
        func(code, glb, loc)
        return (None, None, None)
    except BaseException:
        type, value, traceback = sys.exc_info()
        # strip off the current frame as the traceback should only show user code
        traceback = traceback.tb_next
        return type, value, traceback


def get_cache_filename(fname, code=True):
    """
    Return the filename of the cache for the given filename.

    Cache filenames are similar to those used by the Mercurial DVCS for its
    internal store.

    The ``code`` switch should be true if we should use the code store rather
    than the script store.
    """
    datadir = XSH.env["XONSH_DATA_DIR"]
    cachedir = os.path.join(
        datadir, "xonsh_code_cache" if code else "xonsh_script_cache"
    )
    cachefname = os.path.join(cachedir, *_cache_renamer(fname, code=code))
    return cachefname


def update_cache(ccode, cache_file_name):
    """
    Update the cache at ``cache_file_name`` to contain the compiled code
    represented by ``ccode``.
    """
    if cache_file_name is not None:
        if not is_writable_file(cache_file_name):
            if XSH.env.get("XONSH_DEBUG", "False"):
                print_warning(
                    f"update_cache: Cache file is not writable: {cache_file_name}\n"
                    f"Set $XONSH_CACHE_SCRIPTS=0, $XONSH_CACHE_EVERYTHING=0 to disable cache."
                )
            return
        os.makedirs(os.path.dirname(cache_file_name), exist_ok=True)
        with open(cache_file_name, "wb") as cfile:
            cfile.write(XONSH_VERSION.encode() + b"\n")
            cfile.write(bytes(PYTHON_VERSION_INFO_BYTES) + b"\n")
            marshal.dump(ccode, cfile)


def _check_cache_versions(cfile):
    # version data should be < 1 kb
    ver = cfile.readline(1024).strip()
    if ver != XONSH_VERSION.encode():
        return False
    ver = cfile.readline(1024).strip()
    return ver == PYTHON_VERSION_INFO_BYTES


def compile_code(filename, code, execer, glb, loc, mode):
    """
    Wrapper for ``execer.compile`` to compile the given code
    """

    if filename.endswith(".py") and mode == "exec":
        return compile(code, filename, mode)

    if not code.endswith("\n"):
        code += "\n"
    old_filename = execer.filename
    try:
        execer.filename = filename
        ccode = execer.compile(code, glbs=glb, locs=loc, mode=mode, filename=filename)
    except Exception:
        raise
    finally:
        execer.filename = old_filename
    return ccode


def script_cache_check(filename, cachefname):
    """
    Check whether the script cache for a particular file is valid.

    Returns a tuple containing: a boolean representing whether the cached code
    should be used, and the cached code (or ``None`` if the cache should not be
    used).
    """
    ccode = None
    run_cached = False
    if os.path.isfile(cachefname):
        if os.stat(cachefname).st_mtime >= os.stat(filename).st_mtime:
            with open(cachefname, "rb") as cfile:
                if not _check_cache_versions(cfile):
                    return False, None
                ccode = marshal.load(cfile)
                run_cached = True
    return run_cached, ccode


def run_script_with_cache(filename, execer, glb=None, loc=None, mode="exec"):
    """
    Run a script, using a cached version if it exists (and the source has not
    changed), and updating the cache as necessary.
    See run_compiled_code for the return value.
    """
    run_cached = False
    use_cache = should_use_cache(execer, mode)
    cachefname = get_cache_filename(filename, code=False)
    if use_cache:
        run_cached, ccode = script_cache_check(filename, cachefname)
    if not run_cached:
        with open(filename, encoding="utf-8") as f:
            code = f.read()
        ccode = compile_code(filename, code, execer, glb, loc, mode)
        if use_cache:
            update_cache(ccode, cachefname)
    return run_compiled_code(ccode, glb, loc, mode)


def code_cache_name(code):
    """
    Return an appropriate spoofed filename for the given code.
    """
    if isinstance(code, str):
        code = code.encode()
    return hashlib.md5(code).hexdigest()


def code_cache_check(cachefname):
    """
    Check whether the code cache for a particular piece of code is valid.

    Returns a tuple containing: a boolean representing whether the cached code
    should be used, and the cached code (or ``None`` if the cache should not be
    used).
    """
    ccode = None
    run_cached = False
    if os.path.isfile(cachefname):
        with open(cachefname, "rb") as cfile:
            if not _check_cache_versions(cfile):
                return False, None
            ccode = marshal.load(cfile)
            run_cached = True
    return run_cached, ccode


def run_code_with_cache(
    code, display_filename, execer, glb=None, loc=None, mode="exec"
):
    """
    Run a piece of code, using a cached version if it exists, and updating the
    cache as necessary.
    See run_compiled_code for the return value.
    """
    use_cache = should_use_cache(execer, mode)
    filename = code_cache_name(code)
    cachefname = get_cache_filename(filename, code=True)
    run_cached = False
    if use_cache:
        run_cached, ccode = code_cache_check(cachefname)
    if not run_cached:
        ccode = compile_code(display_filename, code, execer, glb, loc, mode)
        update_cache(ccode, cachefname)
    return run_compiled_code(ccode, glb, loc, mode)
