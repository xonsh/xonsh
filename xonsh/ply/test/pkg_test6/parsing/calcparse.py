# -----------------------------------------------------------------------------
# yacc_simple.py
#
# A simple, properly specifier grammar
# -----------------------------------------------------------------------------

from .calclex import tokens
from ply import yacc

# Parsing rules
precedence = (
    ('left','PLUS','MINUS'),
    ('left','TIMES','DIVIDE'),
    ('right','UMINUS'),
    )

# dictionary of names
names = { }

from .statement import *

from .expression import *

def p_error(t):
    print("Syntax error at '%s'" % t.value)

import os.path
parser = yacc.yacc(outputdir=os.path.dirname(__file__))





