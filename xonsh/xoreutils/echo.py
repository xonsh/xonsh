def echo(args, stdin, stdout, stderr, controller):
    opts = _parse_args(args)
    if opts is None:
        return

    ender = opts['end']

    args = map(str, args)
    if opts['escapes']:
        args = map(lambda x: x.encode().decode('unicode_escape'), args)

    print(*args, end=ender, file=stdout)


def _parse_args(args):
    out = {'escapes': False, 'end': '\n'}
    if '-e' in args:
        args.remove('-e')
        out['escapes'] = True
    if '-E' in args:
        args.remove('-E')
        out['escapes'] = False
    if '-n' in args:
        args.remove('-n')
        out['end'] = ''
    return out
