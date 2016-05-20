# -*- coding: utf-8 -*-
"""A (tab-)completer for xonsh."""
import ast
import builtins
import inspect
import importlib
import os
from pathlib import Path
import pickle
import re
import shlex
import subprocess
import sys

from xonsh.built_ins import iglobpath, expand_path
from xonsh.platform import ON_WINDOWS
from xonsh.tools import (subexpr_from_unbalanced, get_sep,
                         check_for_partial_string, RE_STRING_START)


RE_DASHF = re.compile(r'-F\s+(\w+)')
RE_ATTR = re.compile(r'(\S+(\..+)*)\.(\w*)$')
RE_WIN_DRIVE = re.compile(r'^([a-zA-Z]):\\')


def _path_from_partial_string(inp, pos=None):
    if pos is None:
        pos = len(inp)
    partial = inp[:pos]
    startix, endix, quote = check_for_partial_string(partial)
    _post = ""
    if startix is None:
        return None
    elif endix is None:
        string = partial[startix:]
    else:
        if endix != pos:
            _test = partial[endix:pos]
            if not any(i == ' ' for i in _test):
                _post = _test
            else:
                return None
        string = partial[startix:endix]
    end = re.sub(RE_STRING_START, '', quote)
    _string = string
    if not _string.endswith(end):
        _string = _string + end
    try:
        val = ast.literal_eval(_string)
    except SyntaxError:
        return None
    if isinstance(val, bytes):
        env = builtins.__xonsh_env__
        val = val.decode(encoding=env.get('XONSH_ENCODING'),
                         errors=env.get('XONSH_ENCODING_ERRORS'))
    return string + _post, val + _post, quote, end


XONSH_TOKENS = {
    'and ', 'as ', 'assert ', 'break', 'class ', 'continue', 'def ', 'del ',
    'elif ', 'else', 'except ', 'finally:', 'for ', 'from ', 'global ',
    'import ', 'if ', 'in ', 'is ', 'lambda ', 'nonlocal ', 'not ', 'or ',
    'pass', 'raise ', 'return ', 'try:', 'while ', 'with ', 'yield ', '+', '-',
    '/', '//', '%', '**', '|', '&', '~', '^', '>>', '<<', '<', '<=', '>', '>=',
    '==', '!=', '->', '=', '+=', '-=', '*=', '/=', '%=', '**=', '>>=', '<<=',
    '&=', '^=', '|=', '//=', ',', ';', ':', '?', '??', '$(', '${', '$[', '..',
    '...'
}

CHARACTERS_NEED_QUOTES = ' `\t\r\n${}*()"\',?&'
if ON_WINDOWS:
    CHARACTERS_NEED_QUOTES += '%'

COMPLETION_SKIP_TOKENS = {'man', 'sudo', 'time', 'timeit', 'which'}

BASH_COMPLETE_SCRIPT = """source {filename}
COMP_WORDS=({line})
COMP_LINE={comp_line}
COMP_POINT=${{#COMP_LINE}}
COMP_COUNT={end}
COMP_CWORD={n}
{func} {cmd} {prefix} {prev}
for ((i=0;i<${{#COMPREPLY[*]}};i++)) do echo ${{COMPREPLY[i]}}; done
"""

WS = set(' \t\r\n')


def startswithlow(x, start, startlow=None):
    """True if x starts with a string or its lowercase version. The lowercase
    version may be optionally be provided.
    """
    if startlow is None:
        startlow = start.lower()
    return x.startswith(start) or x.lower().startswith(startlow)


def startswithnorm(x, start, startlow=None):
    """True if x starts with a string s. Ignores its lowercase version, but
    matches the API of startswithlow().
    """
    return x.startswith(start)


def _normpath(p):
    """ Wraps os.normpath() to avoid removing './' at the beginning
        and '/' at the end. On windows it does the same with backslases
    """
    initial_dotslash = p.startswith(os.curdir + os.sep)
    initial_dotslash |= (ON_WINDOWS and p.startswith(os.curdir + os.altsep))
    p = p.rstrip()
    trailing_slash = p.endswith(os.sep)
    trailing_slash |= (ON_WINDOWS and p.endswith(os.altsep))
    p = os.path.normpath(p)
    if initial_dotslash and p != '.':
        p = os.path.join(os.curdir, p)
    if trailing_slash:
        p = os.path.join(p, '')

    if ON_WINDOWS and builtins.__xonsh_env__.get('FORCE_POSIX_PATHS'):
        p = p.replace(os.sep, os.altsep)

    return p


class Completer(object):
    """This provides a list of optional completions for the xonsh shell."""

    def __init__(self):
        # initialize command cache
        self._cmds_cache = builtins.__xonsh_commands_cache__
        self._man_completer = ManCompleter()
        try:
            # FIXME this could be threaded for faster startup times
            self._load_bash_complete_funcs()
            # or we could make this lazy
            self._load_bash_complete_files()
            self.have_bash = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.have_bash = False

    def complete(self, prefix, line, begidx, endidx, ctx=None):
        """Complete the string, given a possible execution context.

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
        ctx : Iterable of str (ie dict, set, etc), optional
            Names in the current execution context.

        Returns
        -------
        rtn : list of str
            Possible completions of prefix, sorted alphabetically.
        lprefix : int
            Length of the prefix to be replaced in the completion
            (only used with prompt_toolkit)
        """
        space = ' '  # intern some strings for faster appending
        ctx = ctx or {}
        prefixlow = prefix.lower()
        _line = line
        line = builtins.aliases.expand_alias(line)
        # string stuff for automatic quoting
        path_str_start = ''
        path_str_end = ''
        p = _path_from_partial_string(_line, endidx)
        lprefix = len(prefix)
        if p is not None:
            lprefix = len(p[0])
            prefix = p[1]
            path_str_start = p[2]
            path_str_end = p[3]
        cmd = line.split(' ', 1)[0]
        while cmd in COMPLETION_SKIP_TOKENS:
            begidx -= len(cmd)+1
            endidx -= len(cmd)+1
            cmd = line.split(' ', 2)[1]
            line = line.split(' ', 1)[1]
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        startswither = startswithnorm if csc else startswithlow
        if begidx == 0:
            # the first thing we're typing; could be python or subprocess, so
            # anything goes.
            rtn = self.cmd_complete(prefix)
        elif cmd in self.bash_complete_funcs:
            # bash completions
            rtn = self.bash_complete(prefix, line, begidx, endidx)
            rtn |= self.path_complete(prefix, path_str_start, path_str_end)
            return self._filter_repeats(rtn), lprefix
        elif prefix.startswith('${') or prefix.startswith('@('):
            # python mode explicitly
            return self._python_mode_completions(prefix, ctx,
                                                 prefixlow,
                                                 startswither)
        elif prefix.startswith('-'):
            comps = self._man_completer.option_complete(prefix, cmd)
            return sorted(comps), lprefix
        elif cmd not in ctx:
            ltoks = line.split()
            if len(ltoks) > 2 and ltoks[0] == 'from' and ltoks[2] == 'import':
                # complete thing inside a module
                try:
                    mod = importlib.import_module(ltoks[1])
                except ImportError:
                    return set(), lprefix
                out = [i[0]
                       for i in inspect.getmembers(mod)
                       if i[0].startswith(prefix)]
                return out, lprefix
            if len(ltoks) == 2 and ltoks[0] == 'from':
                comps = ('{} '.format(i) for i in self.module_complete(prefix))
                return sorted(comps), lprefix
            if cmd == 'import' and begidx == len('import '):
                # completing module to import
                return sorted(self.module_complete(prefix)), lprefix
            if cmd in self._cmds_cache:
                # subproc mode; do path completions
                comps = self.path_complete(prefix, path_str_start,
                                           path_str_end, cdpath=True)
                return sorted(comps), lprefix
            else:
                # if we're here, could be anything
                rtn = set()
        else:
            # if we're here, we're not a command, but could be anything else
            rtn = set()
        rtn |= self._python_mode_completions(prefix, ctx,
                                             prefixlow,
                                             startswither)
        rtn |= {s + space for s in builtins.aliases
                if startswither(s, prefix, prefixlow)}
        rtn |= self.path_complete(prefix, path_str_start, path_str_end)
        return sorted(rtn), lprefix

    def _python_mode_completions(self, prefix, ctx, prefixlow, startswither):
        rtn = {s for s in XONSH_TOKENS if startswither(s, prefix, prefixlow)}
        if ctx is not None:
            if '.' in prefix:
                rtn |= self.attr_complete(prefix, ctx)
            else:
                rtn |= {s for s in ctx if startswither(s, prefix, prefixlow)}
        rtn |= {s for s in dir(builtins) if startswither(s, prefix, prefixlow)}
        return rtn

    def _canonical_rep(self, x):
        if x.endswith('"') or x.endswith("'"):
            x = ast.literal_eval(x)
            if isinstance(x, bytes):
                env = builtins.__xonsh_env__
                x = x.decode(encoding=env.get('XONSH_ENCODING'),
                             errors=env.get('XONSH_ENCODING_ERRORS'))
        if x.endswith('\\') or x.endswith(' ') or x.endswith('/'):
            x = x[:-1]
        return x

    def _filter_repeats(self, comps):
        reps = {}
        for comp in comps:
            canon = self._canonical_rep(comp)
            if canon not in reps:
                reps[canon] = []
            reps[canon].append(comp)
        return {max(i, key=len) for i in reps.values()}

    def find_and_complete(self, line, idx, ctx=None):
        """Finds the completions given only the full code line and a current
        cursor position. This represents an easier alternative to the
        complete() method.

        Parameters
        ----------
        line : str
            The line that prefix appears on.
        idx : int
            The current position in the line.
        ctx : Iterable of str (ie dict, set, etc), optional
            Names in the current execution context.

        Returns
        -------
        rtn : list of str
            Possible completions of prefix, sorted alphabetically.
        begidx : int
            The index in line that prefix starts on.
        endidx : int
            The index in line that prefix ends on.
        """
        if idx < 0:
            raise ValueError('index must be non-negative!')
        n = len(line)
        begidx = endidx = (idx - 1 if idx == n else idx)
        while 0 < begidx and line[begidx] not in WS:
            begidx -= 1
        begidx = begidx + 1 if line[begidx] in WS else begidx
        while endidx < n - 1 and line[endidx] not in WS:
            endidx += 1
        endidx = endidx - 1 if line[endidx] in WS else endidx
        prefix = line[begidx:endidx+1]
        rtn, _ = self.complete(prefix, line, begidx, endidx, ctx=ctx)
        return rtn, begidx, endidx

    def _add_env(self, paths, prefix):
        if prefix.startswith('$'):
            csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
            startswither = startswithnorm if csc else startswithlow
            key = prefix[1:]
            paths.update({'$' + k for k in builtins.__xonsh_env__
                         if startswither(k, key, key.lower())})

    def _add_dots(self, paths, prefix):
        if prefix in {'', '.'}:
            paths.update({'./', '../'})
        if prefix == '..':
            paths.add('../')

    def _add_cdpaths(self, paths, prefix):
        """Completes current prefix using CDPATH"""
        env = builtins.__xonsh_env__
        csc = env.get('CASE_SENSITIVE_COMPLETIONS')
        for cdp in env.get('CDPATH'):
            test_glob = os.path.join(builtins.__xonsh_expand_path__(cdp), prefix) + '*'
            for s in iglobpath(test_glob, ignore_case=(not csc)):
                if os.path.isdir(s):
                    paths.add(os.path.basename(s))

    def cmd_complete(self, cmd):
        """Completes a command name based on what is on the $PATH"""
        space = ' '
        cmdlow = cmd.lower()
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        startswither = startswithnorm if csc else startswithlow
        return {s + space
                for s in self._cmds_cache
                if startswither(s, cmd, cmdlow)}

    def module_complete(self, prefix):
        """Completes a name of a module to import."""
        prefixlow = prefix.lower()
        modules = set(sys.modules.keys())
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        startswither = startswithnorm if csc else startswithlow
        return {s for s in modules if startswither(s, prefix, prefixlow)}

    def _quote_to_use(self, x):
        single = "'"
        double = '"'
        if single in x and double not in x:
            return double
        else:
            return single

    def _quote_paths(self, paths, start, end):
        out = set()
        space = ' '
        backslash = '\\'
        double_backslash = '\\\\'
        slash = get_sep()
        orig_start = start
        orig_end = end
        for s in paths:
            start = orig_start
            end = orig_end
            if (start == '' and
                    (any(i in s for i in CHARACTERS_NEED_QUOTES) or
                     (backslash in s and slash != backslash))):
                start = end = self._quote_to_use(s)
            if os.path.isdir(expand_path(s)):
                _tail = slash
            elif end == '':
                _tail = space
            else:
                _tail = ''
            s = s + _tail
            if end != '':
                if "r" not in start.lower():
                    s = s.replace(backslash, double_backslash)
                elif s.endswith(backslash):
                    s += backslash
            if end in s:
                s = s.replace(end, ''.join('\\%s' % i for i in end))
            out.add(start + s + end)
        return out

    def path_complete(self, prefix, start, end, cdpath=False):
        """Completes based on a path name."""
        tilde = '~'
        paths = set()
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        for s in iglobpath(prefix + '*', ignore_case=(not csc)):
            paths.add(s)
        if tilde in prefix:
            home = os.path.expanduser(tilde)
            paths = {s.replace(home, tilde) for s in paths}
        if cdpath:
            self._add_cdpaths(paths, prefix)
        paths = self._quote_paths({_normpath(s) for s in paths}, start, end)
        self._add_env(paths, prefix)
        self._add_dots(paths, prefix)
        return paths

    def bash_complete(self, prefix, line, begidx, endidx):
        """Attempts BASH completion."""
        splt = line.split()
        cmd = splt[0]
        func = self.bash_complete_funcs.get(cmd, None)
        fnme = self.bash_complete_files.get(cmd, None)
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
                ['bash'], input=script, universal_newlines=True,
                stderr=subprocess.PIPE, env=builtins.__xonsh_env__.detype())
        except subprocess.CalledProcessError:
            out = ''

        rtn = set(out.splitlines())
        return rtn

    @staticmethod
    def _collect_completions_sources():
        sources = []
        paths = (Path(x) for x in
                 builtins.__xonsh_env__.get('BASH_COMPLETIONS', ()))
        for path in paths:
            if path.is_file():
                sources.append('source ' + str(path))
            elif path.is_dir():
                for _file in (x for x in path.glob('*') if x.is_file()):
                    sources.append('source ' + str(_file))
        return sources

    def _load_bash_complete_funcs(self):
        self.bash_complete_funcs = bcf = {}
        inp = self._collect_completions_sources()
        if not inp:
            return
        inp.append('complete -p\n')
        out = self._source_completions(inp)
        for line in out.splitlines():
            head, _, cmd = line.rpartition(' ')
            if len(cmd) == 0 or cmd == 'cd':
                continue
            m = RE_DASHF.search(head)
            if m is None:
                continue
            bcf[cmd] = m.group(1)

    def _load_bash_complete_files(self):
        inp = self._collect_completions_sources()
        if not inp:
            self.bash_complete_files = {}
            return
        if self.bash_complete_funcs:
            inp.append('shopt -s extdebug')
            bash_funcs = set(self.bash_complete_funcs.values())
            inp.append('declare -F ' + ' '.join([f for f in bash_funcs]))
            inp.append('shopt -u extdebug\n')
        out = self._source_completions(inp)
        func_files = {}
        for line in out.splitlines():
            parts = line.split()
            func_files[parts[0]] = parts[-1]
        self.bash_complete_files = {
            cmd: func_files[func]
            for cmd, func in self.bash_complete_funcs.items()
            if func in func_files
        }

    def _source_completions(self, source):
        return subprocess.check_output(
            ['bash'], input='\n'.join(source), universal_newlines=True,
            env=builtins.__xonsh_env__.detype(), stderr=subprocess.DEVNULL)

    def attr_complete(self, prefix, ctx):
        """Complete attributes of an object."""
        attrs = set()
        m = RE_ATTR.match(prefix)
        if m is None:
            return attrs
        expr, attr = m.group(1, 3)
        expr = subexpr_from_unbalanced(expr, '(', ')')
        expr = subexpr_from_unbalanced(expr, '[', ']')
        expr = subexpr_from_unbalanced(expr, '{', '}')
        _ctx = None
        try:
            val = eval(expr, ctx)
            _ctx = ctx
        except:  # pylint:disable=bare-except
            try:
                val = eval(expr, builtins.__dict__)
                _ctx = builtins.__dict__
            except:  # pylint:disable=bare-except
                return attrs  # anything could have gone wrong!
        _opts = dir(val)
        # check whether these options actually work (e.g., disallow 7.imag)
        opts = []
        for i in _opts:
            try:
                eval('{0}.{1}'.format(expr, i), _ctx)
            except:  # pylint:disable=bare-except
                continue
            else:
                opts.append(i)
        if len(attr) == 0:
            opts = [o for o in opts if not o.startswith('_')]
        else:
            csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
            startswither = startswithnorm if csc else startswithlow
            attrlow = attr.lower()
            opts = [o for o in opts if startswither(o, attr, attrlow)]
        prelen = len(prefix)
        for opt in opts:
            a = getattr(val, opt)
            rpl = opt + '(' if callable(a) else opt
            # note that prefix[:prelen-len(attr)] != prefix[:-len(attr)]
            # when len(attr) == 0.
            comp = prefix[:prelen - len(attr)] + rpl
            attrs.add(comp)
        return attrs


OPTIONS_PATH = os.path.expanduser('~') + "/.xonsh_man_completions"
SCRAPE_RE = re.compile(r'^(?:\s*(?:-\w|--[a-z0-9-]+)[\s,])+', re.M)
INNER_OPTIONS_RE = re.compile(r'-\w|--[a-z0-9-]+')


class ManCompleter(object):
    """Helper class that loads completions derived from man pages."""

    def __init__(self):
        self._load_cached_options()

    def __del__(self):
        try:
            self._save_cached_options()
        except Exception:
            pass

    def option_complete(self, prefix, cmd):
        """Completes an option name, basing on content of man page."""
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        startswither = startswithnorm if csc else startswithlow
        if cmd not in self._options.keys():
            try:
                manpage = subprocess.Popen(
                    ["man", cmd], stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL)
                # This is a trick to get rid of reverse line feeds
                text = subprocess.check_output(
                    ["col", "-b"], stdin=manpage.stdout)
                text = text.decode('utf-8')
                scraped_text = ' '.join(SCRAPE_RE.findall(text))
                matches = INNER_OPTIONS_RE.findall(scraped_text)
                self._options[cmd] = matches
            except:
                return set()
        prefixlow = prefix.lower()
        return {s for s in self._options[cmd]
                if startswither(s, prefix, prefixlow)}

    def _load_cached_options(self):
        """Load options from file at startup."""
        try:
            with open(OPTIONS_PATH, 'rb') as f:
                self._options = pickle.load(f)
        except:
            self._options = {}

    def _save_cached_options(self):
        """Save completions to file."""
        with open(OPTIONS_PATH, 'wb') as f:
            pickle.dump(self._options, f)
