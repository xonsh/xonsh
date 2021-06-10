#!/usr/bin/env xonsh
import argparse
import subprocess
from typing import List


$RAISE_SUBPROC_ERROR = True
# $XONSH_NO_AMALGAMATE = 1
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

    if (not ns.no_amalgam) and not $(xonsh -c "import xonsh.main; print(xonsh.main.__file__, end='')").endswith("__amalgam__.py"):
        echo "Tests need to run from the amalgamated xonsh! install with `pip install .` (without `-e`)"
        exit(1)

    if ns.report_coverage:
        $XONSH_NO_AMALGAMATE = True
        ![pytest @(_replace_args(args, 0)) --cov --cov-report=xml --cov-report=term]
    else:
        ![pytest @(_replace_args(args, 0))]


def qa(ns: argparse.Namespace):
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
        '-c',
        action="store_true",
        default=False,
        help="Report coverage at the end of the test",
    )
    test_parser.add_argument(
        '--no-amalgam',
        '-n',
        action="store_true",
        default=False,
        help="Disable amalgamation check.",
    )
    test_parser.set_defaults(func=test)

    qa_parser = commands.add_parser('qa', help=qa.__doc__)
    qa_parser.set_defaults(func=qa)

    args = parser.parse_args()
    try:
        args.func(args)
    except subprocess.CalledProcessError as ex:
        parser.exit(1, f"Failed with {ex}")
