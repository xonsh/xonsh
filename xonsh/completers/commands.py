import functools
import os
import re
import typing as tp

import xonsh.platform as xp
from xonsh.built_ins import XSH
from xonsh.commands_cache import executables_in
from xonsh.completer import Completer
from xonsh.completers.tools import (
    RichCompletion,
    contextual_command_completer,
    get_filter_function,
    non_exclusive_completer,
    tag_provider,
)
from xonsh.lib.modules import ModuleFinder
from xonsh.parsers.completion_context import CommandContext, CompletionContext

SKIP_TOKENS = {"sudo", "time", "timeit", "which", "showcmd", "man"}
END_PROC_TOKENS = ("|", ";", "&&")  # includes ||
END_PROC_KEYWORDS = {"and", "or"}


def _alias_completion_description(aliases, name: str) -> str:
    """Return the first non-empty line of the alias docstring, or ``""``.

    The completion dropdown's ``display_meta`` is rendered as a single line
    (prompt-toolkit replaces newlines with spaces in
    ``PromptToolkitCompleter.get_completions``), so a multi-line docstring is
    summarised down to its first non-empty line — typically the docstring's
    one-line summary in PEP 257 style.
    """
    if aliases is None:
        return ""
    doc = aliases.get_doc(name)
    if not doc:
        return ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def complete_command(command: CommandContext):
    """
    Returns a list of valid commands starting with the first argument
    """

    cmd = command.prefix
    show_desc = (XSH.env or {}).get("CMD_COMPLETIONS_SHOW_DESC", False)
    aliases = XSH.aliases
    for s, (path, is_alias) in XSH.commands_cache.iter_commands():
        if get_filter_function()(s, cmd):
            description = ""
            if is_alias:
                # Surface the alias docstring as the dropdown description
                # whenever the user wrote one — the docstring is an explicit
                # opt-in, so showing it doesn't depend on
                # ``$CMD_COMPLETIONS_SHOW_DESC``. Fall back to the static
                # ``"Alias"`` label only when descriptions are explicitly
                # enabled and there is no docstring to show.
                description = _alias_completion_description(aliases, s)
                if not description and show_desc:
                    description = "Alias"
            elif show_desc:
                description = path
            yield RichCompletion(
                s,
                append_space=True,
                provider="alias" if is_alias else "command",
                description=description,
            )
    if xp.ON_WINDOWS:
        for i in executables_in("."):
            if get_filter_function()(i, cmd):
                yield RichCompletion(i, append_space=True, provider="command")
    base = os.path.basename(cmd)
    if os.path.isdir(base):
        for i in executables_in(base):
            if get_filter_function()(i, cmd):
                yield RichCompletion(os.path.join(base, i), provider="command")


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


class ModuleReMatcher(ModuleFinder):
    """supports regex based proxying"""

    def __init__(self, *names: str):
        # list of pre-defined patterns. More can be added using the public method ``.wrap``
        self._patterns: dict[str, str] = {}
        self._compiled: dict[str, tp.Pattern] = {}
        super().__init__(*names)

    def search_completer(self, cmd: str, cleaned=False):
        if not cleaned:
            cmd = CommandCompleter.clean_cmd_name(cmd)
        # try any pattern match
        for pattern, mod_name in self._patterns.items():
            # lazy compile regex
            if pattern not in self._compiled:
                self._compiled[pattern] = re.compile(pattern, re.IGNORECASE)
            regex = self._compiled[pattern]
            if regex.match(cmd):
                return self.get_module(mod_name)

    def wrap(self, pattern: str, module: str):
        """For any commands matching the pattern complete from the ``module``"""
        self._patterns[pattern] = module


class CommandCompleter:
    """Lazily complete commands from `xompletions` package

    The base-name (case-insensitive) of the executable is used to find the matching completer module
    or the regex patterns.
    """

    def __init__(self):
        self.contextual = True
        self._matcher = None

    @property
    def matcher(self):
        if self._matcher is None:
            self._matcher = ModuleReMatcher(
                "xompletions",
                *XSH.env.get("XONSH_COMPLETER_DIRS", []),
            )
            self._matcher.wrap(r"\bx?pip(?:\d|\.)*(exe)?$", "pip")
            self._matcher.wrap(r"\bpython(?:\d|\.)*(exe)?$", "python")
            # More patterns can be registered via self.wrap() from xonshrc/xontrib
        return self._matcher

    def wrap(self, pattern, module_name):
        """Register a regex pattern to map command name variants to a completer module.

        Can be called from xonshrc or xontrib::

            from xonsh.completers.commands import complete_xompletions as xmp
            xmp.wrap(r"\\bmycmd(?:\\d)*$", "mycmd")

        """
        self.matcher.wrap(pattern, module_name)

    @staticmethod
    @functools.lru_cache(10)
    def clean_cmd_name(cmd: str):
        cmd_name = os.path.basename(cmd).lower()
        exts = XSH.env.get("PATHEXT", [])
        for ex in exts:
            if cmd_name.endswith(ex.lower()):
                # windows handling
                cmd_name = cmd_name.removesuffix(ex.lower())
                break
        return cmd_name

    def __call__(self, full_ctx: CompletionContext):
        """For the given command load completions lazily"""

        # completion for commands only
        ctx = full_ctx.command
        if not ctx:
            return

        if ctx.arg_index == 0:
            return

        cmd_name = self.clean_cmd_name(ctx.command)
        module = self.matcher.get_module(cmd_name) or self.matcher.search_completer(
            cmd_name, cleaned=True
        )

        if not module:
            return

        if hasattr(module, "xonsh_complete"):
            func = module.xonsh_complete
            # Tag results with the xompletion module's short name
            # (``xompletions.pip`` → ``pip``) so ``$XONSH_COMPLETER_TRACE``
            # can tell which concrete module produced each completion
            # under the generic ``source=xompleter`` umbrella.
            provider = module.__name__.rsplit(".", 1)[-1]
            return tag_provider(func(ctx), provider)


complete_xompletions = CommandCompleter()
