import os
import shlex
import pathlib
import builtins
import subprocess

import xonsh.platform as xp

from xonsh.completers.path import _quote_paths

BASH_COMPLETE_SCRIPT = r"""
{source}

# Override some functions in bash-completion, do not quote for readline
quote_readline()
{{
    echo "$1"
}}

_quote_readline_by_ref()
{{
    if [[ $1 == \'* ]]; then
        # Leave out first character
        printf -v $2 %s "${{1:1}}"
    else
        printf -v $2 %s "$1"
    fi

    [[ ${{!2}} == \$* ]] && eval $2=${{!2}}
}}


function _get_complete_statement {{
    complete -p {cmd} 2> /dev/null || echo "-F _minimal"
}}

_complete_stmt=$(_get_complete_statement)
if echo "$_complete_stmt" | grep --quiet -e "_minimal"
then
    declare -f _completion_loader > /dev/null && _completion_loader {cmd}
    _complete_stmt=$(_get_complete_statement)
fi

_func=$(echo "$_complete_stmt" | grep -o -e '-F \w\+' | cut -d ' ' -f 2)
declare -f "$_func" > /dev/null || exit 1

echo "$_complete_stmt"
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
    source = _get_completions_source()
    if not source:
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
        prefix_quoted = '""'
        n += 1
    else:
        prefix_quoted = shlex.quote(prefix)

    script = BASH_COMPLETE_SCRIPT.format(
        source=source, line=' '.join(shlex.quote(p) for p in splt),
        comp_line=shlex.quote(line), n=n, cmd=shlex.quote(cmd),
        end=endidx + 1, prefix=prefix_quoted, prev=shlex.quote(prev),
    )

    try:
        out = subprocess.check_output(
            [xp.bash_command(), '-c', script], universal_newlines=True,
            stderr=subprocess.PIPE, env=builtins.__xonsh_env__.detype())
    except (subprocess.CalledProcessError, FileNotFoundError,
            UnicodeDecodeError):
        return set()

    out = out.splitlines()
    complete_stmt = out[0]
    out = set(out[1:])

    # From GNU Bash document: The results of the expansion are prefix-matched
    # against the word being completed
    commprefix = os.path.commonprefix(out)
    strip_len = 0
    while strip_len < len(prefix):
        if commprefix.startswith(prefix[strip_len:]):
            break
        strip_len += 1

    if '-o noquote' not in complete_stmt:
        out = _quote_paths(out, '', '')
    if '-o nospace' in complete_stmt:
        out = set([x.rstrip() for x in out])

    return out, len(prefix) - strip_len


def _get_completions_source():
    completers = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    for path in map(pathlib.Path, completers):
        if path.is_file():
            return 'source "{}"'.format(path.as_posix())
    return None
