from xonsh.tools import VER_3_5, VER_FULL

if VER_FULL >= VER_3_5:
    from xonsh.tokenize.tokenize_35 import *
else:
    from xonsh.tokenize.tokenize_34 import *
