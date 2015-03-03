"""A (tab-)completer for xonsh."""
from __future__ import print_function, unicode_literals
import os
import re
import sys
import builtins
import subprocess
from glob import glob, iglob

RE_DASHF = re.compile('-F\s+(\w+)')

XONSH_TOKENS = {'and ', 'as ', 'assert ', 'break', 'class ', 'continue', 
    'def ', 'del ', 'elif ', 'else', 'except ', 'finally:', 'for ', 'from ', 
    'global ', 'import ', 'if ', 'in ', 'is ', 'lambda ', 'nonlocal ', 'not ',
    'or ', 'pass', 'raise ', 'return ', 'try:', 'while ', 'with ', 'yield ', 
    '+', '-', '/', '//', '%', '**', '|', '&', '~', '^', '>>', '<<', '<', '<=',
    '>', '>=', '==', '!=', '->', '=', '+=', '-=', '*=', '/=', '%=', '**=', 
    '>>=', '<<=', '&=', '^=', '|=', '//=', ',', ';', ':', '?', '??', '$(', 
    '${', '$[', '..', '...'}

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
        rtn = {s for s in XONSH_TOKENS if s.startswith(prefix)}
        if ctx is not None:
            rtn |= {s for s in ctx if s.startswith(prefix)}
        rtn |= {s for s in dir(builtins) if s.startswith(prefix)}
        rtn |= {s + space for s in builtins.aliases if s.startswith(prefix)}
        if prefix.startswith('$'):
            key = prefix[1:]
            rtn |= {'$'+k for k in builtins.__xonsh_env__ if k.startswith(key)}
        rtn |= {s + (slash if os.path.isdir(s) else space) for s in iglob(prefix + '*')}
        if begidx == 0:
            rtn |= self.cmd_complete(prefix)
        return sorted(rtn)

    def cmd_complete(self, cmd):
        path = builtins.__xonsh_env__.get('PATH', None)
        if path is None:
            return set()
        cmds = set()
        for d in path:
            print(d)
            cmds |= {s for s in os.listdir(d) if s.startswith(cmd)}
        return cmds

    def _load_bash_complete_funcs(self):
        input = 'source /etc/bash_completion\n'
        if os.path.isfile('/usr/share/bash-completion/completions/git'):
            input += 'source /usr/share/bash-completion/completions/git\n'
        input += 'complete -p\n'
        out = subprocess.check_output(['bash'], input=input, 
                                      universal_newlines=True)
        self.bash_complete_funcs = bcf = {}
        for line in out.splitlines():
            head, cmd = line.rsplit(' ', 1)
            if len(cmd) == 0:
                continue
            m = RE_DASHF.search(head)
            if m is None:
                continue
            bcf[cmd] = m.group(1)

    def _load_bash_complete_files(self):
        declare_f = 'declare -F '
        input = ['source /etc/bash_completion']
        if os.path.isfile('/usr/share/bash-completion/completions/git'):
            input.append('source /usr/share/bash-completion/completions/git')
        input.append('shopt -s extdebug')
        input += [declare_f + f for f in self.bash_complete_funcs.values()]
        input.append('shopt -u extdebug\n')
        input = '\n'.join(input)
        out = subprocess.check_output(['bash'], input=input,
                                      universal_newlines=True)
        func_files = {}
        for line in out.splitlines():
            parts = line.split()
            func_files[parts[0]] = parts[-1]
        self.bash_complete_files = {cmd: func_files[func] for cmd, func in 
                                    self.bash_complete_funcs.items()
                                    if func in func_files}
