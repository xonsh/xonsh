import builtins
from xonsh.xoreutils.util import all_builtin_commands, arg_handler

def enable(args, stdin, stdout, stderr):
    opts = _parse_args(args)
    enabled = builtins.__xonsh_enabled_builtin_commands__
    if '--help' in args:
        print(HELP_STR, file=stdout)
        return 0
    if opts['showall'] or opts['print']:
        for i in sorted(all_builtin_commands):
            if i in enabled:
                print('enabled', end=' ', file=stdout)
            else:
                if not opts['showall']:
                    continue
                print('disabled', end=' ', file=stdout)
            print(i, file=stdout)
        return 0
    errors = False
    if opts['disable']:
        for i in args:
            if i not in all_builtin_commands:
                print('enable: {} is not a built-in command!'.format(i), file=stderr)
                errors = True
                continue
            elif i not in enabled:
                print('enable: {} is not enabled!'.format(i), file=stderr)
                errors = True
                continue
            enabled.remove(i)
    else:
        for i in args:
            if i not in all_builtin_commands:
                print('enable: {} is not a built-in command!'.format(i), file=stderr)
                errors = True
                continue
            elif i in enabled:
                print('enable: {} is already enabled!'.format(i), file=stderr)
                errors = True
                continue
            enabled.add(i)
    return int(errors)


def _parse_args(args):
    if '--help' in args:
        return
    out = {'showall': False,
           'disable': False,
           'print': False}

    arg_handler(args, out, '-a', 'showall', True)
    arg_handler(args, out, '-n', 'disable', True)
    arg_handler(args, out, '-p', 'print', True)
    return out

HELP_STR = """Usage: enable [OPTION] [name ...]
Enable or disable buit-in commands

  -a      List each builtin with an indication of whether
          or not it is enabled
  -n      Disable the names listed (otherwise, names are enabled)
  -p      Print a list of enabled shell builtins,
          default if no name arguments appear.
  --help  display this help and exit"""
