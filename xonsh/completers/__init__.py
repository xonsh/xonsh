from collections import OrderedDict

from xonsh.completers.man import complete_from_man
from xonsh.completers.bash import complete_from_bash
from xonsh.completers.base import complete_base
from xonsh.completers.path import complete_path
from xonsh.completers.dirs import complete_cd, complete_rmdir
from xonsh.completers.python import complete_python, complete_import
from xonsh.completers.commands import complete_skipper

completers = OrderedDict()
completers['base'] = complete_base
completers['skip'] = complete_skipper
completers['cd'] = complete_cd
completers['rmdir'] = complete_cd
completers['bash'] = complete_from_bash
completers['man'] = complete_from_man
completers['import'] = complete_import
completers['python'] = complete_python
completers['path'] = complete_path


def _add_one_completer(name, func, loc='end'):
    new = OrderedDict()
    if loc == 'start':
        new[name] = func
        for (k,v) in dict.iteritems():
            new[k] = v
    elif loc == 'end':
        for (k,v) in dict.iteritems():
            new[k] = v
        new[name] = func
    else:
        dir, rel = loc[0], loc[1:]
        found = False
        for (k, v) in dict.iteritems():
            if rel == k and dir == '<':
                new[name] = func
                found = True
            new[k] = v
            if rel == k and dir == '>':
                new[name] = func
                found = True
        if not found:
            new[name] = func
    return new


def list_completers(args, stdin=None):
    o = "Registered Completer Functions: \n"
    _strs = ('  %s' % (ix+1, c) for ix, c in enumerate(all_completers))
    return o + '\n'.join(_strs)


def register_completer(args, stdin=None):
    err = None
    if '--help' in args or '-h' in args:
        return _register_help_str
    if len(args) not in {2, 3}:
        err = "register-completer takes either 2 or 3 arguments."
    else:
        name = args[0]
        func = args[1]
        if name in completers:
            err = ("The name %s is already a registered "
                   "completer function.") % name
        else:
            if (func in builtins.__xonsh_env__ and
                    not callable(builtins.__xonsh_env__[func])):
                err = "%s is not callable" % func
            else:
                err = "No such function: %s" % func
    if err is None:
        position = "end" if len(args) == 2 else args[2]
        func = builtins.__xonsh_env__[func]
        all_completers = _add_one_completer(name, func, position)
    else:
        return None, err, 1

_register_help_str = """
register-completer: adds a new completer to xonsh

Usage:
    register-completer NAME FUNC [POS]

NAME is a unique name to use in the listing (run list-completers to see the
     current completers in order)

FUNC is the name of a completer function to use.  This should be a function
     of the following arguments, and should return a set of valid completions
     for the given prefix.  If this completer should not be used in a given
     context, it should return an empty set or None.

     Arguments to FUNC:
       * prefix: the string to be matched
       * line: a string representing the whole current line, for context
       * begidx: the index at which prefix starts in line
       * endidx: the index at which prefix ends in line
       * ctx: the current Python environment

     If the completer expands the prefix in any way, it should return a tuple
     of two elements: the first should be the set of completions, and the
     second should be the length of the modified prefix (for an example, see
     xonsh.completers.path.complete_path).

POS (optional) is a position into the list of completers at which the new
     completer should be added.  It can be one of the following values:
       * "start" indicates that the completer should be added to the start of
                 the list of completers (it should be run before all others)
       * "end" indicates that the completer should be added to the end of the
               list of completers (it should be run after all others)
       * ">KEY", where KEY is a pre-existing name, indicates that this should
                 be added after the completer named KEY
       * "<KEY", where KEY is a pre-existing name, indicates that this should
                 be added before the completer named KEY
"""
