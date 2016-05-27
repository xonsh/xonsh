import importlib

from xonsh.xoreutils.util import all_builtin_commands

_cmd_names = {'cat', 'pwd', 'tee', 'tty', 'yes', 'echo', 'which', 'enable'}

for i in _cmd_names:
    cmd = importlib.import_module('xonsh.xoreutils.%s' % i)
    all_builtin_commands[i] = getattr(cmd, i)
