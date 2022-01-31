from xonsh.completers import completer
from xonsh.completers.tools import complete_from_sub_proc, contextual_command_completer
from xonsh.parsers.completion_context import CommandContext


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

    yield from complete_from_sub_proc(
        "fish",
        "-c",
        "; ".join(script_lines),
    )


completer.add_one_completer("fish", fish_proc_completer, "<bash")
