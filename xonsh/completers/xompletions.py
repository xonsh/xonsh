

def complete_xonfig(prefix, line, start, end, ctx):
    """Completion for ``xonfig``"""
    args = line.split(' ')
    if len(args) == 0 or args[0] != 'xonfig':
        return None
    curix = args.index(prefix)
    if curix == 1:
        possible = {'info', 'wizard', 'styles', 'colors', '-h'}
    return {i for i in possible if i.startswith(prefix)}
