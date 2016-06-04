import builtins

from collections import OrderedDict

from xonsh.completers.tools import justify

VALID_ACTIONS = frozenset({'add', 'remove', 'list'})

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
        direction, rel = loc[0], loc[1:]
        found = False
        for (k, v) in builtins.__xonsh_completers__.items():
            if rel == k and direction == '<':
                new[name] = func
                found = True
            new[k] = v
            if rel == k and direction == '>':
                new[name] = func
                found = True
        if not found:
            new[name] = func
    builtins.__xonsh_completers__.clear()
    builtins.__xonsh_completers__.update(new)


def _list_completers(args, stdin=None):
    o = "Registered Completer Functions: \n"
    _comp = builtins.__xonsh_completers__
    ml = max(len(i) for i in _comp)
    _strs = []
    for c in _comp:
        doc = ' '.join(_comp[c].__doc__.split()) or 'No description provided'
        doc = justify(doc, 80, ml + 3)
        _strs.append('{: >{}} : {}'.format(c, ml, doc))
    return o + '\n'.join(_strs) + '\n'


def _remove_completer(args, stdin=None):
    err = None
    if len(args) != 1:
        err = "completer remove takes exactly 1 argument."
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


def _register_completer(args, stdin=None):
    err = None
    if len(args) not in {2, 3}:
        err = ("completer add takes either 2 or 3 arguments.\n"
               "For help, run:  completer help add")
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
        position = "start" if len(args) == 2 else args[2]
        func = builtins.__xonsh_ctx__[func]
        _add_one_completer(name, func, position)
    else:
        return None, err + '\n', 1


def completer_alias(args, stdin=None):
    err = None
    if len(args) == 0 or args[0] not in (VALID_ACTIONS | {'help'}):
        err = ('Please specify an action.  Valid actions are: '
               '"add", "remove", "list", or "help".')
    elif args[0] == 'help':
        if len(args) == 1 or args[1] not in VALID_ACTIONS:
            return ('Valid actions are: add, remove, list.  For help with a '
                    'specific action, run: completer help ACTION\n')
        elif args[1] == 'add':
            return COMPLETER_ADD_HELP_STR
        elif args[1] == 'remove':
            return COMPLETER_REMOVE_HELP_STR
        elif args[1] == 'list':
            return COMPLETER_LIST_HELP_STR

    if err is not None:
        return None, err + '\n', 1

    if args[0] == 'add':
        func = _register_completer
    elif args[0] == 'remove':
        func = _remove_completer
    elif args[0] == 'list':
        func = _list_completers
    return func(args[1:], stdin=stdin)

COMPLETER_LIST_HELP_STR = """
completer list: list the active completers, in order

Usage:
    completer remove
""".lstrip()

COMPLETER_REMOVE_HELP_STR = """
completer remove: removes a completer from xonsh

Usage:
    completer remove NAME

NAME is a unique name of a completer (run "completer list" to see the current
     completers in order)
""".lstrip()

COMPLETER_ADD_HELP_STR = """
completer add: adds a new completer to xonsh

Usage:
    completer add NAME FUNC [POS]

NAME is a unique name to use in the listing (run "completer list" to see the
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

     If POS is not provided, the default value is "start"
""".lstrip()
