from xonsh.platform import PYTHON_VERSION_INFO

if PYTHON_VERSION_INFO >= (3, 5, 0):
    from xonsh.tokenize.tokenize_35 import *
else:
    from xonsh.tokenize.tokenize_34 import *
