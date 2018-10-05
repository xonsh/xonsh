"""This module provides the implementation for the retrieving completion results
from bash.
"""
# developer note: this file should not perform any action on import.
#                 This file comes from https://github.com/xonsh/py-bash-completion
#                 and should be edited there!
import os
import re
import sys
import shlex
import shutil
import pathlib
import platform
import functools
import subprocess

__version__ = "0.2.5"


@functools.lru_cache(1)
def _git_for_windows_path():
    """Returns the path to git for windows, if available and None otherwise."""
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\GitForWindows")
        gfwp, _ = winreg.QueryValueEx(key, "InstallPath")
    except FileNotFoundError:
        gfwp = None
    return gfwp


@functools.lru_cache(1)
def _windows_bash_command(env=None):
    """Determines the command for Bash on windows."""
    wbc = "bash"
    path = None if env is None else env.get("PATH", None)
    bash_on_path = shutil.which("bash", path=path)
    if bash_on_path:
        try:
            out = subprocess.check_output(
                [bash_on_path, "--version"],
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        except subprocess.CalledProcessError:
            bash_works = False
        else:
            # Check if Bash is from the "Windows Subsystem for Linux" (WSL)
            # which can't be used by xonsh foreign-shell/completer
            bash_works = out and "pc-linux-gnu" not in out.splitlines()[0]

        if bash_works:
            wbc = bash_on_path
        else:
            gfwp = _git_for_windows_path()
            if gfwp:
                bashcmd = os.path.join(gfwp, "bin\\bash.exe")
                if os.path.isfile(bashcmd):
                    wbc = bashcmd
    return wbc


def _bash_command(env=None):
    """Determines the command for Bash on the current plaform."""
    if platform.system() == "Windows":
        bc = _windows_bash_command(env=None)
    else:
        bc = "bash"
    return bc


def _bash_completion_paths_default():
    """A possibly empty tuple with default paths to Bash completions known for
    the current platform.
    """
    platform_sys = platform.system()
    if platform_sys == "Linux" or sys.platform == "cygwin":
        bcd = ("/usr/share/bash-completion/bash_completion",)
    elif platform_sys == "Darwin":
        bcd = (
            "/usr/local/share/bash-completion/bash_completion",  # v2.x
            "/usr/local/etc/bash_completion",
        )  # v1.x
    elif platform_sys == "Windows":
        gfwp = _git_for_windows_path()
        if gfwp:
            bcd = (
                os.path.join(gfwp, "usr\\share\\bash-completion\\" "bash_completion"),
                os.path.join(
                    gfwp, "mingw64\\share\\git\\completion\\" "git-completion.bash"
                ),
            )
        else:
            bcd = ()
    else:
        bcd = ()
    return bcd


_BASH_COMPLETIONS_PATHS_DEFAULT = None


def _get_bash_completions_source(paths=None):
    global _BASH_COMPLETIONS_PATHS_DEFAULT
    if paths is None:
        if _BASH_COMPLETIONS_PATHS_DEFAULT is None:
            _BASH_COMPLETIONS_PATHS_DEFAULT = _bash_completion_paths_default()
        paths = _BASH_COMPLETIONS_PATHS_DEFAULT
    for path in map(pathlib.Path, paths):
        if path.is_file():
            return 'source "{}"'.format(path.as_posix())
    return None


def _bash_get_sep():
    """ Returns the appropriate filepath separator char depending on OS and
    xonsh options set
    """
    if platform.system() == "Windows":
        return os.altsep
    else:
        return os.sep


_BASH_PATTERN_NEED_QUOTES = None


def _bash_pattern_need_quotes():
    global _BASH_PATTERN_NEED_QUOTES
    if _BASH_PATTERN_NEED_QUOTES is not None:
        return _BASH_PATTERN_NEED_QUOTES
    pattern = r'\s`\$\{\}\,\*\(\)"\'\?&'
    if platform.system() == "Windows":
        pattern += "%"
    pattern = "[" + pattern + "]" + r"|\band\b|\bor\b"
    _BASH_PATTERN_NEED_QUOTES = re.compile(pattern)
    return _BASH_PATTERN_NEED_QUOTES


def _bash_expand_path(s):
    """Takes a string path and expands ~ to home and environment vars."""
    # expand ~ according to Bash unquoted rules "Each variable assignment is
    # checked for unquoted tilde-prefixes immediately following a ':' or the
    # first '='". See the following for more details.
    # https://www.gnu.org/software/bash/manual/html_node/Tilde-Expansion.html
    pre, char, post = s.partition("=")
    if char:
        s = os.path.expanduser(pre) + char
        s += os.pathsep.join(map(os.path.expanduser, post.split(os.pathsep)))
    else:
        s = os.path.expanduser(s)
    return s


def _bash_quote_to_use(x):
    single = "'"
    double = '"'
    if single in x and double not in x:
        return double
    else:
        return single


def _bash_quote_paths(paths, start, end):
    out = set()
    space = " "
    backslash = "\\"
    double_backslash = "\\\\"
    slash = _bash_get_sep()
    orig_start = start
    orig_end = end
    # quote on all or none, to make readline completes to max prefix
    need_quotes = any(
        re.search(_bash_pattern_need_quotes(), x)
        or (backslash in x and slash != backslash)
        for x in paths
    )

    for s in paths:
        start = orig_start
        end = orig_end
        if start == "" and need_quotes:
            start = end = _bash_quote_to_use(s)
        if os.path.isdir(_bash_expand_path(s)):
            _tail = slash
        elif end == "":
            _tail = space
        else:
            _tail = ""
        if start != "" and "r" not in start and backslash in s:
            start = "r%s" % start
        s = s + _tail
        if end != "":
            if "r" not in start.lower():
                s = s.replace(backslash, double_backslash)
            if s.endswith(backslash) and not s.endswith(double_backslash):
                s += backslash
        if end in s:
            s = s.replace(end, "".join("\\%s" % i for i in end))
        out.add(start + s + end)
    return out, need_quotes


BASH_COMPLETE_SCRIPT = r"""
{source}

# Override some functions in bash-completion, do not quote for readline
quote_readline()
{{
    echo "$1"
}}

_quote_readline_by_ref()
{{
    if [[ $1 == \'* || $1 == \"* ]]; then
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

# print out completions, right-stripped if they contain no internal spaces
shopt -s extglob
for ((i=0;i<${{#COMPREPLY[*]}};i++))
do
    no_spaces="${{COMPREPLY[i]//[[:space:]]}}"
    no_trailing_spaces="${{COMPREPLY[i]%%+([[:space:]])}}"
    if [[ "$no_spaces" == "$no_trailing_spaces" ]]; then
        echo "$no_trailing_spaces"
    else
        echo "${{COMPREPLY[i]}}"
    fi
done
"""


def bash_completions(
    prefix,
    line,
    begidx,
    endidx,
    env=None,
    paths=None,
    command=None,
    quote_paths=_bash_quote_paths,
    **kwargs
):
    """Completes based on results from BASH completion.

    Parameters
    ----------
    prefix : str
        The string to match
    line : str
        The line that prefix appears on.
    begidx : int
        The index in line that prefix starts on.
    endidx : int
        The index in line that prefix ends on.
    env : Mapping, optional
        The environment dict to execute the Bash subprocess in.
    paths : list or tuple of str or None, optional
        This is a list (or tuple) of strings that specifies where the
        ``bash_completion`` script may be found. The first valid path will
        be used. For better performance, bash-completion v2.x is recommended
        since it lazy-loads individual completion scripts. For both
        bash-completion v1.x and v2.x, paths of individual completion scripts
        (like ``.../completes/ssh``) do not need to be included here. The
        default values are platform dependent, but sane.
    command : str or None, optional
        The /path/to/bash to use. If None, it will be selected based on the
        from the environment and platform.
    quote_paths : callable, optional
        A functions that quotes file system paths. You shouldn't normally need
        this as the default is acceptable 99+% of the time. This function should
        return a set of the new paths and a boolean for whether the paths were
        quoted.

    Returns
    -------
    rtn : set of str
        Possible completions of prefix
    lprefix : int
        Length of the prefix to be replaced in the completion.
    """
    source = _get_bash_completions_source(paths) or ""

    if prefix.startswith("$"):  # do not complete env variables
        return set(), 0

    splt = line.split()
    cmd = splt[0]
    idx = n = 0
    prev = ""
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
        source=source,
        line=" ".join(shlex.quote(p) for p in splt),
        comp_line=shlex.quote(line),
        n=n,
        cmd=shlex.quote(cmd),
        end=endidx + 1,
        prefix=prefix_quoted,
        prev=shlex.quote(prev),
    )

    if command is None:
        command = _bash_command(env=env)
    try:
        out = subprocess.check_output(
            [command, "-c", script],
            universal_newlines=True,
            stderr=subprocess.PIPE,
            env=env,
        )
        if not out:
            raise ValueError
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        UnicodeDecodeError,
        ValueError,
    ):
        return set(), 0

    out = out.splitlines()
    complete_stmt = out[0]
    out = set(out[1:])

    # From GNU Bash document: The results of the expansion are prefix-matched
    # against the word being completed

    # Ensure input to `commonprefix` is a list (now required by Python 3.6)
    commprefix = os.path.commonprefix(list(out))
    strip_len = 0
    strip_prefix = prefix.strip("\"'")
    while strip_len < len(strip_prefix) and strip_len < len(commprefix):
        if commprefix[strip_len] == strip_prefix[strip_len]:
            break
        strip_len += 1

    if "-o noquote" not in complete_stmt:
        out, need_quotes = quote_paths(out, "", "")
    if "-o nospace" in complete_stmt:
        out = set([x.rstrip() for x in out])

    return out, max(len(prefix) - strip_len, 0)


def bash_complete_line(line, return_line=True, **kwargs):
    """Provides the completion from the end of the line.

    Parameters
    ----------
    line : str
        Line to complete
    return_line : bool, optional
        If true (default), will return the entire line, with the completion added.
        If false, this will instead return the strings to append to the original line.
    kwargs : optional
        All other keyword arguments are passed to the bash_completions() function.

    Returns
    -------
    rtn : set of str
        Possible completions of prefix
    """
    # set up for completing from the end of the line
    split = line.split()
    if len(split) > 1 and not line.endswith(" "):
        prefix = split[-1]
        begidx = len(line.rsplit(prefix)[0])
    else:
        prefix = ""
        begidx = len(line)
    endidx = len(line)
    # get completions
    out, lprefix = bash_completions(prefix, line, begidx, endidx, **kwargs)
    # reformat output
    if return_line:
        preline = line[:-lprefix]
        rtn = {preline + o for o in out}
    else:
        rtn = {o[lprefix:] for o in out}
    return rtn


def _bc_main(args=None):
    """Runs complete_line() and prints the output."""
    from argparse import ArgumentParser

    p = ArgumentParser("bash_completions")
    p.add_argument(
        "--return-line",
        action="store_true",
        dest="return_line",
        default=True,
        help="will return the entire line, with the completion added",
    )
    p.add_argument(
        "--no-return-line",
        action="store_false",
        dest="return_line",
        help="will instead return the strings to append to the original line",
    )
    p.add_argument("line", help="line to complete")
    ns = p.parse_args(args=args)
    out = bash_complete_line(ns.line, return_line=ns.return_line)
    for o in sorted(out):
        print(o)


if __name__ == "__main__":
    _bc_main()
