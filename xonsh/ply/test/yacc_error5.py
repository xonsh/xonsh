# -----------------------------------------------------------------------------
# yacc_error5.py
#
# Lineno and position tracking with error tokens
# -----------------------------------------------------------------------------
import sys

if ".." not in sys.path: sys.path.insert(0,"..")
import ply.yacc as yacc

from calclex import tokens

# Parsing rules
precedence = (
    ('left','PLUS','MINUS'),
    ('left','TIMES','DIVIDE'),
    ('right','UMINUS'),
    )

# dictionary of names
names = { }

def p_statement_assign(t):
    'statement : NAME EQUALS expression'
    names[t[1]] = t[3]

def p_statement_assign_error(t):
    'statement : NAME EQUALS error'
    line_start, line_end = t.linespan(3)
    pos_start, pos_end = t.lexspan(3)
    print("Assignment Error at %d:%d to %d:%d" % (line_start,pos_start,line_end,pos_end))

def p_statement_expr(t):
    'statement : expression'
    print(t[1])

def p_expression_binop(t):
    '''expression : expression PLUS expression
                  | expression MINUS expression
                  | expression TIMES expression
                  | expression DIVIDE expression'''
    if t[2] == '+'  : t[0] = t[1] + t[3]
    elif t[2] == '-': t[0] = t[1] - t[3]
    elif t[2] == '*': t[0] = t[1] * t[3]
    elif t[2] == '/': t[0] = t[1] / t[3]

def p_expression_uminus(t):
    'expression : MINUS expression %prec UMINUS'
    t[0] = -t[2]

def p_expression_group(t):
    'expression : LPAREN expression RPAREN'
    line_start, line_end = t.linespan(2)
    pos_start, pos_end = t.lexspan(2)
    print("Group at %d:%d to %d:%d" % (line_start,pos_start, line_end, pos_end))
    t[0] = t[2]

def p_expression_group_error(t):
    'expression : LPAREN error RPAREN'
    line_start, line_end = t.linespan(2)
    pos_start, pos_end = t.lexspan(2)
    print("Syntax error at %d:%d to %d:%d" % (line_start,pos_start, line_end, pos_end))
    t[0] = 0
    
def p_expression_number(t):
    'expression : NUMBER'
    t[0] = t[1]

def p_expression_name(t):
    'expression : NAME'
    try:
        t[0] = names[t[1]]
    except LookupError:
        print("Undefined name '%s'" % t[1])
        t[0] = 0

def p_error(t):
    print("Syntax error at '%s'" % t.value)

parser = yacc.yacc()
import calclex
calclex.lexer.lineno=1
parser.parse("""
a = 3 +
(4*5) +
(a b c) +
+ 6 + 7
""", tracking=True)






