"""Tests xonsh contexts."""
from nose.tools import assert_equal, assert_is

from tools import (mock_xonsh_env, execer_setup, check_exec, check_eval,
    check_parse, skip_if)

from xonsh.contexts import Block

def setup():
    execer_setup()


def test_block_noexec():
    s = ('x = 1\n'
         'with Block():\n'
         '    x += 42\n')
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    assert_equal(1, glbs['x'])

def test_block_oneline():
    s = ('x = 1\n'
         'with Block() as b:\n'
         '    x += 42\n')
    glbs = {'Block': Block}
    check_exec(s, glbs=glbs, locs=None)
    b = glbs['b']
    yield assert_equal, '    x += 42', b.lines
    yield assert_is, glbs, b.glbs
    yield assert_is, None, b.locs
