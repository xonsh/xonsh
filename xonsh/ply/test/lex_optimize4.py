# -----------------------------------------------------------------------------
# lex_optimize4.py
# -----------------------------------------------------------------------------
import re
import sys

if ".." not in sys.path: sys.path.insert(0,"..")
import ply.lex as lex

tokens = [
    "PLUS",
    "MINUS",
    "NUMBER",
    ]

t_PLUS = r'\+?'
t_MINUS = r'-'
t_NUMBER = r'(\d+)'

def t_error(t):
    pass


# Build the lexer
lex.lex(optimize=True, lextab="opt4tab", reflags=re.UNICODE)
lex.runmain(data="3+4")
