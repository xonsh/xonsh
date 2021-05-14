from xonsh.built_ins import XSH
from xonsh.parsers.completion_context import CompletionContext
from xonsh.completers.tools import (
    contextual_completer,
    non_exclusive_completer,
    get_filter_function,
)


@contextual_completer
@non_exclusive_completer
def complete_environment_vars(context: CompletionContext):
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
    filter_func = get_filter_function()
    env_names = XSH.env

    return {"$" + k for k in env_names if filter_func(k, key)}, lprefix
