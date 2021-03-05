"""Xonsh hooks into bash completions."""
import builtins

import xonsh.platform as xp
from xonsh.completers.path import _quote_paths
from xonsh.completers.bash_completion import bash_completions
from xonsh.completers.tools import contextual_command_completer, RichCompletion
from xonsh.parsers.completion_context import CommandContext


@contextual_command_completer
def complete_from_bash(context: CommandContext):
    """Completes based on results from BASH completion."""
    env = builtins.__xonsh__.env.detype()  # type: ignore
    paths = builtins.__xonsh__.env.get("BASH_COMPLETIONS", ())  # type: ignore
    command = xp.bash_command()
    # TODO: Allow passing the parsed data directly to py-bash-completion
    args = [arg.raw_value for arg in context.args]
    prefix = context.prefix
    args.insert(context.arg_index, prefix)
    line = " ".join(args)

    # lengths of all args + joining spaces
    begidx = sum(len(a) for a in args[: context.arg_index]) + max(
        context.arg_index - 1, 0
    )
    endidx = begidx + len(prefix)

    comps, lprefix = bash_completions(
        prefix,
        line,
        begidx,
        endidx,
        env=env,
        paths=paths,
        command=command,
        quote_paths=_quote_paths,
    )

    def handle_space(comp: str):
        if comp.endswith(" "):
            return RichCompletion(comp[:-1], append_space=True)
        return comp

    comps = set(map(handle_space, comps))
    return comps, lprefix
