import builtins

from xonsh.lazyasd import LazyObject

from xonsh.platform import scandir
from xonsh.vox import Vox
import os

DEFAULT_ENV_HOME = os.path.expanduser('~/.virtualenvs')


def complete_vox(prefix, line, begidx, endidx, ctx):
    """
    Completes Xonsh's Vox virtual environment manager
    """
    if not line.startswith('vox'):
        return
    to_list_when = ['vox activate ', 'vox remove ']
    if any(c in line for c in to_list_when):
        venv_home = builtins.__xonsh_env__.get('VIRTUALENV_HOME', DEFAULT_ENV_HOME)
        env_dirs = list(x.name for x in scandir(venv_home) if x.is_dir())
        return set(env_dirs)

    if (len(line.split()) > 1 and line.endswith(' ')) or len(line.split()) > 2:
        # "vox new " -> no complete (note space)
        return

    all_commands = [c[0].split()[1] for c in Vox.help_commands]
    if prefix in all_commands:
        # "vox new" -> suggest replacing new with other command (note no space)
        return all_commands, len(prefix)
    elif prefix:
        # "vox n" -> suggest "new"
        suggestions = [c for c in all_commands if c.startswith(prefix)]
        if suggestions:
            return suggestions, len(prefix)
    return all_commands, len(prefix)
