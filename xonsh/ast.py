"""The xonsh abstract syntax tree node."""
from __future__ import unicode_literals, print_function
from ast import Module, Num, Expr, Str, Bytes, UnaryOp, UAdd, USub, Invert, \
    BinOp, Add, Sub, Mult, Div, FloorDiv, Mod, Pow, Compare, Lt, Gt, LtE, \
    GtE, Eq, NotEq, In, NotIn, Is, IsNot, Not, BoolOp, Or, And, Subscript, \
    Index, Load, Slice, List, Tuple, Set, Dict, AST, NameConstant, Ellipsis, \
    Name, GeneratorExp, Store, comprehension