from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    RichCompletion,
    contextual_completer,
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
    env = XSH.env

    # Strip trailing '?' to support "$VAR?" help completions
    help_query = key.endswith("?")
    search_key = key[:-1] if help_query else key

    vars = [k for k, v in env.items() if search_key.lower() in k.lower()]

    def _completions():
        for k in vars:
            vd = env.get_docs(k)
            type_name = type(env[k]).__name__
            yield RichCompletion(
                "$" + k,
                display=f"${k} [{type_name}]",
                description=vd.doc,
            )
            if not help_query:
                doc_str = vd.doc
                default_str = vd.doc_default
                desc = f"{doc_str} | Type: {type_name} | Default: {default_str}"
                yield RichCompletion(
                    "$" + k + "?",
                    display=f"${k}? [{type_name}]",
                    description=desc,
                )

    return _completions(), lprefix
