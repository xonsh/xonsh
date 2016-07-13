import re
import subprocess

from xonsh.lazyasd import LazyObject

PIP_RE = LazyObject(lambda: re.compile("pip(?:\d|\.)*"),
                    globals(), 'PIP_RE')
PIP_LIST_RE = LazyObject(lambda: re.compile("pip(?:\d|\.)* (?:uninstall|show)"),
                         globals(), 'PIP_LIST_RE')


def get_pip_commands():
    help_text = str(subprocess.check_output(['pip', '--help'], stderr=subprocess.DEVNULL))
    commands = re.findall("  (\w+)  ", help_text)
    return [c for c in commands if c not in ['completion', 'help']]

ALL_COMMANDS = LazyObject(lambda: get_pip_commands(),
                          globals(), 'ALL_COMMANDS')


def complete_pip(prefix, line, begidx, endidx, ctx):
    """
    Completes python's package manager pip
    """
    line_len = len(line.split())
    case = [
        not PIP_RE.search(line),
        line_len > 3,
        line_len > 2 and line.endswith(' '),
    ]
    if any(case):
        return
    if PIP_LIST_RE.search(line):
        items = subprocess.check_output(['pip', 'list'], stderr=subprocess.DEVNULL)
        items = items.decode('utf-8').splitlines()
        return set(i.split()[0] for i in items)

    if (line_len > 1 and line.endswith(' ')) or line_len > 2:
        # "pip show " -> no complete (note space)
        return

    if prefix not in ALL_COMMANDS:
        suggestions = [c for c in ALL_COMMANDS if c.startswith(prefix)]
        if suggestions:
            return suggestions, len(prefix)
    return ALL_COMMANDS, len(prefix)
