import builtins
from collections import OrderedDict

from xonsh.completers.man import complete_from_man
from xonsh.completers.bash import complete_from_bash
from xonsh.completers.base import complete_base
from xonsh.completers.path import complete_path
from xonsh.completers.dirs import complete_cd, complete_rmdir
from xonsh.completers.python import (complete_python, complete_import,
                                     complete_python_mode)
from xonsh.completers.commands import complete_skipper

completers = OrderedDict([
    ('python_mode', complete_python_mode),
    ('base', complete_base),
    ('skip', complete_skipper),
    ('cd', complete_cd),
    ('rmdir', complete_rmdir),
    ('bash', complete_from_bash),
    ('man', complete_from_man),
    ('import', complete_import),
    ('python', complete_python),
    ('path', complete_path),
])

builtins.__xonsh_completers__ = completers
