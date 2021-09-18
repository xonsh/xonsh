"""Completers for pip."""

import re
import shlex
import subprocess

import xonsh.lazyasd as xl
from xonsh.completers.tools import (
    contextual_command_completer,
    get_filter_function,
    RichCompletion,
)
from xonsh.parsers.completion_context import CommandContext


@xl.lazyobject
def PIP_RE():
    return re.compile(r"\bx?pip(?:\d|\.)*$")


@contextual_command_completer
def complete_pip(context: CommandContext):
    """Completes python's package manager pip."""
    prefix = context.prefix
    if context.arg_index == 0 or (not PIP_RE.search(context.args[0].value)):
        return None
    filter_func = get_filter_function()

    args = [arg.raw_value for arg in context.args]
    try:
        proc = subprocess.run(
            [args[0]],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            env={
                "PIP_AUTO_COMPLETE": "1",
                "COMP_WORDS": " ".join(args),
                "COMP_CWORD": str(len(context.args)),
            },
        )
    except FileNotFoundError:
        return None

    if proc.stdout:
        out = shlex.split(proc.stdout.decode())
        for cmp in out:
            if filter_func(cmp, prefix):
                yield RichCompletion(cmp, append_space=True)

    return None
