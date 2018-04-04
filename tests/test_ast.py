"""Xonsh AST tests."""
import ast as pyast

from xonsh import ast
from xonsh.ast import Tuple, Name, Store, min_line, Call, BinOp, pdump

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


def test_gather_load_store_names_tuple():
    node = Tuple(elts=[Name(id='y', ctx=Store()),
                       Name(id='z', ctx=Store())])
    lexp = set()
    sexp = {'y', 'z'}
    lobs, sobs = ast.gather_load_store_names(node)
    assert lexp == lobs
    assert sexp == sobs


@pytest.mark.parametrize('line1', [
    # this second line wil be transformed into a subprocess call
    'x = 1',
    # this second line wil be transformed into a subprocess call even though
    # ls is defined.
    'ls = 1',
    # the second line wil be transformed still even though l exists.
    'l = 1',
])
def test_multilline_num(xonsh_builtins, line1):
    code = line1 + '\nls -l\n'
    tree = check_parse(code)
    lsnode = tree.body[1]
    assert 2 == min_line(lsnode)
    assert isinstance(lsnode.value, Call)


def test_multilline_no_transform():
    # no subprocess transformations happen here since all variables are known
    code = 'ls = 1\nl = 1\nls -l\n'
    tree = check_parse(code)
    lsnode = tree.body[2]
    assert 3 == min_line(lsnode)
    assert isinstance(lsnode.value, BinOp)


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
"""import os
path = '/path/to/wakka'
paths = []
for root, dirs, files in os.walk(path):
    paths.extend(os.path.join(root, d) for d in dirs)
    paths.extend(os.path.join(root, f) for f in files)
""",
"""lambda x: x + 1
""",
])
def test_unmodified(inp):
    # Context sensitive parsing should not modify AST
    exp = pyast.parse(inp)
    obs = check_parse(inp)

    assert nodes_equal(exp, obs)
