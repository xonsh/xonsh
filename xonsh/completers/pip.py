import re
import subprocess

RE_PIP = re.compile("pip(?:\d|\.)*")
RE_PIP_LIST = re.compile("pip(?:\d|\.)* (?:uninstall|show)")


def get_pip_commands():
    help_text = str(subprocess.check_output(['pip', '--help'], stderr=subprocess.DEVNULL))
    commands = re.findall("  (\w+)  ", help_text)
    return [c for c in commands if c not in ['completion', 'help']]


ALL_COMMANDS = get_pip_commands()


def complete_pip(prefix, line, begidx, endidx, ctx):
    """
    Completes python's package manager pip
    """
    if not RE_PIP.search(line):
        return
    if RE_PIP_LIST.search(line):
        items = subprocess.check_output(['pip', 'list'], stderr=subprocess.DEVNULL)
        items = items.decode('utf-8').splitlines()
        return set(i.split()[0] for i in items)

    if (len(line.split()) > 1 and line.endswith(' ')) or len(line.split()) > 2:
        # "pip show " -> no complete (note space)
        return

    if prefix in ALL_COMMANDS:
        # "pip show" -> suggest replacing new with other command (note no space)
        return ALL_COMMANDS, len(prefix)
    elif prefix:
        # "pip sh" -> suggest "show"
        return [c for c in ALL_COMMANDS if c.startswith(prefix)], len(prefix)
    return set(ALL_COMMANDS)
