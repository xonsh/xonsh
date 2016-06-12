import builtins


def complete_completer(prefix, line, start, end, ctx):
    """
    Completion for "completer"
    """
    args = line.split(' ')
    if len(args) == 0 or args[0] != 'completer':
        return None
    curix = args.index(prefix)
    compnames = set(builtins.__xonsh_completers__.keys())
    if curix == 1:
        possible = {'list', 'help', 'add', 'remove'}
    elif curix == 2:
        if args[1] == 'help':
            possible = {'list', 'add', 'remove'}
        elif args[1] == 'remove':
            possible = compnames
        else:
            raise StopIteration
    else:
        if args[1] != 'add':
            raise StopIteration
        if curix == 3:
            possible = {i
                        for i, j in builtins.__xonsh_ctx__.items()
                        if callable(j)}
        elif curix == 4:
            possible = ({'start', 'end'} |
                        {'>' + n for n in compnames} |
                        {'<' + n for n in compnames})
        else:
            raise StopIteration
    return {i for i in possible if i.startswith(prefix)}
