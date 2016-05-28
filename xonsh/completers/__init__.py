from collections import OrderedDict

from xonsh.completers.path import complete_path
from xonsh.completers.dirs import (complete_cd, complete_rmdir)
#from xonsh.completers.commands import complete_command

completers = OrderedDict()
completers['cd'] = complete_cd
completers['rmdir'] = complete_cd
completers['path'] = complete_path

all_completers = list(completers.keys())
completers_enabled = list(all_completers)
