from collections import OrderedDict

from xonsh.completers.man import complete_from_man
from xonsh.completers.bash import complete_from_bash
from xonsh.completers.base import complete_base
from xonsh.completers.path import complete_path
from xonsh.completers.dirs import complete_cd, complete_rmdir
from xonsh.completers.python import complete_python, complete_import
from xonsh.completers.commands import complete_skipper

completers = OrderedDict()
completers['base'] = complete_base
completers['man'] = complete_from_man
completers['skip'] = complete_skipper
completers['cd'] = complete_cd
completers['rmdir'] = complete_cd
completers['bash'] = complete_from_bash
completers['import'] = complete_import
completers['python'] = complete_python
completers['path'] = complete_path

all_completers = list(completers.keys())
completers_enabled = list(all_completers)
