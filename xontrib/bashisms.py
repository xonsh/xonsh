"""Bash-like interface extensions for xonsh."""
import shlex
import sys
import re

from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition, EmacsInsertMode, ViInsertMode

from xonsh.platform import ptk_shell_type

__all__ = ()


@events.on_transform_command
def bash_preproc(cmd, **kw):
    bang_previous = {
        "!": lambda x: x,
        "$": lambda x: shlex.split(x)[-1],
        "^": lambda x: shlex.split(x)[0],
        "*": lambda x: " ".join(shlex.split(x)[1:]),
    }

    def replace_bang(m):
        arg = m.group(1)
        inputs = __xonsh__.history.inps

        # Dissect the previous command.
        if arg in bang_previous:
            try:
                return bang_previous[arg](inputs[-1])
            except IndexError:
                print("xonsh: no history for '!{}'".format(arg))
                return ""

        # Look back in history for a matching command.
        else:
            try:
                return next((x for x in reversed(inputs) if x.startswith(arg)))
            except StopIteration:
                print("xonsh: no previous commands match '!{}'".format(arg))
                return ""

    return re.sub(r"!([!$^*]|[\w]+)", replace_bang, cmd.strip())


@events.on_ptk_create
def custom_keybindings(bindings, **kw):
    if ptk_shell_type() == "prompt_toolkit2":
        handler = bindings.add
    else:
        handler = bindings.registry.add_binding

    insert_mode = ViInsertMode() | EmacsInsertMode()

    @Condition
    def last_command_exists():
        return len(__xonsh__.history) > 0

    @handler(Keys.Escape, ".", filter=last_command_exists & insert_mode)
    def recall_last_arg(event):
        arg = __xonsh__.history[-1].cmd.split()[-1]
        event.current_buffer.insert_text(arg)


def alias(args, stdin=None):
    ret = 0

    if args:
        for arg in args:
            if "=" in arg:
                # shlex.split to remove quotes, e.g. "foo='echo hey'" into
                # "foo=echo hey"
                name, cmd = shlex.split(arg)[0].split("=", 1)
                aliases[name] = shlex.split(cmd)
            elif arg in aliases:
                print("{}={}".format(arg, aliases[arg]))
            else:
                print("alias: {}: not found".format(arg), file=sys.stderr)
                ret = 1
    else:
        for alias, cmd in aliases.items():
            print("{}={}".format(alias, cmd))

    return ret


aliases["alias"] = alias
