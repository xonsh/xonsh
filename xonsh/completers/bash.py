"""Xonsh hooks into bash completions."""

import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.completers.bash_completion import bash_completions
from xonsh.completers.tools import RichCompletion, contextual_command_completer
from xonsh.parsers.completion_context import CommandContext


@contextual_command_completer
def complete_from_bash(context: CommandContext):
    """Completes based on results from BASH completion."""
    env = XSH.env.detype()  # type: ignore
    paths = XSH.env.get("BASH_COMPLETIONS", ())  # type: ignore
    command = xp.bash_command()
    args = [arg.value for arg in context.args]
    prefix = context.prefix  # without the quotes
    args.insert(context.arg_index, prefix)
    line = " ".join(args)

    # lengths of all args + joining spaces
    begidx = sum(len(a) for a in args[: context.arg_index]) + context.arg_index
    endidx = begidx + len(prefix)

    opening_quote = context.opening_quote
    closing_quote = context.closing_quote
    if closing_quote and not context.is_after_closing_quote:
        # there already are closing quotes after our cursor, don't complete new ones (i.e. `ls "/pro<TAB>"`)
        closing_quote = ""
    elif opening_quote and not closing_quote:
        # get the proper closing quote
        closing_quote = xt.RE_STRING_START.sub("", opening_quote)

    comps, lprefix = bash_completions(
        prefix,
        line,
        begidx,
        endidx,
        env=env,
        paths=paths,
        command=command,
        line_args=args,
        opening_quote=opening_quote,
        closing_quote=closing_quote,
        arg_index=context.arg_index,
    )

    def enrich_comps(comp: str):
        append_space = False
        if comp.endswith(" "):
            append_space = True
            comp = comp.rstrip()

        # ``bash_completions`` may have added closing quotes:
        return RichCompletion(
            comp, append_closing_quote=False, append_space=append_space
        )

    comps = set(map(enrich_comps, comps))

    if lprefix == len(prefix):
        lprefix += len(context.opening_quote)
    if context.is_after_closing_quote:
        # since bash doesn't see the closing quote, we need to add its length to lprefix
        lprefix += len(context.closing_quote)

    return comps, lprefix
