"""Directory stack and associated utilities for the xonsh shell.
"""
import os
import builtins
from argparse import ArgumentParser

DIRSTACK = []
"""
A list containing the currently remembered directories.
"""


def pushd(args, stdin=None):
    """
    xonsh command: pushd

    Adds a directory to the top of the directory stack, or rotates the stack,
    making the new top of the stack the current working directory.
    """
    global DIRSTACK

    try:
        args = pushd_parser.parse_args(args)
    except SystemExit:
        return None, None

    env = builtins.__xonsh_env__

    pwd = env['PWD']

    if env.get('PUSHD_MINUS', False):
        BACKWARD = '-'
        FORWARD = '+'
    else:
        BACKWARD = '+'
        FORWARD = '-'

    if args.dir is None:
        try:
            new_pwd = DIRSTACK.pop(0)
        except IndexError:
            e = 'pushd: Directory stack is empty\n'
            return None, e
    elif os.path.isdir(args.dir):
        new_pwd = args.dir
    else:
        try:
            num = int(args.dir[1:])
        except ValueError:
            e = 'Invalid argument to pushd: {0}\n'
            return None, e.format(args.dir)

        if num < 0:
            e = 'Invalid argument to pushd: {0}\n'
            return None, e.format(args.dir)

        if num > len(DIRSTACK):
            e = 'Too few elements in dirstack ({0} elements)\n'
            return None, e.format(len(DIRSTACK))
        elif args.dir.startswith(FORWARD):
            if num == len(DIRSTACK):
                new_pwd = None
            else:
                new_pwd = DIRSTACK.pop(len(DIRSTACK)-1-num)
        elif args.dir.startswith(BACKWARD):
            if num == 0:
                new_pwd = None
            else:
                new_pwd = DIRSTACK.pop(num-1)
        else:
            e = 'Invalid argument to pushd: {0}\n'
            return None, e.format(args.dir)
    if new_pwd is not None:
        o = None
        e = None
        if args.cd:
            DIRSTACK.insert(0, os.path.expanduser(pwd))
            o, e = builtins.default_aliases['cd']([new_pwd], None)
        else:
            DIRSTACK.insert(0, os.path.expanduser(os.path.abspath(new_pwd)))

        if e is not None:
            return None, e

    maxsize = env.get('DIRSTACK_SIZE', 20)
    if len(DIRSTACK) > maxsize:
        DIRSTACK = DIRSTACK[:maxsize]

    if not args.quiet and not env.get('PUSHD_SILENT', False):
        return dirs([], None)

    return None, None


def popd(args, stdin=None):
    """
    xonsh command: popd

    Removes entries from the directory stack.
    """
    global DIRSTACK

    try:
        args = pushd_parser.parse_args(args)
    except SystemExit:
        return None, None

    env = builtins.__xonsh_env__

    if env.get('PUSHD_MINUS', False):
        BACKWARD = '-'
        FORWARD = '+'
    else:
        BACKWARD = '-'
        FORWARD = '+'

    if args.dir is None:
        try:
            new_pwd = DIRSTACK.pop(0)
        except IndexError:
            e = 'popd: Directory stack is empty\n'
            return None, e
    else:
        try:
            num = int(args.dir[1:])
        except ValueError:
            e = 'Invalid argument to popd: {0}\n'
            return None, e.format(args.dir)

        if num < 0:
            e = 'Invalid argument to popd: {0}\n'
            return None, e.format(args.dir)

        if num > len(DIRSTACK):
            e = 'Too few elements in dirstack ({0} elements)\n'
            return None, e.format(len(DIRSTACK))
        elif args.dir.startswith(FORWARD):
            if num == len(DIRSTACK):
                new_pwd = DIRSTACK.pop(0)
            else:
                new_pwd = None
                DIRSTACK.pop(len(DIRSTACK)-1-num)
        elif args.dir.startswith(BACKWARD):
            if num == 0:
                new_pwd = DIRSTACK.pop(0)
            else:
                new_pwd = None
                DIRSTACK.pop(num-1)
        else:
            e = 'Invalid argument to popd: {0}\n'
            return None, e.format(args.dir)

    if new_pwd is not None:
        o = None
        e = None
        if args.cd:
            o, e = builtins.default_aliases['cd']([new_pwd], None)

        if e is not None:
            return None, e

    if not args.quiet and not env.get('PUSHD_SILENT', False):
        return dirs([], None)

    return None, None


def dirs(args, stdin=None):
    """
    xonsh command: dirs

    Displays the list of currently remembered directories.  Can also be used
    to clear the directory stack.
    """
    global DIRSTACK
    dirstack = [os.path.expanduser(builtins.__xonsh_env__['PWD'])] + DIRSTACK

    try:
        args = dirs_parser.parse_args(args)
    except SystemExit:
        return None, None

    env = builtins.__xonsh_env__

    if env.get('PUSHD_MINUS', False):
        BACKWARD = '-'
        FORWARD = '+'
    else:
        BACKWARD = '-'
        FORWARD = '+'

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
        except ValueError:
            e = 'Invalid argument to dirs: {0}\n'
            return None, e.format(N)

        if num < 0:
            e = 'Invalid argument to dirs: {0}\n'
            return None, e.format(len(o))

        if num >= len(o):
            e = 'Too few elements in dirstack ({0} elements)\n'
            return None, e.format(len(o))

        if N.startswith(BACKWARD):
            idx = num
        elif N.startswith(FORWARD):
            idx = len(o)-1-num
        else:
            e = 'Invalid argument to dirs: {0}\n'
            return None, e.format(N)

        out = o[idx]

    return out+'\n', None


pushd_parser = ArgumentParser(prog="pushd")
pushd_parser.add_argument('dir', nargs='?')
pushd_parser.add_argument('-n',
                          dest='cd',
                          help='Suppresses the normal change of directory when'
                          ' adding directories to the stack, so that only the'
                          ' stack is manipulated.',
                          action='store_false')
pushd_parser.add_argument('-q',
                          dest='quiet',
                          help='Do not call dirs, regardless of $PUSHD_SILENT',
                          action='store_true')

popd_parser = ArgumentParser(prog="popd")
popd_parser.add_argument('dir', nargs='?')
popd_parser.add_argument('-n',
                         dest='cd',
                         help='Suppresses the normal change of directory when'
                         ' adding directories to the stack, so that only the'
                         ' stack is manipulated.',
                         action='store_false')
popd_parser.add_argument('-q',
                         dest='quiet',
                         help='Do not call dirs, regardless of $PUSHD_SILENT',
                         action='store_true')

dirs_parser = ArgumentParser(prog="dirs")
dirs_parser.add_argument('N', nargs='?')
dirs_parser.add_argument('-c',
                         dest='clear',
                         help='Clears the directory stack by deleting all of'
                         ' the entries.',
                         action='store_true')
dirs_parser.add_argument('-p',
                         dest='print_long',
                         help='Print the directory stack with one entry per'
                         ' line.',
                         action='store_true')
dirs_parser.add_argument('-v',
                         dest='verbose',
                         help='Print the directory stack with one entry per'
                         ' line, prefixing each entry with its index in the'
                         ' stack.',
                         action='store_true')
dirs_parser.add_argument('-l',
                         dest='long',
                         help='Produces a longer listing; the default listing'
                         ' format uses a tilde to denote the home directory.',
                         action='store_true')
