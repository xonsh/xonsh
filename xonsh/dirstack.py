import os
import builtins

from argparse import ArgumentParser

DIRSTACK = []

def get_dirstack():
    global DIRSTACK
    return [builtins.__xonsh_env__['PWD']] + DIRSTACK

def set_dirstack(x):
    global DIRSTACK
    DIRSTACK = DIRSTACK[1:]

pushd_parser = ArgumentParser(description="pushd: push onto the directory stack")
def pushd(args, stdin=None):
    dirstack = get_dirstack()
    return None, None

popd_parser = ArgumentParser(description="popd: pop from the directory stack")
def popd(args, stdin=None):
    dirstack = get_dirstack()
    return None, None


def dirs(args, stdin=None):
    dirstack = get_dirstack()

    try:
        args = dirs_parser.parse_args(args)
    except SystemExit:
        return None, None

    if args.clear:
        dirstack = []
        return None, None

    if args.long:
        o = dirstack
    else:
        d = os.path.expanduser('~')
        o = [i.replace(d, '~') for i in dirstack]

    if args.verbose:
        out = ''
        pad = len(str(len(o)-1))
        for (ix, e) in enumerate(o):
            blanks = ' ' * (pad - len(str(ix)))
            out += '\n{0}{1} {2}'.format(blanks, ix, e)
        out = out[1:]
    elif args.print_long:
        out = '\n'.join(o)
    else:
        out = ' '.join(o)

    N = args.N
    if N is not None:
        try:
            num = int(N[1:])
        except:
            return None, 'Invalid argument to dirs: {0}\n'.format(N)
        if num >= len(o):
            e = 'Too few elements in dirstack ({1} elements)\n'.format(len(o))
            return None, e 
        if N.startswith('-'):
            idx = num
        elif N.startswith('+'):
            idx  = len(o)-1-num
        else:
            return None, 'Invalid argument to dirs: {0}\n'.format(N)

        out = o[idx]

    return out+'\n', None


dirs_parser = ArgumentParser(description="dirs: view and manipulate the directory stack", )
dirs_parser.add_argument('-c',
        dest='clear',
        help='Clears the directory stack by deleting all of the entries',
        action='store_true')
dirs_parser.add_argument('-p',
        dest='print_long',
        help='Print the directory stack with one entry per line.',
        action='store_true')
dirs_parser.add_argument('-v',
        dest='verbose',
        help='Print the directory stack with one entry per line, prefixing each entry with its index in the stack.',
        action='store_true')
dirs_parser.add_argument('-l',
        dest='long',
        help='Produces a longer listing; the default listing format uses a tilde to denote the home directory.',
        action='store_true')
dirs_parser.add_argument('N', nargs='?')

