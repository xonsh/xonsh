"""Tab-completion for click-based aliases registered via
:func:`xonsh.aliases.Aliases.register_click_command`.

The entry point is :func:`complete_click`, bound per-alias through
``functools.partial(complete_click, click_cmd)`` and attached to the
alias wrapper as ``xonsh_complete``. The stock alias completer
(``xonsh.completers._aliases.complete_aliases``) then picks it up from
``alias.func.xonsh_complete`` during normal tab completion.

The ``click`` package is imported lazily — this module is only
exercised once a click alias has been registered, which itself requires
click to be installed.
"""

from xonsh.completers.tools import RichCompletion


def option_all_opts(param):
    """Every flag string declared on a ``click.Option`` — primary +
    secondary. ``secondary_opts`` holds the off-switch of flag pairs
    like ``--verbose/--quiet``.
    """
    return list(param.opts) + list(param.secondary_opts)


def option_takes_value(param):
    """``True`` if the option consumes a separate argument as its value.
    Flags (``--verbose``) and count options (``-vvv``) do not.
    """
    return not (getattr(param, "is_flag", False) or getattr(param, "count", False))


def resolve_subcommand(root_cmd, args):
    """Walk ``click.Group`` → sub-command chain consuming positional tokens.

    Returns ``(current_cmd, remaining_args)`` where ``remaining_args`` is
    the slice of ``args`` belonging to ``current_cmd`` (i.e. everything
    after the last recognised sub-command name).

    Options are skipped when they appear before the sub-command name —
    the few that take a separate value consume the next token as well.
    An unknown sub-command stops the walk, so the completer can still
    offer ``--`` options on the outermost unresolved command.
    """
    import click

    current = root_cmd
    remaining = list(args)
    while isinstance(current, click.Group) and remaining:
        i = 0
        # Skip leading options belonging to the group.
        while i < len(remaining) and remaining[i].startswith("-"):
            opt = remaining[i]
            i += 1
            if "=" not in opt and i < len(remaining):
                for p in current.params:
                    if isinstance(p, click.Option) and opt in option_all_opts(p):
                        if option_takes_value(p):
                            i += 1
                        break
        if i >= len(remaining):
            break
        sub_name = remaining[i]
        sub = current.get_command(click.Context(current), sub_name)
        if sub is None:
            # Unknown sub-command — stop here so caller can still complete
            # against the current group's options.
            break
        current = sub
        remaining = remaining[i + 1 :]
    return current, remaining


def previous_option_waiting_value(current_cmd, args_after_cmd):
    """If the last token is an option expecting a value, return that
    ``click.Option``; otherwise ``None``. Used to drive Choice completion
    after things like ``--color <TAB>``.
    """
    import click

    if not args_after_cmd:
        return None
    prev = args_after_cmd[-1]
    if not prev.startswith("-") or "=" in prev:
        return None
    for param in current_cmd.params:
        if isinstance(param, click.Option) and prev in option_all_opts(param):
            if option_takes_value(param):
                return param
            return None
    return None


def positional_index(current_cmd, args_after_cmd):
    """Count how many positional arguments have been supplied to
    ``current_cmd`` so far, skipping options and their values. Used to
    pick which ``click.Argument`` slot we're completing into.
    """
    import click

    idx = 0
    j = 0
    while j < len(args_after_cmd):
        arg = args_after_cmd[j]
        if arg.startswith("-"):
            if "=" in arg:
                j += 1
                continue
            takes_value = False
            for param in current_cmd.params:
                if isinstance(param, click.Option) and arg in option_all_opts(param):
                    takes_value = option_takes_value(param)
                    break
            j += 2 if takes_value else 1
        else:
            idx += 1
            j += 1
    return idx


def complete_click(click_cmd, command, alias=None, **_):
    """Tab-completer for click-based aliases.

    Yields completions for, in priority order:

    1. Option values when the preceding token is an option with a
       ``click.Choice`` type (``--color <TAB>`` → ``red green blue``).
    2. Option flags when the prefix starts with ``-``
       (``--nam<TAB>`` → ``--name``).
    3. Sub-command names when the current command is a ``click.Group``.
    4. Positional arguments with a ``click.Choice`` type.

    Bound per-alias via :func:`functools.partial` in
    :func:`xonsh.aliases._click_command_alias`, so each wrapper captures
    its own ``click.Command`` instance.
    """
    import click

    # Descend click.Group chain to find the command we're completing into.
    args_after_cmd = [a.value for a in command.args[1:]]
    current_cmd, args_after_cmd = resolve_subcommand(click_cmd, args_after_cmd)

    prefix = command.prefix

    # 1. Value for an option that takes one (only Choice is predictable).
    pending = previous_option_waiting_value(current_cmd, args_after_cmd)
    if pending is not None:
        if isinstance(pending.type, click.Choice):
            return {
                RichCompletion(choice, append_space=True)
                for choice in pending.type.choices
                if choice.startswith(prefix)
            }
        # Opaque type (str, int, path, ...) — no suggestions from us; let
        # other completers (path, etc.) try.
        return None

    # 2. Option flag.
    if prefix.startswith("-"):
        results = set()
        for param in current_cmd.params:
            if isinstance(param, click.Option):
                for opt in option_all_opts(param):
                    if opt.startswith(prefix):
                        results.add(
                            RichCompletion(
                                opt,
                                description=(param.help or "").strip(),
                            )
                        )
        if getattr(current_cmd, "add_help_option", False) and "--help".startswith(
            prefix
        ):
            results.add(
                RichCompletion("--help", description="Show this message and exit.")
            )
        return results

    # 3. Sub-command name for a click.Group.
    if isinstance(current_cmd, click.Group):
        ctx = click.Context(current_cmd)
        results = set()
        for sub_name in current_cmd.list_commands(ctx):
            if sub_name.startswith(prefix):
                sub = current_cmd.get_command(ctx, sub_name)
                desc = (
                    getattr(sub, "short_help", None) or getattr(sub, "help", None) or ""
                ).strip()
                results.add(
                    RichCompletion(sub_name, description=desc, append_space=True)
                )
        return results

    # 4. Positional arg with a Choice type.
    click_arguments = [p for p in current_cmd.params if isinstance(p, click.Argument)]
    pos_idx = positional_index(current_cmd, args_after_cmd)
    if pos_idx < len(click_arguments):
        arg_param = click_arguments[pos_idx]
        if isinstance(arg_param.type, click.Choice):
            return {
                RichCompletion(choice, append_space=True)
                for choice in arg_param.type.choices
                if choice.startswith(prefix)
            }

    return None
