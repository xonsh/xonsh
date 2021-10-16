import importlib.util
import os
import re
import typing as tp

import xonsh.tools as xt
import xonsh.platform as xp
from xonsh.completer import Completer
from xonsh.completers.tools import (
    get_filter_function,
    contextual_command_completer,
    RichCompletion,
    non_exclusive_completer,
)
from xonsh.parsers.completion_context import CompletionContext, CommandContext
from xonsh.built_ins import XSH


SKIP_TOKENS = {"sudo", "time", "timeit", "which", "showcmd", "man"}
END_PROC_TOKENS = ("|", ";", "&&")  # includes ||
END_PROC_KEYWORDS = {"and", "or"}


def complete_command(command: CommandContext):
    """
    Returns a list of valid commands starting with the first argument
    """

    cmd = command.prefix
    show_desc = (XSH.env or {}).get("CMD_COMPLETIONS_SHOW_DESC", False)
    for s, (path, is_alias) in XSH.commands_cache.iter_commands():
        if get_filter_function()(s, cmd):
            kwargs = {}
            if show_desc:
                kwargs["description"] = "Alias" if is_alias else path
            yield RichCompletion(s, append_space=True, **kwargs)
    if xp.ON_WINDOWS:
        for i in xt.executables_in("."):
            if i.startswith(cmd):
                yield RichCompletion(i, append_space=True)
    base = os.path.basename(cmd)
    if os.path.isdir(base):
        for i in xt.executables_in(base):
            if i.startswith(cmd):
                yield RichCompletion(os.path.join(base, i))


@contextual_command_completer
def complete_skipper(command_context: CommandContext):
    """
    Skip over several tokens (e.g., sudo) and complete based on the rest of the command.
    """

    # Contextual completers don't need us to skip tokens since they get the correct completion context -
    # meaning we only need to skip commands like ``sudo``.
    skip_part_num = 0
    # all the args before the current argument
    for arg in command_context.args[: command_context.arg_index]:
        if arg.value not in SKIP_TOKENS:
            break
        skip_part_num += 1

    if skip_part_num == 0:
        return None

    skipped_command_context = command_context._replace(
        args=command_context.args[skip_part_num:],
        arg_index=command_context.arg_index - skip_part_num,
    )

    if skipped_command_context.arg_index == 0:
        # completing the command after a SKIP_TOKEN
        return complete_command(skipped_command_context)

    completer: Completer = XSH.shell.shell.completer  # type: ignore
    return completer.complete_from_context(CompletionContext(skipped_command_context))


@non_exclusive_completer
@contextual_command_completer
def complete_end_proc_tokens(command_context: CommandContext):
    """If there's no space following '|', '&', or ';' - insert one."""
    if command_context.opening_quote or not command_context.prefix:
        return None
    prefix = command_context.prefix
    # for example `echo a|`, `echo a&&`, `echo a ;`
    if any(prefix.endswith(ending) for ending in END_PROC_TOKENS):
        return {RichCompletion(prefix, append_space=True)}
    return None


@non_exclusive_completer
@contextual_command_completer
def complete_end_proc_keywords(command_context: CommandContext):
    """If there's no space following 'and' or 'or' - insert one."""
    if command_context.opening_quote or not command_context.prefix:
        return None
    prefix = command_context.prefix
    if prefix in END_PROC_KEYWORDS:
        return {RichCompletion(prefix, append_space=True)}
    return None


class CommandCompleter:
    """Lazy completer with its own state"""

    def __init__(self):
        # list of pre-defined patterns. More can be added using the public method ``.wrap``
        self._patterns: tp.Dict[str, str] = {
            r"\bx?pip(?:\d|\.)*(exe)?$": "pip",
        }
        self._compiled: tp.Dict[str, tp.Pattern] = {}
        self.contextual = True

    def wrap(self, pattern: str, module: str):
        """For any commands matching the pattern complete form the ``module``"""
        self._patterns[pattern] = module

    @staticmethod
    def get_module(name):
        try:
            return importlib.import_module(f"xompletions.{name}")
        except ModuleNotFoundError:
            pass

    def search_completer(self, cmd: str, cleaned=False):
        if not cleaned:
            cmd = self.clean_cmd_name(cmd)
        # try any pattern match
        for pattern, mod_name in self._patterns.items():
            # lazy compile regex
            if pattern not in self._compiled:
                self._compiled[pattern] = re.compile(pattern, re.IGNORECASE)
            regex = self._compiled[pattern]
            if regex.match(cmd):
                return self.get_module(mod_name)

    @staticmethod
    def clean_cmd_name(cmd: str):
        cmd_name = cmd.lower()
        cmd_name = os.path.split(cmd_name)[-1]
        if cmd_name.endswith(".exe"):
            # windows handling
            cmd_name = cmd_name.replace(".exe", "")
        return cmd_name

    def __call__(self, full_ctx: CommandContext):
        """For the given command load completions lazily"""
        if not full_ctx.command:
            return

        ctx = full_ctx.command
        if ctx.arg_index == 0:
            return

        cmd_name = self.clean_cmd_name(ctx.command)
        module = self.get_module(cmd_name) or self.search_completer(
            cmd_name, cleaned=True
        )

        if not module:
            return

        if hasattr(module, "xonsh_complete"):
            func = module.xonsh_complete
            return func(ctx)


complete_xompletions = CommandCompleter()
