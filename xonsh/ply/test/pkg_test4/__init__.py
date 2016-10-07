# Tests proper handling of lextab and parsetab files in package structures
# Check of warning messages when files aren't writable

# Here for testing purposes
import sys
if '..' not in sys.path:  
    sys.path.insert(0, '..')

import ply.lex
import ply.yacc

def patched_open(filename, mode):
    if 'w' in mode:
        raise IOError("Permission denied %r" % filename)
    return open(filename, mode)

ply.lex.open = patched_open
ply.yacc.open = patched_open
try:
    from .parsing.calcparse import parser
finally:
    del ply.lex.open
    del ply.yacc.open


