#!/usr/bin/env xonsh
import argparse
import subprocess
from typing import List


$XONSH_DEBUG = 1
$RAISE_SUBPROC_ERROR = True
# $XONSH_TRACE_SUBPROC = True


def _replace_args(args: List[str], num: int) -> List[str]:
    return [
         (arg % num) if "%d" in arg else arg
         for arg in args
    ]


def test(ns: argparse.Namespace):
    """Run pytest.

    Examples
    --------
    `xonsh run-tests.xsh -- --junitxml=junit/test-results.%%d.xml`
    """

    args = ns.pytest_args

    if ns.report_coverage:
        ![coverage run -m pytest @(_replace_args(args, 0))]
        ![coverage report -m]
        ![coverage xml]
    else:
        ![pytest @(_replace_args(args, 0))]


def qa(ns: argparse.Namespace):
    """QA checks"""

    echo "---------- Check Black formatter -----------"
    black --check xonsh xontrib tests

    echo "---------- Running flake8 ----------"
    python -m flake8

    echo "---------- Running mypy ----------"
    mypy --version
    # todo: add xontrib folder here
    mypy xonsh --exclude xonsh/ply


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=lambda *args: parser.print_help())

    commands = parser.add_subparsers()

    test_parser = commands.add_parser('test', help=test.__doc__)
    test_parser.add_argument(
        'pytest_args',
        nargs='*',
        help="arbitrary arguments that gets passed to pytest's invocation."
             " Use %%d to parameterize and prevent overwrite "
    )
    test_parser.add_argument(
        '--report-coverage',
        action="store_true",
        default=False,
        help="Report coverage at the end of the test",
    )
    test_parser.set_defaults(func=test)

    qa_parser = commands.add_parser('qa', help=qa.__doc__)
    qa_parser.set_defaults(func=qa)

    args = parser.parse_args()
    try:
        args.func(args)
    except subprocess.CalledProcessError as ex:
        parser.exit(1, f"Failed with {ex}")
