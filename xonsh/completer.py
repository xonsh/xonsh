"""A (tab-)completer for xonsh."""
import os
import re
import builtins
import pickle
import shlex
import subprocess
import sys

from xonsh.built_ins import iglobpath
from xonsh.tools import subexpr_from_unbalanced
from xonsh.tools import ON_WINDOWS


RE_DASHF = re.compile(r'-F\s+(\w+)')
RE_ATTR = re.compile(r'(\S+(\..+)*)\.(\w*)$')
RE_WIN_DRIVE = re.compile(r'^([a-zA-Z]):\\')

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

BASH_COMPLETE_SCRIPT = """source {filename}
COMP_WORDS=({line})
COMP_LINE={comp_line}
COMP_POINT=${{#COMP_LINE}}
COMP_COUNT={end}
COMP_CWORD={n}
{func} {cmd} {prefix} {prev}
for ((i=0;i<${{#COMPREPLY[*]}};i++)) do echo ${{COMPREPLY[i]}}; done
"""

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
        self._path_checksum = None
        self._alias_checksum = None
        self._path_mtime = -1
        self._cmds_cache = frozenset()
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
        """Complete the string s, given a possible execution context.

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
        """
        space = ' '  # intern some strings for faster appending
        slash = '/'
        dot = '.'
        ctx = ctx or {}
        prefixlow = prefix.lower()
        cmd = line.split(' ', 1)[0]
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        startswither = startswithnorm if csc else startswithlow
        if begidx == 0:
            # the first thing we're typing; could be python or subprocess, so
            # anything goes.
            rtn = self.cmd_complete(prefix)
        elif cmd in self.bash_complete_funcs:
            rtn = set()
            for s in self.bash_complete(prefix, line, begidx, endidx):
                if os.path.isdir(s.rstrip()):
                    s = s.rstrip() + slash
                rtn.add(s)
            if len(rtn) == 0:
                rtn = self.path_complete(prefix)
            return sorted(rtn)
        elif prefix.startswith('${') or prefix.startswith('@('):
            # python mode explicitly
            rtn = set()
        elif prefix.startswith('-'):
            return sorted(self._man_completer.option_complete(prefix, cmd))
        elif cmd not in ctx:
            if cmd == 'import' and begidx == len('import '):
                # completing module to import
                return sorted(self.module_complete(prefix))
            if cmd in self._all_commands():
                # subproc mode; do path completions
                return sorted(self.path_complete(prefix, cdpath=True))
            else:
                # if we're here, could be anything
                rtn = set()
        else:
            # if we're here, we're not a command, but could be anything else
            rtn = set()
        rtn |= {s for s in XONSH_TOKENS if startswither(s, prefix, prefixlow)}
        if ctx is not None:
            if dot in prefix:
                rtn |= self.attr_complete(prefix, ctx)
            else:
                rtn |= {s for s in ctx if startswither(s, prefix, prefixlow)}
        rtn |= {s for s in dir(builtins) if startswither(s, prefix, prefixlow)}
        rtn |= {s + space for s in builtins.aliases
                if startswither(s, prefix, prefixlow)}
        rtn |= self.path_complete(prefix)
        return sorted(rtn)

    def _add_env(self, paths, prefix):
        if prefix.startswith('$'):
            csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
            startswither = startswithnorm if csc else startswithlow
            key = prefix[1:]
            keylow = key.lower()
            paths.update({'$' + k for k in builtins.__xonsh_env__ if startswither(k, key, keylow)})

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
            test_glob = os.path.join(cdp, prefix) + '*'
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
                for s in self._all_commands()
                if startswither(s, cmd, cmdlow)}

    def module_complete(self, prefix):
        """Completes a name of a module to import."""
        prefixlow = prefix.lower()
        modules = set(sys.modules.keys())
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        startswither = startswithnorm if csc else startswithlow
        return {s for s in modules if startswither(s, prefix, prefixlow)}

    def path_complete(self, prefix, cdpath=False):
        """Completes based on a path name."""
        space = ' '  # intern some strings for faster appending
        slash = '/'
        tilde = '~'
        paths = set()
        csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
        if prefix.startswith("'") or prefix.startswith('"'):
            prefix = prefix[1:]
        for s in iglobpath(prefix + '*', ignore_case=(not csc)):
            if space in s:
                s = repr(s + (slash if os.path.isdir(s) else ''))
            else:
                s = s + (slash if os.path.isdir(s) else space)
            paths.add(s)
        if tilde in prefix:
            home = os.path.expanduser(tilde)
            paths = {s.replace(home, tilde) for s in paths}
        self._add_env(paths, prefix)
        self._add_dots(paths, prefix)
        if cdpath:
            self._add_cdpaths(paths, prefix)
        return {_normpath(s) for s in paths}

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

        script = BASH_COMPLETE_SCRIPT.format(filename=fnme,
                                             line=' '.join(shlex.quote(p) for p in splt),
                                             comp_line=shlex.quote(line),
                                             n=n,
                                             func=func,
                                             cmd=cmd,
                                             end=endidx + 1,
                                             prefix=prefix,
                                             prev=shlex.quote(prev))
        try:
            out = subprocess.check_output(['bash'],
                                          input=script,
                                          universal_newlines=True,
                                          stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            out = ''

        space = ' '
        rtn = {s + space if s[-1:].isalnum() else s for s in out.splitlines()}
        return rtn

    def _source_completions(self):
        srcs = []
        for f in builtins.__xonsh_env__.get('BASH_COMPLETIONS'):
            if os.path.isfile(f):
                # We need to "Unixify" Windows paths for Bash to understand
                if ON_WINDOWS:  
                    f = RE_WIN_DRIVE.sub(lambda m: '/{0}/'.format(m.group(1).lower()), f).replace('\\', '/')
                srcs.append('source ' + f)
        return srcs

    def _load_bash_complete_funcs(self):
        self.bash_complete_funcs = bcf = {}
        inp = self._source_completions()
        if len(inp) == 0:
            return
        inp.append('complete -p\n')
        out = subprocess.check_output(['bash'], input='\n'.join(inp),
                                      universal_newlines=True)
        for line in out.splitlines():
            head, cmd = line.rsplit(' ', 1)
            if len(cmd) == 0 or cmd == 'cd':
                continue
            m = RE_DASHF.search(head)
            if m is None:
                continue
            bcf[cmd] = m.group(1)

    def _load_bash_complete_files(self):
        inp = self._source_completions()
        if len(inp) == 0:
            self.bash_complete_files = {}
            return
        if self.bash_complete_funcs:
            inp.append('shopt -s extdebug')
            bash_funcs = set(self.bash_complete_funcs.values())
            inp.append('declare -F ' + ' '.join([f for f in bash_funcs]))
            inp.append('shopt -u extdebug\n')
        out = subprocess.check_output(['bash'], input='\n'.join(inp),
                                      universal_newlines=True)
        func_files = {}
        for line in out.splitlines():
            parts = line.split()
            func_files[parts[0]] = parts[-1]
        self.bash_complete_files = {
            cmd: func_files[func]
            for cmd, func in self.bash_complete_funcs.items()
            if func in func_files
        }

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
        try:
            val = builtins.evalx(expr, glbs=ctx)
        except:  # pylint:disable=bare-except
            try:
                val = builtins.evalx(expr, glbs=builtins.__dict__)
            except:  # pylint:disable=bare-except
                return attrs  # anything could have gone wrong!
        opts = dir(val)
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

    def _all_commands(self):
        path = builtins.__xonsh_env__.get('PATH', [])
        # did PATH change?
        path_hash = hash(tuple(path))
        cache_valid = path_hash == self._path_checksum
        self._path_checksum = path_hash
        # did aliases change?
        al_hash = hash(tuple(sorted(builtins.aliases.keys())))
        self._alias_checksum = al_hash
        cache_valid = cache_valid and al_hash == self._alias_checksum
        pm = self._path_mtime
        # did the contents of any directory in PATH change?
        for d in filter(os.path.isdir, path):
            m = os.stat(d).st_mtime
            if m > pm:
                pm = m
                cache_valid = False
        self._path_mtime = pm
        if cache_valid:
            return self._cmds_cache
        allcmds = set()
        for d in filter(os.path.isdir, path):
            allcmds |= set(os.listdir(d))
        allcmds |= set(builtins.aliases.keys())
        self._cmds_cache = frozenset(allcmds)
        return self._cmds_cache


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
                manpage = subprocess.Popen(["man", cmd],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL)
                # This is a trick to get rid of reverse line feeds
                text = subprocess.check_output(["col", "-b"],
                                               stdin=manpage.stdout)
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
