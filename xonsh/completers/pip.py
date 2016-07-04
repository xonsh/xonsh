import re
import subprocess


def get_pip_commands():
    help_text = str(subprocess.check_output(['pip', '--help'], stderr=subprocess.DEVNULL))
    commands = re.findall("  (\w+)  ", help_text)
    return [c for c in commands if c not in ['completion', 'help']]


def complete_pip(prefix, line, begidx, endidx, ctx):
    """
    Completes python's package manager pip
    """
    if not re.search("pip(?:\d|\.)*", line):
        return
    if re.search("pip(?:\d|\.)* (?:uninstall|show)", line):
        items = subprocess.check_output(['pip', 'list'], stderr=subprocess.DEVNULL)
        items = items.decode('utf-8').splitlines()
        return set(i.split()[0] for i in items)

    if (len(line.split()) > 1 and line.endswith(' ')) or len(line.split()) > 2:
        # "pip show " -> no complete (note space)
        return

    all_commands = get_pip_commands()
    if prefix in all_commands:
        # "pip show" -> suggest replacing new with other command (note no space)
        return all_commands, len(prefix)
    elif prefix:
        # "pip sh" -> suggest "show"
        return [c for c in all_commands if c.startswith(prefix)], len(prefix)
    return set(all_commands)
