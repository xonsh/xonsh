"""Xonsh AST tests."""
import ast as pyast

from xonsh import ast
from xonsh.ast import Tuple, Name, Store, min_line

import pytest

from tools import check_parse, nodes_equal


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_execer):
    return xonsh_execer

def test_gather_names_name():
    node = Name(id='y', ctx=Store())
    exp = {'y'}
    obs = ast.gather_names(node)
    assert exp == obs


def test_gather_names_tuple():
    node = Tuple(elts=[Name(id='y', ctx=Store()),
                       Name(id='z', ctx=Store())])
    exp = {'y', 'z'}
    obs = ast.gather_names(node)
    assert exp == obs

def test_multilline_num():
    code = ('x = 1\n'
            'ls -l\n')  # this second line wil be transformed
    tree = check_parse(code)
    lsnode = tree.body[1]
    assert 2 == min_line(lsnode)


@pytest.mark.parametrize('inp', [
"""def f():
    if True:
        pass
""",
"""def f(x):
    if x:
        pass
""",
"""def f(*args):
    if not args:
        pass
""",
"""def f(*, y):
    if y:
        pass
""",
"""def f(**kwargs):
    if not kwargs:
        pass
""",
"""def f(k=42):
    if not k:
        pass
""",
"""def f(k=10, *, a, b=1, **kw):
    if not kw and b:
        pass
""",
])
def test_args_in_scope(inp):
    # Context sensitive parsing should not modify AST
    exp = pyast.parse(inp)
    obs = check_parse(inp)
    assert nodes_equal(exp, obs)
