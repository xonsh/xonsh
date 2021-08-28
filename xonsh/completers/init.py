"""Constructor for xonsh completer objects."""
import collections

from xonsh.completers.pip import complete_pip
from xonsh.completers.man import complete_from_man
from xonsh.completers.bash import complete_from_bash
from xonsh.completers.base import complete_base
from xonsh.completers.path import complete_path
from xonsh.completers.dirs import complete_cd, complete_rmdir
from xonsh.completers.python import (
    complete_python,
)
from xonsh.completers.imports import complete_import
from xonsh.completers.commands import (
    complete_skipper,
    complete_end_proc_tokens,
    complete_end_proc_keywords,
)
from xonsh.completers._aliases import complete_argparser_aliases
from xonsh.completers.environment import complete_environment_vars


def default_completers():
    """Creates a copy of the default completers."""
    return collections.OrderedDict(
        [
            # non-exclusive completers:
            ("end_proc_tokens", complete_end_proc_tokens),
            ("end_proc_keywords", complete_end_proc_keywords),
            ("environment_vars", complete_environment_vars),
            # exclusive completers:
            ("base", complete_base),
            ("skip", complete_skipper),
            ("argparser_aliases", complete_argparser_aliases),
            ("pip", complete_pip),
            ("cd", complete_cd),
            ("rmdir", complete_rmdir),
            ("import", complete_import),
            ("bash", complete_from_bash),
            ("man", complete_from_man),
            ("python", complete_python),
            ("path", complete_path),
        ]
    )
