"""Completers for pip."""
# pylint: disable=invalid-name, missing-docstring, unsupported-membership-test
# pylint: disable=unused-argument, not-an-iterable
import re
import subprocess

import xonsh.lazyasd as xl
from xonsh.completers.tools import contextual_command_completer, get_filter_function
from xonsh.parsers.completion_context import CommandContext


PIP_LIST_COMMANDS = {"uninstall", "show"}


@xl.lazyobject
def PIP_RE():
    return re.compile(r"\bx?pip(?:\d|\.)*$")


@xl.lazyobject
def ALL_COMMANDS():
    try:
        help_text = str(
            subprocess.check_output(["pip", "--help"], stderr=subprocess.DEVNULL)
        )
    except FileNotFoundError:
        try:
            help_text = str(
                subprocess.check_output(["pip3", "--help"], stderr=subprocess.DEVNULL)
            )
        except FileNotFoundError:
            return []
    commands = re.findall(r"  (\w+)  ", help_text)
    return [c for c in commands if c not in ["completion", "help"]]


@contextual_command_completer
def complete_pip(context: CommandContext):
    """Completes python's package manager pip"""
    prefix = context.prefix
    if context.arg_index == 0 or (not PIP_RE.search(context.args[0].value)):
        return None
    filter_func = get_filter_function()

    if context.arg_index == 2 and context.args[1].value in PIP_LIST_COMMANDS:
        # `pip show PREFIX` - complete package names
        try:
            enc_items = subprocess.check_output(
                [context.args[0].value, "list"], stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            return None
        packages = (
            line.split(maxsplit=1)[0] for line in enc_items.decode("utf-8").splitlines()
        )
        return {package for package in packages if filter_func(package, prefix)}

    if context.arg_index == 1:
        # `pip PREFIX` - complete pip commands
        suggestions = [c for c in ALL_COMMANDS if filter_func(c, prefix)]
        if suggestions:
            return suggestions, len(prefix)

    return None
