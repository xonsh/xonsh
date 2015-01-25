"""The xonsh abstract syntax tree node."""
from __future__ import unicode_literals, print_function
from ast import Module, Num, Expr, Str, Bytes, UnaryOp, UAdd, USub, Invert, \
    BinOp, Add, Sub, Mult, Div, FloorDiv, Mod, Pow, Compare, Lt, Gt, LtE, \
    GtE, Eq, NotEq, In, NotIn, Is, IsNot