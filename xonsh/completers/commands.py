import contextlib
import functools
import importlib
import importlib.util as im_util
import os
import re
import typing as tp
from collections import OrderedDict

import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.completer import Completer
from xonsh.completers.tools import (
    RichCompletion,
    contextual_command_completer,
    get_filter_function,
    non_exclusive_completer,
)
from xonsh.environ import scan_dir_for_source_files
from xonsh.parsers.completion_context import CommandContext, CompletionContext

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


class ModuleMatcher:
    """Reusable module matcher. Can be used by other completers like Python to find matching script completions"""

    extensions = (".py", ".xsh")

    def __init__(self, *names: "str"):
        """Helper class to search and load Python modules

        Parameters
        ----------
        names
            extra search paths/package-names to use if finding module on namespace package fails.
            paths should have a path literal to indicate it is a path. Otherwise it is treated as a package name.
        """

        self.contextual = True

        # unique but maintain order
        self._pkgs = OrderedDict()
        self._paths = OrderedDict()
        for pk in names:
            if os.sep in pk:
                self._paths[pk] = None
            else:
                self._pkgs[pk] = None

        self._file_names_cache: "dict[str, str]" = {}
        self._path_st_mtimes: "dict[str, float]" = {}

    def _get_new_paths(self):
        for path in self._paths:
            if not os.path.isdir(path):
                continue
            # check if path is updated
            old_mtime = self._path_st_mtimes.get(path, 0)
            new_mtime = os.stat(path).st_mtime
            if old_mtime >= new_mtime:
                continue
            self._path_st_mtimes[path] = os.stat(path).st_mtime
            yield path

    def _find_file_path(self, name):
        # `importlib.machinery.FileFinder` wasn't useful as the findspec handles '.' differently
        if name in self._file_names_cache:
            return self._file_names_cache[name]

        found = None
        entries = {}
        for path in self._get_new_paths():
            for file, entry in scan_dir_for_source_files(path):
                file_name = os.path.splitext(entry.name)[0]
                if file_name not in entries:
                    # do not override. prefer the first one that appears on the path list
                    entries[file_name] = file
                if file_name == name:
                    found = file
            if found:
                # search a directory completely since we cache path-mtime
                break
        self._file_names_cache.update(entries)
        return found

    @staticmethod
    def import_module(path, name: str):
        """given the file location import as module"""
        pkg = path.replace(os.sep, ".")
        spec = im_util.spec_from_file_location(f"{pkg}.{name}", path)
        if not spec:
            return
        module = im_util.module_from_spec(spec)
        if not spec.loader:
            return
        spec.loader.exec_module(module)  # type: ignore
        return module

    @functools.lru_cache(maxsize=None)
    def get_module(self, module: str):
        for name in [
            module,
            f"_{module}",  # naming convention to not clash with actual python package
        ]:
            for base in self._pkgs:
                with contextlib.suppress(ModuleNotFoundError):
                    return importlib.import_module(f"{base}.{name}")
        file = self._find_file_path(module)
        if file:
            return self.import_module(file, module)


class ModuleReMatcher(ModuleMatcher):
    """supports regex based proxying"""

    def __init__(self, *names: str):
        # list of pre-defined patterns. More can be added using the public method ``.wrap``
        self._patterns: tp.Dict[str, str] = {}
        self._compiled: tp.Dict[str, tp.Pattern] = {}
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
        return self._matcher

    @staticmethod
    @functools.lru_cache(10)
    def clean_cmd_name(cmd: str):
        cmd_name = os.path.basename(cmd).lower()
        exts = XSH.env.get("PATHEXT", [])
        for ex in exts:
            if cmd_name.endswith(ex.lower()):
                # windows handling
                cmd_name = cmd_name.rstrip(ex.lower())
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
            return func(ctx)


complete_xompletions = CommandCompleter()
