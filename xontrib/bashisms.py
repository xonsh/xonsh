"""Bash-like interface extensions for xonsh."""
import shlex
import sys
import re
import builtins


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

    return re.sub(r"!([!$^*]|[\w]+)", replace_bang, cmd)


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
builtins.__xonsh__.env["THREAD_SUBPROCS"] = False
