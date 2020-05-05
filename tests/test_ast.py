"""Xonsh AST tests."""
import ast as pyast

from xonsh import ast
from xonsh.ast import Tuple, Name, Store, min_line, Call, BinOp, isexpression

import pytest

from tools import check_parse, nodes_equal


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_execer):
    return xonsh_execer


def test_gather_names_name():
    node = Name(id="y", ctx=Store())
    exp = {"y"}
    obs = ast.gather_names(node)
    assert exp == obs


def test_gather_names_tuple():
    node = Tuple(elts=[Name(id="y", ctx=Store()), Name(id="z", ctx=Store())])
    exp = {"y", "z"}
    obs = ast.gather_names(node)
    assert exp == obs


def test_gather_load_store_names_tuple():
    node = Tuple(elts=[Name(id="y", ctx=Store()), Name(id="z", ctx=Store())])
    lexp = set()
    sexp = {"y", "z"}
    lobs, sobs = ast.gather_load_store_names(node)
    assert lexp == lobs
    assert sexp == sobs


@pytest.mark.parametrize(
    "line1",
    [
        "x = 1",  # Both, ls and l remain undefined.
        "ls = 1",  # l remains undefined.
        "l = 1",  # ls remains undefined.
    ],
)
def test_multilline_num(xonsh_execer, line1):
    # Subprocess transformation happens on the second line,
    # because not all variables are known.
    code = line1 + "\nls -l\n"
    tree = check_parse(code)
    lsnode = tree.body[1]
    assert 2 == min_line(lsnode)
    assert isinstance(lsnode.value, Call)


def test_multilline_no_transform():
    # No subprocess transformations happen here, since all variables are known.
    code = "ls = 1\nl = 1\nls -l\n"
    tree = check_parse(code)
    lsnode = tree.body[2]
    assert 3 == min_line(lsnode)
    assert isinstance(lsnode.value, BinOp)


@pytest.mark.parametrize(
    "inp",
    [
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
    ],
)
def test_unmodified(inp):
    # Context sensitive parsing should not modify AST
    exp = pyast.parse(inp)
    obs = check_parse(inp)

    assert nodes_equal(exp, obs)


@pytest.mark.parametrize(
    "test_input",
    ["echo; echo && echo\n", "echo; echo && echo a\n", "true && false && true\n"],
)
def test_whitespace_subproc(test_input):
    assert check_parse(test_input)


@pytest.mark.parametrize(
    "inp,exp",
    [
        ("1+1", True),
        ("1+1;", True),
        ("1+1\n", True),
        ("1+1; 2+2", False),
        ("1+1; 2+2;", False),
        ("1+1; 2+2\n", False),
        ("1+1; 2+2;\n", False),
        ("x = 42", False),
    ],
)
def test_isexpression(xonsh_execer, inp, exp):
    obs = isexpression(inp)
    assert exp is obs
