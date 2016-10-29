"""Completers for pip."""
# pylint: disable=invalid-name, missing-docstring, unsupported-membership-test
# pylint: disable=unused-argument, not-an-iterable
import re
import subprocess

import xonsh.lazyasd as xl


@xl.lazyobject
def PIP_RE():
    return re.compile(r"pip(?:\d|\.)*")


@xl.lazyobject
def PIP_LIST_RE():
    return re.compile(r"pip(?:\d|\.)* (?:uninstall|show)")


@xl.lazyobject
def ALL_COMMANDS():
    try:
        help_text = str(subprocess.check_output(['pip', '--help'],
                                                stderr=subprocess.DEVNULL))
    except FileNotFoundError:
        return []
    commands = re.findall(r"  (\w+)  ", help_text)
    return [c for c in commands if c not in ['completion', 'help']]


def complete_pip(prefix, line, begidx, endidx, ctx):
    """Completes python's package manager pip"""
    line_len = len(line.split())
    if (line_len > 3) or (line_len > 2 and line.endswith(' ')) or \
                         (not PIP_RE.search(line)):
        return
    if PIP_LIST_RE.search(line):
        try:
            items = subprocess.check_output(['pip', 'list'],
                                            stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            return set()
        items = items.decode('utf-8').splitlines()
        return set(i.split()[0] for i in items
                   if i.split()[0].startswith(prefix))

    if (line_len > 1 and line.endswith(' ')) or line_len > 2:
        # "pip show " -> no complete (note space)
        return
    if prefix not in ALL_COMMANDS:
        suggestions = [c for c in ALL_COMMANDS if c.startswith(prefix)]
        if suggestions:
            return suggestions, len(prefix)
    return ALL_COMMANDS, len(prefix)
