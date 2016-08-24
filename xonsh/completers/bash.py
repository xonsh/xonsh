import shlex
import pathlib
import builtins
import subprocess

import xonsh.platform as xp

from xonsh.completers.path import _quote_paths

BASH_COMPLETE_SCRIPT = r"""
{sources}
if (complete -p "{cmd}" 2> /dev/null || echo _minimal) | grep --quiet -e "_minimal"
then
    declare -f _completion_loader > /dev/null && _completion_loader "{cmd}"
fi
_func=$(complete -p {cmd} | grep -o -e '-F \w\+' | cut -d ' ' -f 2)
COMP_WORDS=({line})
COMP_LINE={comp_line}
COMP_POINT=${{#COMP_LINE}}
COMP_COUNT={end}
COMP_CWORD={n}
$_func {cmd} {prefix} {prev}
for ((i=0;i<${{#COMPREPLY[*]}};i++)) do echo ${{COMPREPLY[i]}}; done
"""


def complete_from_bash(prefix, line, begidx, endidx, ctx):
    """Completes based on results from BASH completion."""
    sources = _collect_completions_sources()
    if not sources:
        return set()

    if prefix.startswith('$'):  # do not complete env variables
        return set()

    splt = line.split()
    cmd = splt[0]
    idx = n = 0
    prev = ''
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
        sources='\n'.join(sources), line=' '.join(shlex.quote(p) for p in splt),
        comp_line=shlex.quote(line), n=n, cmd=cmd,
        end=endidx + 1, prefix=prefix, prev=shlex.quote(prev),
    )

    try:
        out = subprocess.check_output(
            [xp.bash_command()], input=script, universal_newlines=True,
            stderr=subprocess.PIPE, env=builtins.__xonsh_env__.detype())
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ''

    rtn = _quote_paths(set(out.splitlines()), '', '')
    return rtn


def _collect_completions_sources():
    sources = []
    completers = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    paths = (pathlib.Path(x) for x in completers)
    for path in paths:
        if path.is_file():
            sources.append('source "{}"'.format(path.as_posix()))
        elif path.is_dir():
            for _file in (x for x in path.glob('*') if x.is_file()):
                sources.append('source "{}"'.format(_file.as_posix()))
    return sources
