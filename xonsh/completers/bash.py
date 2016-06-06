import os
import re
import shlex
import pickle
import builtins
import subprocess

import hashlib

from pathlib import Path

from xonsh.platform import ON_WINDOWS

RE_DASHF = re.compile(r'-F\s+(\w+)')

INITED = False

BASH_COMPLETE_HASH = None
BASH_COMPLETE_FUNCS = {}
BASH_COMPLETE_FILES = {}

CACHED_HASH = None
CACHED_FUNCS = None
CACHED_FILES = None

BASH_COMPLETE_SCRIPT = """source "{filename}"
COMP_WORDS=({line})
COMP_LINE={comp_line}
COMP_POINT=${{#COMP_LINE}}
COMP_COUNT={end}
COMP_CWORD={n}
{func} {cmd} {prefix} {prev}
for ((i=0;i<${{#COMPREPLY[*]}};i++)) do echo ${{COMPREPLY[i]}}; done
"""


if ON_WINDOWS:
    from xonsh.platform import WINDOWS_BASH_COMMAND as BASH_COMMAND
else: 
    BASH_COMMAND = 'bash'


def update_bash_completion():
    global BASH_COMPLETE_FUNCS, BASH_COMPLETE_FILES, BASH_COMPLETE_HASH
    global CACHED_FUNCS, CACHED_FILES, CACHED_HASH, INITED

    completers = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    BASH_COMPLETE_HASH = hashlib.md5(repr(completers).encode()).hexdigest()

    datadir = builtins.__xonsh_env__['XONSH_DATA_DIR']
    cachefname = os.path.join(datadir, 'bash_completion_cache')

    if not INITED:
        if os.path.isfile(cachefname):
            # load from cache
            with open(cachefname, 'rb') as cache:
                CACHED_HASH, CACHED_FUNCS, CACHED_FILES = pickle.load(cache)
                BASH_COMPLETE_HASH = CACHED_HASH
                BASH_COMPLETE_FUNCS = CACHED_FUNCS
                BASH_COMPLETE_FILES = CACHED_FILES
        else:
            # create initial cache
            _load_bash_complete_funcs()
            _load_bash_complete_files()
            CACHED_HASH = BASH_COMPLETE_HASH
            CACHED_FUNCS = BASH_COMPLETE_FUNCS
            CACHED_FILES = BASH_COMPLETE_FILES
            with open(cachefname, 'wb') as cache:
                val = (CACHED_HASH, CACHED_FUNCS, CACHED_FILES)
                pickle.dump(val, cache)
        INITED = True

    invalid = ((not os.path.isfile(cachefname)) or
               BASH_COMPLETE_HASH != CACHED_HASH or
               _completions_time() > os.stat(cachefname).st_mtime)

    if invalid:
        # update the cache
        _load_bash_complete_funcs()
        _load_bash_complete_files()
        CACHED_HASH = BASH_COMPLETE_HASH
        CACHED_FUNCS = BASH_COMPLETE_FUNCS
        CACHED_FILES = BASH_COMPLETE_FILES
        with open(cachefname, 'wb') as cache:
            val = (CACHED_HASH, BASH_COMPLETE_FUNCS, BASH_COMPLETE_FILES)
            pickle.dump(val, cache)


def complete_from_bash(prefix, line, begidx, endidx, ctx):
    """Completes based on results from BASH completion."""
    update_bash_completion()
    splt = line.split()
    cmd = splt[0]
    func = BASH_COMPLETE_FUNCS.get(cmd, None)
    fnme = BASH_COMPLETE_FILES.get(cmd, None)
    if func is None or fnme is None:
        return set()
    idx = n = 0
    for n, tok in enumerate(splt):
        if tok == prefix:
            idx = line.find(prefix, idx)
            if idx >= begidx:
                break
        prev = tok
    if len(prefix) == 0:
        prefix = '""'
        n += 1
    else:
        prefix = shlex.quote(prefix)

    script = BASH_COMPLETE_SCRIPT.format(
        filename=fnme, line=' '.join(shlex.quote(p) for p in splt),
        comp_line=shlex.quote(line), n=n, func=func, cmd=cmd,
        end=endidx + 1, prefix=prefix, prev=shlex.quote(prev))
    try:
        out = subprocess.check_output(
            [BASH_COMMAND], input=script, universal_newlines=True,
            stderr=subprocess.PIPE, env=builtins.__xonsh_env__.detype())
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ''

    rtn = set(out.splitlines())
    return rtn


def _load_bash_complete_funcs():
    global BASH_COMPLETE_FUNCS
    BASH_COMPLETE_FUNCS = bcf = {}
    inp = _collect_completions_sources()
    if not inp:
        return
    inp.append('complete -p\n')
    out = _source_completions(inp)
    for line in out.splitlines():
        head, _, cmd = line.rpartition(' ')
        if len(cmd) == 0 or cmd == 'cd':
            continue
        m = RE_DASHF.search(head)
        if m is None:
            continue
        bcf[cmd] = m.group(1)


def _load_bash_complete_files():
    global BASH_COMPLETE_FILES
    inp = _collect_completions_sources()
    if not inp:
        BASH_COMPLETE_FILES = {}
        return
    if BASH_COMPLETE_FUNCS:
        inp.append('shopt -s extdebug')
        bash_funcs = set(BASH_COMPLETE_FUNCS.values())
        inp.append('declare -F ' + ' '.join([f for f in bash_funcs]))
        inp.append('shopt -u extdebug\n')
    out = _source_completions(inp)
    func_files = {}
    for line in out.splitlines():
        parts = line.split()
        if ON_WINDOWS:
            parts = [parts[0], ' '.join(parts[2:])]
        func_files[parts[0]] = parts[-1]
    BASH_COMPLETE_FILES = {
        cmd: func_files[func]
        for cmd, func in BASH_COMPLETE_FUNCS.items()
        if func in func_files
    }


def _source_completions(source):
    try:
        return subprocess.check_output(
            [BASH_COMMAND], input='\n'.join(source), universal_newlines=True,
            env=builtins.__xonsh_env__.detype(), stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return ''

        
def _collect_completions_sources():
    sources = []
    completers = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    paths = (Path(x) for x in completers)
    for path in paths:
        if path.is_file():
            sources.append('source "{}"'.format(path.as_posix()))
        elif path.is_dir():
            for _file in (x for x in path.glob('*') if x.is_file()):
                sources.append('source "{}"'.format(_file.as_posix()))
    return sources


def _completions_time():
    compfiles = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    compfiles = [os.stat(x).st_mtime for x in compfiles if os.path.exists(x)]
    return max(compfiles) if compfiles else 0
