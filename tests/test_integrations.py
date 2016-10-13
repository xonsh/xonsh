import os
import subprocess

import pytest

#
# The following list contains a (stdin, stdout, returncode) tuples
#

ALL_PLATFORMS = [
# test calling a function alias
("""
def _f():
    print('hello')

aliases['f'] = _f
f
""", "hello\n", 0),
# test redirecting a function alias
("""
def _f():
    print('Wow Mom!')

aliases['f'] = _f
f > tttt

with open('tttt') as tttt:
    s = tttt.read().strip()
print('REDIRECTED OUTPUT: ' + s)
""", "REDIRECTED OUTPUT: Wow Mom!\n", 0),
]


@pytest.mark.parametrize('case', ALL_PLATFORMS)
def test_script(case):
    script, exp_out, exp_rtn = case
    env = dict(os.environ)
    env['XONSH_DEBUG'] = '1'
    env['XONSH_SHOW_TRACEBACK'] = '1'
    p = subprocess.Popen(['xonsh', '--no-rc'],
                         env=env,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         universal_newlines=True,
                         )
    try:
        out, err = p.communicate(input=script, timeout=1)
    except subprocess.TimeoutExpired:
        p.kill()
        raise
    assert exp_rtn == p.returncode
    assert exp_out == out


