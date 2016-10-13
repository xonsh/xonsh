import os
import sys
import shutil
import subprocess

import pytest

import xonsh
from xonsh.platform import ON_WINDOWS

XONSH_PREFIX = xonsh.__file__
if 'site-packages' in XONSH_PREFIX:
    # must be installed version of xonsh
    num_up = 5
else:
    # must be in source dir
    num_up = 2
for i in range(num_up):
    XONSH_PREFIX = os.path.dirname(XONSH_PREFIX)
PATH = os.path.join(os.path.dirname(__file__), 'bin') + os.pathsep + \
       os.path.join(XONSH_PREFIX, 'bin') + os.pathsep + \
       os.path.join(XONSH_PREFIX, 'Scripts') + os.pathsep + \
       os.path.join(XONSH_PREFIX, 'scripts') + os.pathsep + \
       os.path.dirname(sys.executable) + os.pathsep + \
       os.environ['PATH']

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
    env['PATH'] = PATH
    env['XONSH_DEBUG'] = '1'
    env['XONSH_SHOW_TRACEBACK'] = '1'
    xonsh = 'xonsh.bat' if ON_WINDOWS else 'xon.sh'
    xonsh = shutil.which(xonsh, path=PATH)
    p = subprocess.Popen([xonsh, '--no-rc'],
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
    assert exp_out == out
    assert exp_rtn == p.returncode


