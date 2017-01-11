"""Tests xonsh contexts."""
from textwrap import dedent

from tools import check_exec
from xonsh.contexts import Block, Functor

import pytest


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_builtins, xonsh_execer):
    return xonsh_execer

#
# helpers
#

X1_WITH = ('x = 1\n'
           'with! Block() as b:\n')
SIMPLE_WITH = 'with! Block() as b:\n'
FUNC_WITH = ('x = 1\n'
             'def func():\n'
             '    y = 1\n'
             '    with! Block() as b:\n'
             '{body}'
             '    y += 1\n'
             '    return b\n'
             'x += 1\n'
             'rtn = func()\n'
             'x += 1\n')

FUNC_OBSG = {'x': 3}
FUNC_OBSL = {'y': 1}


def norm_body(body):
    if not isinstance(body, str):
        body = '\n'.join(body)
    body = dedent(body)
    body = body.splitlines()
    return body


def block_checks_glb(name, glbs, body, obs=None):
    block = glbs[name]
    obs = obs or {}
    for k, v in obs.items():
        assert v == glbs[k]
    body = norm_body(body)
    assert body == block.lines
    assert glbs is block.glbs
    assert block.locs is None


def block_checks_func(name, glbs, body, obsg=None, obsl=None):
    block = glbs[name]
    obsg = obsg or {}
    for k, v in obsg.items():
        assert v == glbs[k]
    body = norm_body(body)
    assert body == block.lines
    assert glbs is block.glbs
    # local context tests
    locs = block.locs
    assert locs is not None
    obsl = obsl or {}
    for k, v in obsl.items():
        assert v == locs[k]


#
# Block tests
#

def test_block_noexec():
    s = ('x = 1\n'
         'with! Block():\n'
         '    x += 42\n')
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    assert 1 == glbs['x']


def test_block_oneline():
    body = '    x += 42\n'
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body, {'x': 1})


def test_block_manylines():
    body = ('    ![echo wow mom]\n'
            '# bad place for a comment\n'
            '    x += 42')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body, {'x': 1})


def test_block_leading_comment():
    # leading comments do not show up in block lines
    body = ('    # I am a leading comment\n'
            '    x += 42\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, ['    x += 42'], {'x': 1})


def test_block_trailing_comment():
    # trailing comments show up in block lines
    body = ('    x += 42\n'
            '    # I am a trailing comment\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body, {'x': 1})


def test_block_trailing_line_continuation():
    body = ('    x += \\\n'
            '         42\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body, {'x': 1})


def test_block_trailing_close_paren():
    body = ('    x += int("42"\n'
            '             )\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body, {'x': 1})


def test_block_trailing_close_many():
    body = ('    x = {None: [int("42"\n'
            '                    )\n'
            '                ]\n'
            '         }\n')
    s = SIMPLE_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body)


def test_block_trailing_triple_string():
    body = ('    x = """This\n'
            'is\n'
            '"probably"\n'
            '\'not\' what I meant.\n'
            '"""\n')
    s = SIMPLE_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('b', glbs, body)


def test_block_func_oneline():
    body = '        x += 42\n'
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_manylines():
    body = ('        ![echo wow mom]\n'
            '# bad place for a comment\n'
            '        x += 42\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_leading_comment():
    # leading comments do not show up in block lines
    body = ('        # I am a leading comment\n'
            '        x += 42\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, '        x += 42\n',
                                 FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_comment():
    # trailing comments show up in block lines
    body = ('        x += 42\n'
            '        # I am a trailing comment\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_blockfunc__trailing_line_continuation():
    body = ('        x += \\\n'
            '             42\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_close_paren():
    body = ('        x += int("42"\n'
            '                 )\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_close_many():
    body = ('        x = {None: [int("42"\n'
            '                        )\n'
            '                    ]\n'
            '             }\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


def test_block_func_trailing_triple_string():
    body = ('        x = """This\n'
            'is\n'
            '"probably"\n'
            '\'not\' what I meant.\n'
            '"""\n')
    s = FUNC_WITH.format(body=body)
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_func('rtn', glbs, body, FUNC_OBSG, FUNC_OBSL)


#
# Functor tests
#

X2_WITH = ('{var} = 1\n'
           'with! Functor() as f:\n'
           '{body}'
           '{var} += 1\n'
           '{calls}\n'
           )

def test_functor_oneline_onecall_class():
    body = ('    global y\n'
            '    y += 42\n')
    calls = 'f()'
    s = X2_WITH.format(body=body, calls=calls, var='y')
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'y': 44})


def test_functor_oneline_onecall_func():
    body = ('    global z\n'
            '    z += 42\n')
    calls = 'f.func()'
    s = X2_WITH.format(body=body, calls=calls, var='z')
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'z': 44})


def test_functor_oneline_onecall_both():
    body = ('    global x\n'
            '    x += 42\n')
    calls = 'f()\nf.func()'
    s = X2_WITH.format(body=body, calls=calls, var='x')
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'x': 86})


XA_WITH = ('x = [1]\n'
           'with! Functor() as f:\n'
           '{body}'
           'x.append(2)\n'
           '{calls}\n'
           )

def test_functor_oneline_append():
    body = '    x.append(3)\n'
    calls = 'f()\n'
    s = XA_WITH.format(body=body, calls=calls)
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'x': [1, 2, 3]})


def test_functor_return():
    body = '    x = 42'
    t = ('res = 0\n'
         'with! Functor(rtn="x") as f:\n'
         '{body}\n'
         'res = f()\n')
    s = t.format(body=body)
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'res': 42})


def test_functor_args():
    body = '    x = 42 + a'
    t = ('res = 0\n'
         'with! Functor(args=("a",), rtn="x") as f:\n'
         '{body}\n'
         'res = f(2)\n')
    s = t.format(body=body)
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'res': 44})


def test_functor_kwargs():
    body = '    x = 42 + a + b'
    t = ('res = 0\n'
         'with! Functor(kwargs={{"a": 1, "b": 12}}, rtn="x") as f:\n'
         '{body}\n'
         'res = f(b=6)\n')
    s = t.format(body=body)
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'res': 49})


def test_functor_fullsig():
    body = '    x = 42 + a + b + c'
    t = ('res = 0\n'
         'with! Functor(args=("c",), kwargs={{"a": 1, "b": 12}}, rtn="x") as f:\n'
         '{body}\n'
         'res = f(55)\n')
    s = t.format(body=body)
    glbs = {'Functor': Functor}
    check_exec(s, glbs=glbs, locs=None)
    block_checks_glb('f', glbs, body, {'res': 110})


