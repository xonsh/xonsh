from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    RichCompletion,
    contextual_completer,
    get_filter_function,
    non_exclusive_completer,
)
from xonsh.parsers.completion_context import CompletionContext


@contextual_completer
@non_exclusive_completer
def complete_environment_vars(context: CompletionContext):
    """Completes environment variables."""
    if context.command:
        prefix = context.command.prefix
    elif context.python:
        prefix = context.python.prefix
    else:
        return None

    dollar_location = prefix.rfind("$")
    if dollar_location == -1:
        return None

    key = prefix[dollar_location + 1 :]
    lprefix = len(key) + 1
    if context.command is not None and context.command.is_after_closing_quote:
        lprefix += 1
    filter_func = get_filter_function()
    env = XSH.env

    return (
        RichCompletion(
            "$" + k,
            display=f"${k} [{type(v).__name__}]",
            description=env.get_docs(k).doc,
        )
        for k, v in env.items()
        if filter_func(k, key)
    ), lprefix
