import os
import sys
import hashlib
import marshal
import builtins

def _splitpath(path, sofar=[]):
    folder, path = os.path.split(path)
    if path == "":
        return sofar[::-1]
    elif folder == "":
        return (sofar + [path])[::-1]
    else:
        return _splitpath(folder, sofar + [path])

_CHARACTER_MAP = {chr(o): '_%s' % chr(o+32) for o in range(65, 91)}
_CHARACTER_MAP.update({'.': '_.', '_': '__'})


def _cache_renamer(path, code=False):
    if not code:
        path = os.path.abspath(path)
    o = [''.join(_CHARACTER_MAP.get(i, i) for i in w) for w in _splitpath(path)]
    o[-1] = "{}.{}".format(o[-1], sys.implementation.cache_tag)
    return o


def _make_if_not_exists(dirname):
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

def should_use_cache(execer, mode):
    """
    Return ``True`` if caching has been enabled for this mode (through command
    line flags or environment variables)
    """
    if mode == 'exec':
        return ((execer.scriptcache or
                    execer.cacheall) and
                (builtins.__xonsh_env__['XONSH_CACHE_SCRIPTS'] or
                    builtins.__xonsh_env__['XONSH_CACHE_EVERYTHING']))
    else:
        return (execer.cacheall or
                builtins.__xonsh_env__['XONSH_CACHE_EVERYTHING'])


def run_compiled_code(code, glb, loc, mode):
    """
    Helper to run code in a given mode and context
    """
    if code is None:
        return
    if mode in {'exec', 'single'}:
        func = exec
    else:
        func = eval
    func(code, glb, loc)


def get_cache_filename(fname, code=True):
    """
    Return the filename of the cache for the given filename.

    Cache filenames are similar to those used by the Mercurial DVCS for its
    internal store.

    The ``code`` switch should be true if we should use the code store rather
    than the script store.
    """
    datadir = builtins.__xonsh_env__['XONSH_DATA_DIR']
    cachedir = os.path.join(datadir, 'xonsh_code_cache' if code else 'xonsh_script_cache')
    cachefname = os.path.join(cachedir, *_cache_renamer(fname, code=code))
    return cachefname


def update_cache(ccode, cache_file_name):
    """
    Update the cache at ``cache_file_name`` to contain the compiled code
    represented by ``ccode``.
    """
    if cache_file_name is not None:
        _make_if_not_exists(os.path.dirname(cache_file_name))
        with open(cache_file_name, 'wb') as cfile:
            marshal.dump(ccode, cfile)


def compile_code(filename, code, execer, glb, loc, mode):
    """
    Wrapper for ``execer.compile`` to compile the given code
    """
    try:
        if not code.endswith('\n'):
            code += '\n'
        old_filename = execer.filename
        execer.filename = filename
        ccode = execer.compile(code, glbs=glb, locs=loc, mode=mode)
    except:
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
            with open(cachefname, 'rb') as cfile:
                ccode = marshal.load(cfile)
                run_cached = True
    return run_cached, ccode


def run_script_with_cache(filename, execer, glb=None, loc=None, mode='exec'):
    """
    Run a script, using a cached version if it exists (and the source has not
    changed), and updating the cache as necessary.
    """
    run_cached = False
    use_cache = should_use_cache(execer, mode)
    if use_cache:
        cachefname = get_cache_filename(filename, code=False)
        run_cached, ccode = script_cache_check(filename, cachefname)
    if not run_cached:
        with open(filename, 'r') as f:
            code = f.read()
        ccode = compile_code(filename, code, execer, glb, loc, mode)
        update_cache(ccode, cachefname) 
    run_compiled_code(ccode, glb, loc, mode)


def code_cache_name(code):
    """
    Return an appropriate spoofed filename for the given code.
    """
    if isinstance(code, str):
        _code = code.encode()
    else:
        _code = code
    return hashlib.md5(_code).hexdigest()


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
        with open(cachefname, 'rb') as cfile:
            ccode = marshal.load(cfile)
            run_cached = True
    return run_cached, ccode 


def run_code_with_cache(code, execer, glb=None, loc=None, mode='exec'):
    """
    Run a piece of code, using a cached version if it exists, and updating the
    cache as necessary.
    """
    use_cache = should_use_cache(execer, mode)
    filename = code_cache_name(code)
    cachefname = get_cache_filename(filename, code=True)
    run_cached = False
    if use_cache:
        run_cached, ccode = code_cache_check(cachefname)
    if not run_cached:
        ccode = compile_code(filename, code, execer, glb, loc, mode)
        update_cache(ccode, cachefname) 
    run_compiled_code(ccode, glb, loc, mode)
