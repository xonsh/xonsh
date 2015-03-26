"""A (tab-)completer for xonsh."""
from __future__ import print_function, unicode_literals
import os
import re
import sys
import builtins
import subprocess
from glob import iglob

from xonsh.built_ins import iglobpath

RE_DASHF = re.compile(r'-F\s+(\w+)')

XONSH_TOKENS = {'and ', 'as ', 'assert ', 'break', 'class ', 'continue', 
    'def ', 'del ', 'elif ', 'else', 'except ', 'finally:', 'for ', 'from ', 
    'global ', 'import ', 'if ', 'in ', 'is ', 'lambda ', 'nonlocal ', 'not ',
    'or ', 'pass', 'raise ', 'return ', 'try:', 'while ', 'with ', 'yield ', 
    '+', '-', '/', '//', '%', '**', '|', '&', '~', '^', '>>', '<<', '<', '<=',
    '>', '>=', '==', '!=', '->', '=', '+=', '-=', '*=', '/=', '%=', '**=', 
    '>>=', '<<=', '&=', '^=', '|=', '//=', ',', ';', ':', '?', '??', '$(', 
    '${', '$[', '..', '...'}

BASH_COMPLETE_SCRIPT = """source {filename}
COMP_WORDS=({line})
COMP_LINE="{line}"
COMP_POINT=${{#COMP_LINE}}
COMP_COUNT={end}
COMP_CWORD={n}
{func} {cmd} {prefix} {prev}
for ((i=0;i<${{#COMPREPLY[*]}};i++)) do echo ${{COMPREPLY[i]}}; done
"""

class Completer(object):
    """This provides a list of optional completions for the xonsh shell."""

    def __init__(self):
        try:
            # FIXME this could be threaded for faster startup times
            self._load_bash_complete_funcs()
            # or we could make this lazy
            self._load_bash_complete_files()
            self.have_bash = True
        except subprocess.CalledProcessError:
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
        if begidx == 0:
            rtn = self.cmd_complete(prefix)
        elif line.split(' ', 1)[0] in self.bash_complete_funcs:
            rtn = set()
            for s in self.bash_complete(prefix, line, begidx, endidx):
                if os.path.isdir(s.rstrip()):
                    s = s.rstrip() + slash
                rtn.add(s)
            if len(rtn) == 0:
                rtn = self.path_complete(prefix)
            return sorted(rtn)
        else:
            rtn = set()
        rtn |= {s for s in XONSH_TOKENS if s.startswith(prefix)}
        if ctx is not None:
            rtn |= {s for s in ctx if s.startswith(prefix)}
        rtn |= {s for s in dir(builtins) if s.startswith(prefix)}
        rtn |= {s + space for s in builtins.aliases if s.startswith(prefix)}
        if prefix.startswith('$'):
            key = prefix[1:]
            rtn |= {'$'+k for k in builtins.__xonsh_env__ if k.startswith(key)}
        rtn |= self.path_complete(prefix)
        return sorted(rtn)

    def cmd_complete(self, cmd):
        """Completes a command name based on what is on the $PATH"""
        path = builtins.__xonsh_env__.get('PATH', None)
        if path is None:
            return set()
        cmds = set()
        space = ' '
        for d in path:
            if os.path.isdir(d):
                cmds |= {s + space for s in os.listdir(d) if s.startswith(cmd)}
        return cmds

    def path_complete(self, prefix):
        """Completes based on a path name."""
        space = ' '  # intern some strings for faster appending
        slash = '/'
        tilde = '~'
        paths = set()
        if prefix.startswith("'") or prefix.startswith('"'):
            prefix = prefix[1:]
        for s in iglobpath(prefix + '*'):
            if space in s:
                s = repr(s + (slash if os.path.isdir(s) else ''))
            else:
                s = s + (slash if os.path.isdir(s) else space)
            paths.add(s)
        if tilde in prefix:
            home = os.path.expanduser(tilde)
            paths = {s.replace(home, tilde) for s in paths}
        return paths

    def bash_complete(self, prefix, line, begidx, endidx):
        """Attempts BASH completion."""
        splt = line.split()
        cmd = splt[0]
        func = self.bash_complete_funcs.get(cmd, None)
        fnme = self.bash_complete_files.get(cmd, None)
        if func is None or fnme is None:
            return set()
        idx = 0
        for n, tok in enumerate(splt):
            if tok == prefix:
                idx = line.find(prefix, idx)
                if idx >= begidx:
                    break
            prev = tok
        if len(prefix) == 0:
            prefix = '""'
            n += 1
        script = BASH_COMPLETE_SCRIPT.format(filename=fnme, line=line, n=n,
                    func=func, cmd=cmd, end=endidx+1, prefix=prefix, prev=prev)
        out = subprocess.check_output(['bash'], input=script,
                                      universal_newlines=True, 
                                      stderr=subprocess.PIPE)
        space = ' '
        rtn = {s+space if s[-1:].isalnum() else s for s in out.splitlines()}
        return rtn

    def _source_completions(self):
        srcs = []
        for f in builtins.__xonsh_env__.get('BASH_COMPLETIONS', ()):
            if os.path.isfile(f):
                srcs.append('source ' + f)
        return srcs

    def _load_bash_complete_funcs(self):
        self.bash_complete_funcs = bcf = {}
        input = self._source_completions()
        if len(input) == 0:
            return
        input.append('complete -p\n')
        out = subprocess.check_output(['bash'], input='\n'.join(input), 
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
        input = self._source_completions()
        if len(input) == 0:
            self.bash_complete_files = {}
            return
        input.append('shopt -s extdebug')
        declare_f = 'declare -F '
        input += [declare_f + f for f in self.bash_complete_funcs.values()]
        input.append('shopt -u extdebug\n')
        out = subprocess.check_output(['bash'], input='\n'.join(input),
                                      universal_newlines=True)
        func_files = {}
        for line in out.splitlines():
            parts = line.split()
            func_files[parts[0]] = parts[-1]
        self.bash_complete_files = {cmd: func_files[func] for cmd, func in 
                                    self.bash_complete_funcs.items()
                                    if func in func_files}
