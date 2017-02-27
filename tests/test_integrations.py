import os
import sys
import shutil
import subprocess as sp

import pytest

import xonsh
from xonsh.platform import ON_WINDOWS

from tools import (skip_if_on_windows, skip_if_on_darwin, skip_if_on_travis,
    ON_WINDOWS, ON_DARWIN, ON_TRAVIS)


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


skip_if_no_xonsh = pytest.mark.skipif(shutil.which('xonsh', path=PATH) is None,
                                      reason='xonsh not on path')


def run_xonsh(cmd, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT):
    env = dict(os.environ)
    env['PATH'] = PATH
    env['XONSH_DEBUG'] = '1'
    env['XONSH_SHOW_TRACEBACK'] = '1'
    env['RAISE_SUBPROC_ERROR'] = '1'
    env['PROMPT'] = ''
    xonsh = 'xonsh.bat' if ON_WINDOWS else 'xon.sh'
    xonsh = shutil.which(xonsh, path=PATH)
    proc = sp.Popen([xonsh, '--no-rc'],
                    env=env,
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                    universal_newlines=True,
                    )
    try:
        out, err = proc.communicate(input=cmd, timeout=10)
    except sp.TimeoutExpired:
        proc.kill()
        raise
    return out, err, proc.returncode


def check_run_xonsh(cmd, fmt, exp):
    """The ``fmt`` parameter is a function
    that formats the output of cmd, can be None.
    """
    out, err, rtn = run_xonsh(cmd, stderr=sp.DEVNULL)
    if callable(fmt):
        out = fmt(out)
    if callable(exp):
        exp = exp()
    assert out == exp
    assert rtn == 0


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
# test system exit in function alias
("""
import sys
def _f():
    sys.exit(42)

aliases['f'] = _f
print(![f].returncode)
""", "42\n", 0),
# test uncaptured streaming alias,
# order actually printed in is non-deterministic
("""
def _test_stream(args, stdin, stdout, stderr):
    print('hallo on stream', file=stderr)
    print('hallo on stream', file=stdout)
    return 1

aliases['test-stream'] = _test_stream
x = ![test-stream]
print(x.returncode)
""", "hallo on stream\nhallo on stream\n1\n", 0),
# test captured streaming alias
("""
def _test_stream(args, stdin, stdout, stderr):
    print('hallo on err', file=stderr)
    print('hallo on out', file=stdout)
    return 1

aliases['test-stream'] = _test_stream
x = !(test-stream)
print(x.returncode)
""", "hallo on err\n1\n", 0),
# test piping aliases
("""
def dummy(args, inn, out, err):
    out.write('hey!')
    return 0

def dummy2(args, inn, out, err):
    s = inn.read()
    out.write(s.upper())
    return 0

aliases['d'] = dummy
aliases['d2'] = dummy2
d | d2
""", "HEY!", 0),
# test output larger than most pipe buffers
("""
def _g(args, stdin=None):
    for i in range(1000):
        print('x' * 100)

aliases['g'] = _g
g
""", (("x"*100) + '\n') * 1000, 0),
# test piping 'real' command
("""
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

![cat tttt | wc]
""", '      1       2      10\n' if ON_WINDOWS else " 1  2 9 <stdin>\n", 0),
# test double  piping 'real' command
("""
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

![cat tttt | wc | wc]
""", '      1       3      24\n' if ON_WINDOWS else " 1  4 16 <stdin>\n", 0),
# test unthreadable alias (which should trigger a ProcPoxy call)
("""
from xonsh.tools import unthreadable

@unthreadable
def _f():
    return 'hello\\n'

aliases['f'] = _f
f
""", "hello\n", 0),
]


@pytest.mark.parametrize('case', ALL_PLATFORMS)
def test_script(case):
    script, exp_out, exp_rtn = case
    out, err, rtn = run_xonsh(script)
    assert exp_out == out
    assert exp_rtn == rtn


ALL_PLATFORMS_STDERR = [
# test redirecting a function alias
("""
def _f(args, stdout):
    print('Wow Mom!', file=stdout)

aliases['f'] = _f
f o>e
""", "Wow Mom!\n", 0),
]

@pytest.mark.parametrize('case', ALL_PLATFORMS_STDERR)
def test_script_stder(case):
    script, exp_err, exp_rtn = case
    out, err, rtn = run_xonsh(script, stderr=sp.PIPE)
    assert exp_err == err
    assert exp_rtn == rtn

@skip_if_on_windows
@pytest.mark.parametrize('cmd, fmt, exp', [
    ('pwd', None, lambda: os.getcwd() + '\n'),
    ('echo WORKING', None, 'WORKING\n'),
    ('ls -f', lambda out: out.splitlines().sort(), os.listdir().sort()),
    ])
def test_single_command_no_windows(cmd, fmt, exp):
    check_run_xonsh(cmd, fmt, exp)


_bad_case = pytest.mark.skipif(ON_DARWIN or ON_WINDOWS or ON_TRAVIS,
                               reason="bad platforms")

@_bad_case
def test_printfile():
    check_run_xonsh('printfile.xsh', None, 'printfile.xsh\n')


@_bad_case
def test_printname():
    check_run_xonsh('printfile.xsh', None, 'printfile.xsh\n')


@_bad_case
def test_sourcefile():
    check_run_xonsh('printfile.xsh', None, 'printfile.xsh\n')


@_bad_case
@pytest.mark.parametrize('cmd, fmt, exp', [
    # test subshell wrapping
    ("""
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

(wc) < tttt
""", None, " 1  2 9 <stdin>\n"),
    # test subshell statement wrapping
    ("""
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

(wc;) < tttt
""", None, " 1  2 9 <stdin>\n"),
])
def test_subshells(cmd, fmt, exp):
    check_run_xonsh(cmd, fmt, exp)


@skip_if_on_windows
@pytest.mark.parametrize('cmd, exp', [
    ('pwd', lambda: os.getcwd() + '\n'),
    ])
def test_redirect_out_to_file(cmd, exp, tmpdir):
    outfile = tmpdir.mkdir('xonsh_test_dir').join('xonsh_test_file')
    command = '{} > {}\n'.format(cmd, outfile)
    out, _, _ = run_xonsh(command)
    content = outfile.read()
    if callable(exp):
        exp = exp()
    assert content == exp
