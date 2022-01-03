from xonsh.completers import completer
from xonsh.completers.tools import RichCompletion, contextual_command_completer
import os
import subprocess as sp
from xonsh.built_ins import XSH
from xonsh.parsers.completion_context import CommandContext


def create_rich_completion(line: str, append_space=False):
    line = line.strip()
    if "\t" in line:
        cmd, desc = map(str.strip, line.split("\t", maxsplit=1))
    else:
        cmd, desc = line, ""

    # special treatment for path completions.
    # not appending space even if it is a single candidate.
    if cmd.endswith(os.pathsep):
        append_space = False

    return RichCompletion(
        cmd,
        description=desc,
        append_space=append_space,
    )


@contextual_command_completer
def fish_proc_completer(ctx: CommandContext):
    """Populate completions using fish shell and remove bash-completer"""
    if not ctx.args:
        return
    line = ctx.text_before_cursor

    script_lines = [
        f"complete --no-files {ctx.command}",  # switch off basic file completions for the executable
        f"complete -C '{line}'",
    ]
    args = ["fish", "-c", "; ".join(script_lines)]
    env = XSH.env.detype()
    try:
        output = sp.check_output(args, env=env, stderr=sp.DEVNULL).decode()
    except Exception as ex:
        print(f"Failed to get fish-completions: {ex}")
        return

    if output:
        lines = output.strip().splitlines(keepends=False)
        # if there is a single completion candidate then maybe it is over
        append_space = len(lines) == 1
        for line in lines:
            comp = create_rich_completion(line, append_space)
            yield comp


completer.add_one_completer("fish", fish_proc_completer, "<bash")
