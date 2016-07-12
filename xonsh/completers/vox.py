import builtins

from xonsh.lazyasd import LazyObject

from xonsh.platform import scandir
from xonsh.vox import Vox
import os

DEFAULT_ENV_HOME = os.path.expanduser('~/.virtualenvs')
ALL_COMMANDS = LazyObject(lambda: [c[0].split()[1] for c in Vox.help_commands],
                          globals(), 'ALL_COMMANDS')


def complete_vox(prefix, line, begidx, endidx, ctx):
    """
    Completes Xonsh's Vox virtual environment manager
    """
    cases = [
        not line.startswith('vox'),
        len(line.split()) > 3,
        len(line.split()) > 2 and line.endswith(' '),
    ]
    if any(cases):
        return

    to_list_when = ['vox activate ', 'vox remove ']
    if any(c in line for c in to_list_when):
        venv_home = builtins.__xonsh_env__.get('VIRTUALENV_HOME', DEFAULT_ENV_HOME)
        env_dirs = list(x.name for x in scandir(venv_home) if x.is_dir())
        return env_dirs, len(prefix)

    if len(line.split()) > 1 and line.endswith(' '):  # "vox new "
        return

    if prefix not in ALL_COMMANDS:
        suggestions = [c for c in ALL_COMMANDS if c.startswith(prefix)]
        if suggestions:
            return suggestions, len(prefix)
    return ALL_COMMANDS, len(prefix)
