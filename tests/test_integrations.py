"""Tests involving running Xonsh in subproc.
This requires Xonsh installed in venv or otherwise available on PATH
"""
import os
import shutil
import tempfile
import subprocess as sp

import pytest

from xonsh.lib.os import indir

from tools import (
    skip_if_on_msys,
    skip_if_on_windows,
    skip_if_on_darwin,
    ON_WINDOWS,
    ON_DARWIN,
    ON_TRAVIS,
)


PATH = (
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "bin")
    + os.pathsep
    + os.environ["PATH"]
)


skip_if_no_xonsh = pytest.mark.skipif(
    shutil.which("xonsh") is None, reason="xonsh not on PATH"
)
skip_if_no_make = pytest.mark.skipif(
    shutil.which("make") is None, reason="make command not on PATH"
)
skip_if_no_sleep = pytest.mark.skipif(
    shutil.which("sleep") is None, reason="sleep command not on PATH"
)


def run_xonsh(
    cmd, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT, single_command=False
):
    env = dict(os.environ)
    env["PATH"] = PATH
    env["XONSH_DEBUG"] = "0"  # was "1"
    env["XONSH_SHOW_TRACEBACK"] = "1"
    env["RAISE_SUBPROC_ERROR"] = "0"
    env["PROMPT"] = ""
    xonsh = shutil.which("xonsh", path=PATH)
    if single_command:
        args = [xonsh, "--no-rc", "-c", cmd]
        input = None
    else:
        args = [xonsh, "--no-rc"]
        input = cmd

    proc = sp.Popen(
        args,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        universal_newlines=True,
    )

    try:
        out, err = proc.communicate(input=input, timeout=20)
    except sp.TimeoutExpired:
        proc.kill()
        raise
    return out, err, proc.returncode


def check_run_xonsh(cmd, fmt, exp, exp_rtn=0):
    """The ``fmt`` parameter is a function
    that formats the output of cmd, can be None.
    """
    out, err, rtn = run_xonsh(cmd, stderr=sp.PIPE)
    if callable(fmt):
        out = fmt(out)
    if callable(exp):
        exp = exp()
    assert out == exp, err
    assert rtn == exp_rtn, err


#
# The following list contains a (stdin, stdout, returncode) tuples
#

ALL_PLATFORMS = [
    # test calling a function alias
    (
        """
def _f():
    print('hello')

aliases['f'] = _f
f
""",
        "hello\n",
        0,
    ),
    # test redirecting a function alias to a file
    (
        """
def _f():
    print('Wow Mom!')

aliases['f'] = _f
f > tttt

with open('tttt') as tttt:
    s = tttt.read().strip()
print('REDIRECTED OUTPUT: ' + s)
""",
        "REDIRECTED OUTPUT: Wow Mom!\n",
        0,
    ),
    # test redirecting a function alias from stderr -> stdout
    (
        """
def _f(args, stdin, stdout, stderr):
    print('The Truth is Out There', file=stderr)

aliases['f'] = _f
f e>o
""",
        "The Truth is Out There\n",
        0,
    ),
    # test system exit in function alias
    (
        """
import sys
def _f():
    sys.exit(42)

aliases['f'] = _f
print(![f].returncode)
""",
        "42\n",
        0,
    ),
    # test uncaptured streaming alias,
    # order actually printed in is non-deterministic
    (
        """
def _test_stream(args, stdin, stdout, stderr):
    print('hallo on stream', file=stderr)
    print('hallo on stream', file=stdout)
    return 1

aliases['test-stream'] = _test_stream
x = ![test-stream]
print(x.returncode)
""",
        "hallo on stream\nhallo on stream\n1\n",
        0,
    ),
    # test captured streaming alias
    (
        """
def _test_stream(args, stdin, stdout, stderr):
    print('hallo on err', file=stderr)
    print('hallo on out', file=stdout)
    return 1

aliases['test-stream'] = _test_stream
x = !(test-stream)
print(x.returncode)
""",
        "hallo on err\n1\n",
        0,
    ),
    # test piping aliases
    (
        """
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
""",
        "HEY!",
        0,
    ),
    # test output larger than most pipe buffers
    (
        """
def _g(args, stdin=None):
    for i in range(1000):
        print('x' * 100)

aliases['g'] = _g
g
""",
        (("x" * 100) + "\n") * 1000,
        0,
    ),
    # test piping 'real' command
    (
        """
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

![python tests/bin/cat tttt | python tests/bin/wc]
""",
        " 1  2 10 <stdin>\n" if ON_WINDOWS else " 1  2 9 <stdin>\n",
        0,
    ),
    # test double  piping 'real' command
    (
        """
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

![python tests/bin/cat tttt | python tests/bin/wc | python tests/bin/wc]
""",
        " 1  4 18 <stdin>\n" if ON_WINDOWS else " 1  4 16 <stdin>\n",
        0,
    ),
    # test unthreadable alias (which should trigger a ProcPoxy call)
    (
        """
from xonsh.tools import unthreadable

@unthreadable
def _f():
    return 'hello\\n'

aliases['f'] = _f
f
""",
        "hello\n",
        0,
    ),
    # test ambiguous globs
    (
        """
import os

def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo

files = ['Actually_test.tst', 'Actually.tst', 'Complete_test.tst', 'Complete.tst']

# touch the file
for f in files:
    with open(f, 'w'):
        pass

# echo the files
echo *.tst and echo *_test.tst
echo *_test.tst
echo *_test.tst and echo *.tst

# remove the files
for f in files:
    os.remove(f)
""",
        "Actually.tst Actually_test.tst Complete.tst Complete_test.tst\n"
        "Actually_test.tst Complete_test.tst\n"
        "Actually_test.tst Complete_test.tst\n"
        "Actually_test.tst Complete_test.tst\n"
        "Actually.tst Actually_test.tst Complete.tst Complete_test.tst\n",
        0,
    ),
    #
    # test ambiguous line continuations
    #
    (
        """
def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo

echo --option1 \\
--option2
echo missing \\
EOL""",
        "--option1 --option2\nmissing EOL\n",
        0,
    ),
    #
    # test @$() with aliases
    #
    (
        """
aliases['ls'] = 'spam spam sausage spam'

echo @$(which ls)
""",
        "spam spam sausage spam\n",
        0,
    ),
    #
    # test @$() without leading/trailig WS
    #
    (
        """
def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo

echo foo_@$(echo spam)_bar
""",
        "foo_spam_bar\n",
        0,
    ),
    #
    # test @$() outer product
    #
    (
        """
def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo

echo foo_@$(echo spam sausage)_bar
""",
        "foo_spam_bar foo_sausage_bar\n",
        0,
    ),
    #
    # test redirection
    #
    (
        """
echo Just the place for a snark. >tttt
python tests/bin/cat tttt
""",
        "Just the place for a snark.\n",
        0,
    ),
    #
    # Test completion registration and subproc stack
    #
    (
        """
def _f():
    def j():
        pass

    global aliases
    aliases['j'] = j

    def completions(pref, *args):
        return set(['hello', 'world'])

    completer add j completions "start"


_f()
del _f

""",
        "",
        0,
    ),
    #
    # test single check_output
    #
    (
        """
def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo

from xonsh.lib.subprocess import check_output

print(check_output(["echo", "hello"]).decode("utf8"))
""",
        "hello\n\n",
        0,
    ),
    #
    # test contextvars
    #
    (
        """
import sys

if sys.version_info[:2] >= (3, 7):
    with open("sourced-file.xsh", "w") as f:
        f.write('''
from contextvars import ContextVar

var = ContextVar('var', default='spam')
var.set('foo')
        ''')

    source sourced-file.xsh

    print("Var " + var.get())

    import os
    os.remove('sourced-file.xsh')
else:
    print("Var foo")
""",
        "Var foo\n",
        0,
    ),
    #
    # test logical subprocess operators
    #
    (
        """
def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo

echo --version and echo a
echo --version && echo a
echo --version or echo a
echo --version || echo a
echo -+version and echo a
echo -+version && echo a
echo -+version or echo a
echo -+version || echo a
echo -~version and echo a
echo -~version && echo a
echo -~version or echo a
echo -~version || echo a
""",
        """--version
a
--version
a
--version
--version
-+version
a
-+version
a
-+version
-+version
-~version
a
-~version
a
-~version
-~version
""",
        0,
    ),
]


@skip_if_no_xonsh
@pytest.mark.parametrize("case", ALL_PLATFORMS)
def test_script(case):
    script, exp_out, exp_rtn = case
    out, err, rtn = run_xonsh(script)
    assert exp_out == out
    assert exp_rtn == rtn


ALL_PLATFORMS_STDERR = [
    # test redirecting a function alias
    (
        """
def _f(args, stdin, stdout):
    print('Wow Mom!', file=stdout)

aliases['f'] = _f
f o>e
""",
        "Wow Mom!\n",
        0,
    )
]


@skip_if_no_xonsh
@pytest.mark.parametrize("case", ALL_PLATFORMS_STDERR)
def test_script_stderr(case):
    script, exp_err, exp_rtn = case
    out, err, rtn = run_xonsh(script, stderr=sp.PIPE)
    assert exp_err == err
    assert exp_rtn == rtn


@skip_if_no_xonsh
@skip_if_on_windows
@pytest.mark.parametrize(
    "cmd, fmt, exp",
    [
        ("pwd", None, lambda: os.getcwd() + "\n"),
        ("echo WORKING", None, "WORKING\n"),
        ("ls -f", lambda out: out.splitlines().sort(), os.listdir().sort()),
    ],
)
def test_single_command_no_windows(cmd, fmt, exp):
    check_run_xonsh(cmd, fmt, exp)


@skip_if_no_xonsh
def test_eof_syntax_error():
    """Ensures syntax errors for EOF appear on last line."""
    script = "x = 1\na = (1, 0\n"
    out, err, rtn = run_xonsh(script, stderr=sp.PIPE)
    assert ":0:0: EOF in multi-line statement" not in err
    assert ":2:0: EOF in multi-line statement" in err


@skip_if_no_xonsh
def test_open_quote_syntax_error():
    script = (
        "#!/usr/bin/env xonsh\n\n"
        'echo "This is line 3"\n'
        'print ("This is line 4")\n'
        'x = "This is a string where I forget the closing quote on line 5\n'
        'echo "This is line 6"\n'
    )
    out, err, rtn = run_xonsh(script, stderr=sp.PIPE)
    assert """:3:5: ('code: "This is line 3"',)""" not in err
    assert ':5:4: "' in err
    assert "SyntaxError:" in err


_bad_case = pytest.mark.skipif(
    ON_DARWIN or ON_WINDOWS or ON_TRAVIS, reason="bad platforms"
)


@skip_if_no_xonsh
@_bad_case
def test_printfile():
    check_run_xonsh("printfile.xsh", None, "printfile.xsh\n")


@skip_if_no_xonsh
@_bad_case
def test_printname():
    check_run_xonsh("printfile.xsh", None, "printfile.xsh\n")


@skip_if_no_xonsh
@_bad_case
def test_sourcefile():
    check_run_xonsh("printfile.xsh", None, "printfile.xsh\n")


@skip_if_no_xonsh
@_bad_case
@pytest.mark.parametrize(
    "cmd, fmt, exp",
    [
        # test subshell wrapping
        (
            """
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

(wc) < tttt
""",
            None,
            " 1  2 9 <stdin>\n",
        ),
        # test subshell statement wrapping
        (
            """
with open('tttt', 'w') as fp:
    fp.write("Wow mom!\\n")

(wc;) < tttt
""",
            None,
            " 1  2 9 <stdin>\n",
        ),
    ],
)
def test_subshells(cmd, fmt, exp):
    check_run_xonsh(cmd, fmt, exp)


@skip_if_no_xonsh
@skip_if_on_windows
@pytest.mark.parametrize("cmd, exp", [("pwd", lambda: os.getcwd() + "\n")])
def test_redirect_out_to_file(cmd, exp, tmpdir):
    outfile = tmpdir.mkdir("xonsh_test_dir").join("xonsh_test_file")
    command = "{} > {}\n".format(cmd, outfile)
    out, _, _ = run_xonsh(command)
    content = outfile.read()
    if callable(exp):
        exp = exp()
    assert content == exp


@skip_if_no_make
@skip_if_no_xonsh
@skip_if_no_sleep
@skip_if_on_windows
@pytest.mark.xfail(strict=False)  # TODO: fixme (super flaky on OSX)
def test_xonsh_no_close_fds():
    # see issue https://github.com/xonsh/xonsh/issues/2984
    makefile = (
        "default: all\n"
        "all:\n"
        "\t$(MAKE) s\n"
        "s:\n"
        "\t$(MAKE) a b\n"
        "a:\n"
        "\tsleep 1\n"
        "b:\n"
        "\tsleep 1\n"
    )
    with tempfile.TemporaryDirectory() as d, indir(d):
        with open("Makefile", "w") as f:
            f.write(makefile)
        out = sp.check_output(["make", "-sj2", "SHELL=xonsh"], universal_newlines=True)
        assert "warning" not in out


@skip_if_no_xonsh
@pytest.mark.parametrize(
    "cmd, fmt, exp",
    [("cat tttt | wc", lambda x: x > "", True),],  # noqa E231 (black removes space)
)
def test_pipe_between_subprocs(cmd, fmt, exp):
    "verify pipe between subprocesses doesn't throw an exception"
    check_run_xonsh(cmd, fmt, exp)


@skip_if_no_xonsh
@skip_if_on_windows
def test_negative_exit_codes_fail():
    # see issue 3309
    script = 'python -c "import os; os.abort()" && echo OK\n'
    out, err, rtn = run_xonsh(script)
    assert "OK" != out
    assert "OK" != err


@skip_if_no_xonsh
@pytest.mark.parametrize(
    "cmd, exp",
    [
        ("echo '&'", "&\n"),
        ("echo foo'&'", "foo'&'\n"),
        ("echo foo '&'", "foo &\n"),
        ("echo foo '&' bar", "foo & bar\n"),
    ],
)
def test_ampersand_argument(cmd, exp):
    script = """
#!/usr/bin/env xonsh
def _echo(args):
    print(' '.join(args))
aliases['echo'] = _echo
{}
""".format(
        cmd
    )
    out, _, _ = run_xonsh(script)
    assert out == exp


# issue 3402
@skip_if_no_xonsh
@skip_if_on_windows
@pytest.mark.parametrize(
    "cmd, exp_rtn",
    [
        ("sys.exit(0)", 0),
        ("sys.exit(100)", 100),
        ("sh -c 'exit 0'", 0),
        ("sh -c 'exit 1'", 1),
    ],
)
def test_single_command_return_code(cmd, exp_rtn):
    _, _, rtn = run_xonsh(cmd, single_command=True)
    assert rtn == exp_rtn


@skip_if_no_xonsh
@skip_if_on_msys
@skip_if_on_windows
@skip_if_on_darwin
def test_argv0():
    check_run_xonsh("checkargv0.xsh", None, "OK\n")
