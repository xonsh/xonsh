from xonsh.completers import completer
from xonsh.completers.tools import RichCompletion, contextual_command_completer

import subprocess as sp
from xonsh.built_ins import XSH
from xonsh.parsers.completion_context import CommandContext


def create_rich_completion(line: str):
    line = line.strip()
    if "\t" in line:
        cmd, desc = map(str.strip, line.split("\t", maxsplit=1))
    else:
        cmd, desc = line, ""
    return RichCompletion(
        str(cmd),
        description=str(desc),
        append_space=True,
    )


@contextual_command_completer
def fish_proc_completer(ctx: CommandContext):
    """Populate completions using fish shell and remove bash-completer"""
    args = [arg.value for arg in ctx.args] + [ctx.prefix]
    line = " ".join(args)
    args = ["fish", "-c", f"complete -C '{line}'"]
    env = XSH.env.detype()
    output = sp.check_output(args, env=env).decode()
    if output:
        yield from map(
            create_rich_completion, output.strip().splitlines(keepends=False)
        )


completer.add_one_completer("fish", fish_proc_completer, "<bash")
