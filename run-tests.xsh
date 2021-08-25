#!/usr/bin/env xonsh
import subprocess
from typing import List

import xonsh.cli_utils as xcli


$RAISE_SUBPROC_ERROR = True
# $XONSH_NO_AMALGAMATE = 1
# $XONSH_TRACE_SUBPROC = True


def _replace_args(args: List[str], num: int) -> List[str]:
    return [
         (arg % num) if "%d" in arg else arg
         for arg in args
    ]


def test(
        report_cov: xcli.Arg('--report-coverage', '-c', action="store_true") = False,
        no_amalgam: xcli.Arg('--no-amalgam', '-n', action="store_true") = False,
        pytest_args: xcli.Arg(nargs='*')=(),
):
    """Run pytest.

    Parameters
    ----------
    report_cov
        Report coverage at the end of the test
    pytest_args
        arbitrary arguments that gets passed to pytest's invocation.
        Use %%d to parameterize and prevent overwrite
    no_amalgam
        Disable amalgamation check

    Examples
    --------
    `xonsh run-tests.xsh -- --junitxml=junit/test-results.%%d.xml`
    """

    if (not no_amalgam) and not $(xonsh -c "import xonsh.main; print(xonsh.main.__file__, end='')").endswith("__amalgam__.py"):
        echo "Tests need to run from the amalgamated xonsh! install with `pip install .` (without `-e`)"
        exit(1)

    if report_cov:
        $XONSH_NO_AMALGAMATE = True
        ![pytest @(_replace_args(pytest_args, 0)) --cov --cov-report=xml --cov-report=term]
    else:
        # during CI run, some tests take longer to complete on windows
        ![pytest @(_replace_args(pytest_args, 0)) --durations=5]


def qa():
    """QA checks"""
    $XONSH_NO_AMALGAMATE = True

    echo "---------- Check Black formatter -----------"
    black --check xonsh xontrib tests

    echo "---------- Running flake8 ----------"
    python -m flake8

    echo "---------- Running mypy ----------"
    mypy --version
    # todo: add xontrib folder here
    mypy xonsh --exclude xonsh/ply

    echo "---------- Running news items check ----------"
    pytest -m news


if __name__ == '__main__':
    parser = xcli.make_parser("test commands")
    parser.add_command(test)
    parser.add_command(qa)

    try:
        xcli.dispatch(parser)
    except subprocess.CalledProcessError as ex:
        parser.exit(1, f"Failed with {ex}")
