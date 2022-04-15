import ast
import glob
import os
import re

import xonsh.lazyasd as xl
import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.completers.tools import RichCompletion, contextual_completer
from xonsh.parsers.completion_context import CommandContext


@xl.lazyobject
def PATTERN_NEED_QUOTES():
    pattern = r'\s`\$\{\}\[\]\,\*\(\)"\'\?&#'
    if xp.ON_WINDOWS:
        pattern += "%"
    pattern = "[" + pattern + "]" + r"|\band\b|\bor\b"
    return re.compile(pattern)


def cd_in_command(line):
    """Returns True if "cd" is a token in the line, False otherwise."""
    lexer = XSH.execer.parser.lexer
    lexer.reset()
    lexer.input(line)
    have_cd = False
    for tok in lexer:
        if tok.type == "NAME" and tok.value == "cd":
            have_cd = True
            break
    return have_cd


def _get_normalized_pstring_quote(s):
    for pre, norm_pre in (("p", "p"), ("pr", "pr"), ("rp", "pr"), ("fp", "pf")):
        for q in ('"', "'"):
            if s.startswith(f"{pre}{q}"):
                return norm_pre, q
    return (None, None)


def _path_from_partial_string(inp, pos=None):
    if pos is None:
        pos = len(inp)
    partial = inp[:pos]
    startix, endix, quote = xt.check_for_partial_string(partial)
    _post = ""
    if startix is None:
        return None
    elif endix is None:
        string = partial[startix:]
    else:
        if endix != pos:
            _test = partial[endix:pos]
            if not any(i == " " for i in _test):
                _post = _test
            else:
                return None
        string = partial[startix:endix]

    # If 'pr'/'rp', treat as raw string, otherwise strip leading 'p'
    pstring_pre = _get_normalized_pstring_quote(quote)[0]
    if pstring_pre == "pr":
        string = f"r{string[2:]}"
    elif pstring_pre == "p":
        string = string[1:]

    end = xt.RE_STRING_START.sub("", quote)
    _string = string
    if not _string.endswith(end):
        _string = _string + end
    try:
        val = ast.literal_eval(_string)
    except (SyntaxError, ValueError):
        return None
    if isinstance(val, bytes):
        env = XSH.env
        val = val.decode(
            encoding=env.get("XONSH_ENCODING"), errors=env.get("XONSH_ENCODING_ERRORS")
        )
    return string + _post, val + _post, quote, end


def _normpath(p):
    """
    Wraps os.normpath() to avoid removing './' at the beginning
    and '/' at the end. On windows it does the same with backslashes
    """
    initial_dotslash = p.startswith(os.curdir + os.sep)
    initial_dotslash |= xp.ON_WINDOWS and p.startswith(os.curdir + os.altsep)
    p = p.rstrip()
    trailing_slash = p.endswith(os.sep)
    trailing_slash |= xp.ON_WINDOWS and p.endswith(os.altsep)
    p = os.path.normpath(p)
    if initial_dotslash and p != ".":
        p = os.path.join(os.curdir, p)
    if trailing_slash:
        p = os.path.join(p, "")
    if xp.ON_WINDOWS and XSH.env.get("FORCE_POSIX_PATHS"):
        p = p.replace(os.sep, os.altsep)
    return p


def _startswithlow(x, start, startlow=None):
    if startlow is None:
        startlow = start.lower()
    return x.startswith(start) or x.lower().startswith(startlow)


def _startswithnorm(x, start, startlow=None):
    return x.startswith(start)


def _dots(prefix):
    complete_dots = XSH.env.get("COMPLETE_DOTS", "matching").lower()
    if complete_dots == "never":
        return ()
    slash = xt.get_sep()
    if slash == "\\":
        slash = ""
    prefixes = {"."}
    if complete_dots == "always":
        prefixes.add("")
    if prefix in prefixes:
        return ("." + slash, ".." + slash)
    elif prefix == "..":
        return (".." + slash,)
    else:
        return ()


def _add_cdpaths(paths, prefix):
    """Completes current prefix using CDPATH"""
    env = XSH.env
    csc = env.get("CASE_SENSITIVE_COMPLETIONS")
    glob_sorted = env.get("GLOB_SORTED")
    for cdp in env.get("CDPATH"):
        test_glob = os.path.join(cdp, prefix) + "*"
        for s in xt.iglobpath(
            test_glob, ignore_case=(not csc), sort_result=glob_sorted
        ):
            if os.path.isdir(s):
                paths.add(os.path.relpath(s, cdp))


def _quote_to_use(x):
    single = "'"
    double = '"'
    if single in x and double not in x:
        return double
    else:
        return single


def _is_directory_in_cdpath(path):
    env = XSH.env
    for cdp in env.get("CDPATH"):
        if os.path.isdir(os.path.join(cdp, path)):
            return True
    return False


def _quote_paths(paths, start, end, append_end=True, cdpath=False):
    expand_path = XSH.expand_path
    out = set()
    space = " "
    backslash = "\\"
    double_backslash = "\\\\"
    slash = xt.get_sep()
    orig_start = start
    orig_end = end
    # quote on all or none, to make readline completes to max prefix
    need_quotes = any(
        re.search(PATTERN_NEED_QUOTES, x) or (backslash in x and slash != backslash)
        for x in paths
    )

    for s in paths:
        start = orig_start
        end = orig_end
        if start == "" and need_quotes:
            start = end = _quote_to_use(s)
        expanded = expand_path(s)
        if os.path.isdir(expanded) or (cdpath and _is_directory_in_cdpath(expanded)):
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
        if end in s:
            s = s.replace(end, "".join("\\%s" % i for i in end))
        s = start + s + end if append_end else start + s
        out.add(s)
    return out, need_quotes


def _joinpath(path):
    # convert our tuple representation back into a string representing a path
    if path is None:
        return ""
    elif len(path) == 0:
        return ""
    elif path == ("",):
        return xt.get_sep()
    elif path[0] == "":
        return xt.get_sep() + _normpath(os.path.join(*path))
    else:
        return _normpath(os.path.join(*path))


def _splitpath(path):
    # convert a path into an intermediate tuple representation
    # if this tuple starts with '', it means that the path was an absolute path
    path = _normpath(path)
    if path.startswith(xt.get_sep()):
        pre = ("",)
    else:
        pre = ()
    return pre + _splitpath_helper(path, ())


def _splitpath_helper(path, sofar=()):
    folder, path = os.path.split(path)
    if path:
        sofar = sofar + (path,)
    if not folder or folder == xt.get_sep():
        return sofar[::-1]
    elif xp.ON_WINDOWS and not path:
        return os.path.splitdrive(folder)[:1] + sofar[::-1]
    elif xp.ON_WINDOWS and os.path.splitdrive(path)[0]:
        return sofar[::-1]
    return _splitpath_helper(folder, sofar)


def subsequence_match(ref, typed, csc):
    """
    Detects whether typed is a subsequence of ref.

    Returns ``True`` if the characters in ``typed`` appear (in order) in
    ``ref``, regardless of exactly where in ``ref`` they occur.  If ``csc`` is
    ``False``, ignore the case of ``ref`` and ``typed``.

    Used in "subsequence" path completion (e.g., ``~/u/ro`` expands to
    ``~/lou/carcohl``)
    """
    if csc:
        return _subsequence_match_iter(ref, typed)
    else:
        return _subsequence_match_iter(ref.lower(), typed.lower())


def _subsequence_match_iter(ref, typed):
    if len(typed) == 0:
        return True
    elif len(ref) == 0:
        return False
    elif ref[0] == typed[0]:
        return _subsequence_match_iter(ref[1:], typed[1:])
    else:
        return _subsequence_match_iter(ref[1:], typed)


def _expand_one(sofar, nextone, csc):
    out = set()
    glob_sorted = XSH.env.get("GLOB_SORTED")
    for i in sofar:
        _glob = os.path.join(_joinpath(i), "*") if i is not None else "*"
        for j in xt.iglobpath(_glob, sort_result=glob_sorted):
            j = os.path.basename(j)
            if subsequence_match(j, nextone, csc):
                out.add((i or ()) + (j,))
    return out


def _complete_path_raw(prefix, line, start, end, ctx, cdpath=True, filtfunc=None):
    # string stuff for automatic quoting
    path_str_start = ""
    path_str_end = ""
    append_end = True
    p = _path_from_partial_string(line, end)
    lprefix = len(prefix)
    if p is not None:
        lprefix = len(p[0])
        # Compensate for 'p' if p-string variant
        pstring_pre = _get_normalized_pstring_quote(p[2])[0]
        if pstring_pre in ("pr", "p"):
            lprefix += 1
        prefix = p[1]
        path_str_start = p[2]
        path_str_end = p[3]
        if len(line) >= end + 1 and line[end] == path_str_end:
            append_end = False
    tilde = "~"
    paths = set()
    env = XSH.env
    csc = env.get("CASE_SENSITIVE_COMPLETIONS")
    glob_sorted = env.get("GLOB_SORTED")
    prefix = glob.escape(prefix)
    for s in xt.iglobpath(prefix + "*", ignore_case=(not csc), sort_result=glob_sorted):
        paths.add(s)
    if len(paths) == 0 and env.get("SUBSEQUENCE_PATH_COMPLETION"):
        # this block implements 'subsequence' matching, similar to fish and zsh.
        # matches are based on subsequences, not substrings.
        # e.g., ~/u/ro completes to ~/lou/carcolh
        # see above functions for details.
        p = _splitpath(os.path.expanduser(prefix))
        p_len = len(p)
        if p_len != 0:
            relative_char = ["", ".", ".."]
            if p[0] in relative_char:
                i = 0
                while i < p_len and p[i] in relative_char:
                    i += 1
                basedir = p[:i]
                p = p[i:]
            else:
                basedir = None
            matches_so_far = {basedir}
            for i in p:
                matches_so_far = _expand_one(matches_so_far, i, csc)
            paths |= {_joinpath(i) for i in matches_so_far}
    if len(paths) == 0 and env.get("FUZZY_PATH_COMPLETION"):
        threshold = env.get("SUGGEST_THRESHOLD")
        for s in xt.iglobpath(
            os.path.dirname(prefix) + "*",
            ignore_case=(not csc),
            sort_result=glob_sorted,
        ):
            if xt.levenshtein(prefix, s, threshold) < threshold:
                paths.add(s)
    if cdpath and cd_in_command(line):
        _add_cdpaths(paths, prefix)
    paths = set(filter(filtfunc, paths))
    if tilde in prefix:
        home = os.path.expanduser(tilde)
        paths = {s.replace(home, tilde) for s in paths}
    paths, _ = _quote_paths(
        {_normpath(s) for s in paths}, path_str_start, path_str_end, append_end, cdpath
    )
    paths.update(filter(filtfunc, _dots(prefix)))
    return paths, lprefix


@contextual_completer
def complete_path(context):
    """Completes path names."""
    if context.command:
        return contextual_complete_path(context.command)
    elif context.python:
        line = context.python.prefix
        # simple prefix _complete_path_raw will handle gracefully:
        prefix = line.rsplit(" ", 1)[-1]
        return _complete_path_raw(prefix, line, len(line) - len(prefix), len(line), {})
    return set(), 0


def contextual_complete_path(command: CommandContext, cdpath=True, filtfunc=None):
    # ``_complete_path_raw`` may add opening quotes:
    prefix = command.raw_prefix

    completions, lprefix = _complete_path_raw(
        prefix,
        prefix,
        0,
        len(prefix),
        ctx={},
        cdpath=cdpath,
        filtfunc=filtfunc,
    )

    # ``_complete_path_raw`` may have added closing quotes:
    rich_completions = {
        RichCompletion(comp, append_closing_quote=False) for comp in completions
    }

    return rich_completions, lprefix


def complete_dir(command: CommandContext):
    return contextual_complete_path(command, filtfunc=os.path.isdir)
