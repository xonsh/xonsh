

try:
    from xonsh.jobs_posix import *
except AttributeError:
    from xonsh.jobs_not_implemented import *

    
