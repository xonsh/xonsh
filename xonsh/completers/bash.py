import builtins

import bash_completion


def complete_from_bash(prefix, line, begidx, endidx, ctx):
    """Completes based on results from BASH completion."""
    completers = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    env = builtins.__xonsh_env__.detype()
    return bash_completion.complete_from_bash(prefix, line, begidx, endidx, ctx, env, completers)
