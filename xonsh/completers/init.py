"""Constructor for xonsh completer objects."""

import collections

from xonsh.completers._aliases import complete_aliases
from xonsh.completers.base import complete_base
from xonsh.completers.bash import complete_from_bash
from xonsh.completers.commands import (
    complete_end_proc_keywords,
    complete_end_proc_tokens,
    complete_skipper,
    complete_xompletions,
)
from xonsh.completers.environment import complete_environment_vars
from xonsh.completers.imports import complete_import
from xonsh.completers.man import complete_from_man
from xonsh.completers.path import complete_path
from xonsh.completers.python import complete_python


def default_completers(cmd_cache):
    """Creates a copy of the default completers."""
    defaults = [
        # non-exclusive completers:
        ("end_proc_tokens", complete_end_proc_tokens),
        ("end_proc_keywords", complete_end_proc_keywords),
        ("environment_vars", complete_environment_vars),
        # exclusive completers:
        ("base", complete_base),
        ("skip", complete_skipper),
        ("alias", complete_aliases),
        ("xompleter", complete_xompletions),
        ("import", complete_import),
    ]

    for cmd, func in [
        ("bash", complete_from_bash),
        ("man", complete_from_man),
    ]:
        if cmd in cmd_cache:
            defaults.append((cmd, func))

    defaults.extend(
        [
            ("python", complete_python),
            ("path", complete_path),
        ]
    )
    return collections.OrderedDict(defaults)
