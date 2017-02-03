import builtins

from xonsh.completers.bash_completion import get_completions


def complete_from_bash(prefix, line, begidx, endidx, ctx):
    """Completes based on results from BASH completion."""
    completers = builtins.__xonsh_env__.get('BASH_COMPLETIONS', ())
    env = builtins.__xonsh_env__.detype()
    return get_completions(prefix, line, begidx, endidx, ctx, env, completers)
