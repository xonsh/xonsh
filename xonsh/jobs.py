
import platform
from warnings import warn

try:
    from xonsh.jobs_posix import *
except AttributeError:
    if platform.system() != 'Windows':
        warn('Unable to import jobs_posix.py.  Falling back to '
             'jobs_not_implemented.py',
             RuntimeWarning)

    from xonsh.jobs_not_implemented import *
