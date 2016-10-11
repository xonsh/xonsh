# -----------------------------------------------------------------------------
# yacc_error6.py
#
# Panic mode recovery test
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

def p_statements(t):
    'statements : statements statement'
    pass

def p_statements_1(t):
    'statements : statement'
    pass

def p_statement_assign(p):
    'statement : LPAREN NAME EQUALS expression RPAREN'
    print("%s=%s" % (p[2],p[4]))

def p_statement_expr(t):
    'statement : LPAREN expression RPAREN'
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

def p_expression_number(t):
    'expression : NUMBER'
    t[0] = t[1]

def p_error(p):
    if p:
        print("Line %d: Syntax error at '%s'" % (p.lineno, p.value))
    # Scan ahead looking for a name token
    while True:
        tok = parser.token()
        if not tok or tok.type == 'RPAREN':
            break
    if tok:
        parser.restart()
    return None

parser = yacc.yacc()
import calclex
calclex.lexer.lineno=1

parser.parse("""
(a = 3 + 4)
(b = 4 + * 5 - 6 + *)
(c = 10 + 11)
""")






