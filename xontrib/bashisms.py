"""Bash-like interface extensions for xonsh."""
import shlex
import sys

from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode

from xonsh.platform import ptk_shell_type

__all__ = ()


@events.on_transform_command
def bash_preproc(cmd, **kw):
    if not __xonsh__.history.inps:
        if cmd.strip() == '!!':
            return ''
        return cmd
    return cmd.replace('!!', __xonsh__.history.inps[-1].strip())


@events.on_ptk_create
def custom_keybindings(bindings, **kw):
    if ptk_shell_type() == 'prompt_toolkit2':
        handler = bindings.add
    else:
        handler = bindings.registry.add_binding

    insert_mode = ViInsertMode() | EmacsInsertMode()

    @Condition
    def last_command_exists():
        return len(__xonsh__.history) > 0

    @handler(Keys.Escape, '.', filter=last_command_exists & insert_mode)
    def recall_last_arg(event):
        arg = __xonsh__.history[-1].cmd.split()[-1]
        event.current_buffer.insert_text(arg)


def alias(args, stdin=None):
    ret = 0

    if args:
        for arg in args:
            if '=' in arg:
                # shlex.split to remove quotes, e.g. "foo='echo hey'" into
                # "foo=echo hey"
                name, cmd = shlex.split(arg)[0].split('=', 1)
                aliases[name] = shlex.split(cmd)
            elif arg in aliases:
                print('{}={}'.format(arg, aliases[arg]))
            else:
                print("alias: {}: not found".format(arg), file=sys.stderr)
                ret = 1
    else:
        for alias, cmd in aliases.items():
            print('{}={}'.format(alias, cmd))

    return ret


aliases['alias'] = alias
