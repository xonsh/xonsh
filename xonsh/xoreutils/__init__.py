import importlib

from xonsh.xoreutils.util import all_builtin_commands

cmd_names = {'cat', 'pwd', 'tee', 'tty', 'yes', 'echo', 'which',
             'enable'}


for i in cmd_names:
    cmd = importlib.__import__('xonsh.xoreutils.%s' % i, globals(), locals(), [i], 0)
    all_builtin_commands[i] = getattr(cmd, i)
