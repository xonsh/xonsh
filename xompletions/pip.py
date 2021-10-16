"""Completers for pip."""
import shlex
import subprocess

from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    get_filter_function,
    RichCompletion,
)
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(context: CommandContext):
    """Completes python's package manager pip."""
    prefix = context.prefix

    filter_func = get_filter_function()

    args = [arg.raw_value for arg in context.args]
    env = XSH.env.detype()
    env.update(
        {
            "PIP_AUTO_COMPLETE": "1",
            "COMP_WORDS": " ".join(args),
            "COMP_CWORD": str(len(context.args)),
        }
    )

    try:
        proc = subprocess.run(
            [args[0]],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError:
        return None

    if proc.stdout:
        out = shlex.split(proc.stdout.decode())
        for cmp in out:
            if filter_func(cmp, prefix):
                yield RichCompletion(cmp, append_space=True)

    return None
