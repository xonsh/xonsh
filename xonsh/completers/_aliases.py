import builtins

from collections import OrderedDict

from xonsh.completers.tools import justify


def _add_one_completer(name, func, loc='end'):
    new = OrderedDict()
    if loc == 'start':
        new[name] = func
        for (k, v) in builtins.__xonsh_completers__.items():
            new[k] = v
    elif loc == 'end':
        for (k, v) in builtins.__xonsh_completers__.items():
            new[k] = v
        new[name] = func
    else:
        dir, rel = loc[0], loc[1:]
        found = False
        for (k, v) in builtins.__xonsh_completers__.items():
            if rel == k and dir == '<':
                new[name] = func
                found = True
            new[k] = v
            if rel == k and dir == '>':
                new[name] = func
                found = True
        if not found:
            new[name] = func
    builtins.__xonsh_completers__.clear()
    builtins.__xonsh_completers__.update(new)


def list_completers(args, stdin=None):
    o = "Registered Completer Functions: \n"
    _comp = builtins.__xonsh_completers__
    ml = max(len(i) for i in _comp)
    _strs = []
    for c in _comp:
        doc = _comp[c].__doc__ or 'No description provided'
        doc = justify(doc, 80, 7 + ml)
        padding = ' ' * (2 + ml - len(c))
        _strs.append('%s%r : %s' % (padding, c, doc))
    return o + '\n'.join(_strs) + '\n'


def remove_completer(args, stdin=None):
    err = None
    if len(args) != 1:
        err = "remove-completer takes exactly 1 argument."
    else:
        name = args[0]
        if name not in builtins.__xonsh_completers__:
            err = ("The name %s is not a registered "
                   "completer function.") % name
    if err is None:
        del builtins.__xonsh_completers__[name]
        return
    else:
        return None, err + '\n', 1


def register_completer(args, stdin=None):
    err = None
    if '--help' in args or '-h' in args:
        return _register_help_str
    if len(args) not in {2, 3}:
        err = ("register-completer takes either 2 or 3 arguments.\n"
               "For help, run:  register-completer --help")
    else:
        name = args[0]
        func = args[1]
        if name in builtins.__xonsh_completers__:
            err = ("The name %s is already a registered "
                   "completer function.") % name
        else:
            if func in builtins.__xonsh_ctx__:
                if not callable(builtins.__xonsh_ctx__[func]):
                    err = "%s is not callable" % func
            else:
                err = "No such function: %s" % func
    if err is None:
        position = "end" if len(args) == 2 else args[2]
        func = builtins.__xonsh_ctx__[func]
        _add_one_completer(name, func, position)
    else:
        return None, err + '\n', 1

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
