"""Tests xonsh contexts."""
from nose.tools import assert_equal, assert_is

from tools import (mock_xonsh_env, execer_setup, check_exec, check_eval,
    check_parse, skip_if)

from xonsh.contexts import Block

#
# helpers
#

def setup():
    execer_setup()

def block_checks_glb(name, glbs, body, obs=None):
    block = glbs[name]
    obs = obs or {}
    for k, v in obs.items():
        yield assert_equal, v, glbs[k]
    if isinstance(body, str):
        body = body.splitlines()
    yield assert_equal, body, block.lines
    yield assert_is, glbs, block.glbs
    yield assert_is, None, block.locs

X1_WITH = ('x = 1\n'
           'with Block() as b:\n')
SIMPLE_WITH = 'with Block() as b:\n'


#
# tests
#

def test_block_noexec():
    s = ('x = 1\n'
         'with Block():\n'
         '    x += 42\n')
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    assert_equal(1, glbs['x'])


def test_block_oneline():
    body = '    x += 42\n'
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, body, {'x': 1})


def test_block_manylines():
    body = ('    ![echo wow mom]\n'
            '# bad place for a comment\n'
            '    x += 42')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, body, {'x': 1})


def test_block_leading_comment():
    # leading comments do not show up in block lines
    body = ('    # I am a leading comment\n'
            '    x += 42\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, ['    x += 42'], {'x': 1})


def test_block_trailing_comment():
    # trailing comments do not show up in block lines
    body = ('    x += 42\n'
            '    # I am a trailing comment\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, ['    x += 42'], {'x': 1})


def test_block_trailing_line_continuation():
    body = ('    x += \\\n'
            '         42\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, body, {'x': 1})


def test_block_trailing_close_paren():
    body = ('    x += int("42"\n'
            '             )\n')
    s = X1_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, body, {'x': 1})


def test_block_trailing_close_many():
    body = ('    x = {None: [int("42"\n'
            '                    )\n'
            '                ]\n'
            '         }\n')
    s = SIMPLE_WITH + body
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    yield from block_checks_glb('b', glbs, body)

