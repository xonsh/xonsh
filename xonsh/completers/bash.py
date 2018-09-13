"""Xonsh hooks into bash completions."""
import builtins

import xonsh.platform as xp
from xonsh.completers.path import _quote_paths
from xonsh.completers.bash_completion import bash_completions


def complete_from_bash(prefix, line, begidx, endidx, ctx):
    """Completes based on results from BASH completion."""
    env = builtins.__xonsh__.env.detype()
    paths = builtins.__xonsh__.env.get("BASH_COMPLETIONS", ())
    command = xp.bash_command()
    return bash_completions(
        prefix,
        line,
        begidx,
        endidx,
        env=env,
        paths=paths,
        command=command,
        quote_paths=_quote_paths,
    )
