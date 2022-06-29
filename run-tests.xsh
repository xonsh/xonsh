#!/usr/bin/env xonsh
import sys
import subprocess
from typing import List

import xonsh.cli_utils as xcli

from xonsh.tools import print_color
import itertools


$RAISE_SUBPROC_ERROR = True
# $XONSH_TRACE_SUBPROC = True


def colored_tracer(cmds, **_):
    cmd = " ".join(itertools.chain.from_iterable(cmds))
    print_color(f"{{GREEN}}$ {{BLUE}}{cmd}{{RESET}}", file=sys.stderr)


def _replace_args(args: List[str], num: int) -> List[str]:
    return [
         (arg % num) if "%d" in arg else arg
         for arg in args
    ]


def test(
        report_cov: xcli.Arg('--report-coverage', '-c', action="store_true") = False,
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

    Examples
    --------
    `xonsh run-tests.xsh -- --junitxml=junit/test-results.%%d.xml`
    """

    if report_cov:
        ![pytest @(_replace_args(pytest_args, 0)) --cov --cov-report=xml --cov-report=term]
    else:
        # during CI run, some tests take longer to complete on windows
        ![pytest @(_replace_args(pytest_args, 0)) --durations=5]


def qa():
    """QA checks"""
    $XONSH_TRACE_SUBPROC_FUNC = colored_tracer
    $XONSH_TRACE_SUBPROC = True

    black --check xonsh xontrib tests xompletions
    isort --check xonsh xontrib tests xompletions

    python -m flake8

    mypy xonsh
    mypy xontrib --namespace-packages --explicit-package-bases
    mypy xompletions --namespace-packages --explicit-package-bases

    pytest -m news


if __name__ == '__main__':
    parser = xcli.make_parser("test commands")
    parser.add_command(test)
    parser.add_command(qa)

    try:
        xcli.dispatch(parser)
    except subprocess.CalledProcessError as ex:
        parser.exit(1, f"Failed with {ex}")
